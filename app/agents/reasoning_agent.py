"""AGENT 4: Reasoning -- competing root-cause hypotheses."""
from __future__ import annotations

import json
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.agents.base_agent import BaseAgent
from app.agents.scoring import observed_onset, rescore_all
from app.models.agent import AgentName, InvestigationTask
from app.models.evidence import EvidenceRef
from app.models.hypothesis import EvidenceRequest, Hypothesis, RootCauseCategory

SYSTEM = """You are the Reasoning Agent in a production incident investigation team.
You receive structured findings from the Observability and Dependency agents (and, in later rounds, the Critic's feedback) and develop COMPETING root-cause hypotheses.

Method:
- Cite each piece of evidence only once per hypothesis; mark contradicting evidence 'strong' only when it directly refutes the hypothesis.
- Generate 2-4 distinct, plausible hypotheses (different categories or culprit services). Include the "obvious" explanation AND alternatives.
- For each: category (from the enum), culprit_service, mechanism (cause -> effect chain), cause_time (ISO time the proposed cause started), supporting evidence, CONTRADICTING evidence, missing evidence, and recommended investigation.
- Evidence refs must use exact evidence_id values listed in the briefing or returned by get_evidence. Strength: strong (direct, specific), moderate, weak (indirect/temporal only).
- You may use search_historical_incidents for analogies; a historical match is weak, supplementary evidence only.

Reasoning rules:
- Temporal correlation is NOT causation: a change shortly before the incident is only supported if the affected behaviour is mechanistically linked to the change and nothing anomalous started before it.
- A cause must precede its effects. If anomalies began before a proposed cause, cite that as contradicting evidence.
- Distinguish symptoms (latency, high DB CPU, pool saturation) from causes; ask what CAUSED the symptom.
- Do not hide contradictions or invent evidence. If evidence is insufficient, say so via missing_evidence and evidence_requests (target_agent: observability or dependency).
- You do NOT assign confidence numbers; a transparent scoring function computes them from your cited evidence.
Finish by calling submit_hypotheses."""


class HypothesisIn(BaseModel):
    hypothesis_id: str = Field(description="H1, H2, ...")
    category: RootCauseCategory
    culprit_service: Optional[str] = None
    description: str
    mechanism: str
    cause_time: Optional[str] = Field(default=None, description="ISO-8601 time the proposed cause began")
    supporting_evidence: list[EvidenceRef] = Field(default_factory=list)
    contradicting_evidence: list[EvidenceRef] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    recommended_investigation: list[str] = Field(default_factory=list)


class ReasoningSubmission(BaseModel):
    hypotheses: list[HypothesisIn] = Field(min_length=1, max_length=5)
    ranking_rationale: str = Field(description="why the leading hypothesis ranks above the others")
    evidence_requests: list[EvidenceRequest] = Field(default_factory=list)


class ReasoningAgent(BaseAgent):
    name = AgentName.REASONING
    system_prompt = SYSTEM
    tool_names = ["search_historical_incidents"]
    uses_evidence_lookup = True
    submit_name = "submit_hypotheses"
    submit_description = "Submit competing root-cause hypotheses with cited evidence."
    submit_model = ReasoningSubmission
    max_tokens = 10000

    def briefing(self, findings_msgs: list[dict[str, Any]], critic_feedback: Optional[dict[str, Any]],
                 previous: list[dict[str, Any]]) -> str:
        inc = self.state.incident
        onset = observed_onset(self.state)
        lines = [f"INCIDENT {inc.incident_id} ({inc.severity}): {inc.title}\n{inc.description}",
                 f"Reported symptom start: {inc.symptom_start.isoformat()}; earliest strong metric anomaly in collected "
                 f"evidence: {onset.isoformat() if onset else 'unknown'}", "",
                 "FINDINGS RECEIVED FROM SPECIALIST AGENTS:"]
        for m in findings_msgs:
            p = m["payload"]
            lines.append(f"--- from {m['sender']} (task {p.get('task_id')}, round {p.get('round')}): {p.get('summary', '')}")
            if p.get("earliest_symptom"):
                lines.append(f"    earliest symptom: {p['earliest_symptom']}")
            for f in p.get("findings", []):
                ids = ",".join(e["evidence_id"] for e in f.get("evidence", []))
                lines.append(f"  [{f['kind']}] {f['statement']} {{{ids}}}")
            for u in p.get("uncertainties", []):
                lines.append(f"  [uncertainty] {u}")
            if p.get("failed"):
                lines.append(f"  [TASK FAILED] {p.get('error')}")
        lines.append("\nEVIDENCE CATALOGUE (id | type | service | reliability | description):")
        for rec in list(self.state.evidence.values())[:120]:
            if rec.source_type.value == "log" and not rec.evidence_id.startswith("logpat-"):
                continue  # raw log lines are summarised by their pattern records
            lines.append(f"  {rec.evidence_id} | {rec.source_type.value} | {rec.service} | {rec.reliability.value} | {rec.description[:180]}")
        gaps = [g for g in self.state.evidence_gaps if not g.resolved]
        if gaps:
            lines.append("\nKNOWN EVIDENCE GAPS / TOOL FAILURES:")
            lines += [f"  - {g.description} ({g.reason})" for g in gaps[:15]]
        if previous:
            lines.append("\nYOUR PREVIOUS HYPOTHESES (revise them in light of new evidence and critic feedback):")
            lines += [f"  {h['hypothesis_id']} {h['category']} {h.get('culprit_service')}: {h['description']}" for h in previous]
        if critic_feedback:
            lines.append("\nCRITIC FEEDBACK ON THE PREVIOUS ROUND:")
            lines.append(json.dumps({k: critic_feedback.get(k) for k in
                                     ("verdict", "summary", "assessments", "precheck_issues", "unsupported_assumptions",
                                      "alternative_explanations")}, default=str)[:3000])
        return "\n".join(lines)

    async def run(self, task: InvestigationTask, findings_msgs: list[dict[str, Any]],
                  critic_feedback: Optional[dict[str, Any]] = None) -> ReasoningSubmission:
        previous = [h.model_dump(mode="json") for h in self.state.hypotheses]
        sub: ReasoningSubmission = await self.run_loop(self.briefing(findings_msgs, critic_feedback, previous), task)
        if self.state.hypotheses:
            self.state.hypothesis_history.append([h.model_copy(deep=True) for h in self.state.hypotheses])
        hyps = []
        seen = set()
        for i, h in enumerate(sub.hypotheses, 1):
            hid = h.hypothesis_id if h.hypothesis_id not in seen else f"H{i}"
            seen.add(hid)
            hyps.append(Hypothesis(**h.model_dump(exclude={"hypothesis_id"}), hypothesis_id=hid, round_proposed=task.round))
        self.state.hypotheses = hyps
        rescore_all(self.state, adjustments={})
        return sub
