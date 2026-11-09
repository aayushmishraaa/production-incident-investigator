"""Shared submission schema/helpers for the two evidence-gathering specialists."""
from __future__ import annotations

from datetime import timedelta
from typing import Optional

from pydantic import BaseModel, Field

from app.agents.base_agent import BaseAgent, fmt_time, unknown_ids
from app.models.agent import AgentFinding, AgentOutput, FindingKind, InvestigationTask
from app.models.evidence import EvidenceRef


class FindingIn(BaseModel):
    kind: FindingKind = Field(description="observed_fact | derived_observation | possible_explanation | missing_evidence | contradiction")
    statement: str
    service: Optional[str] = None
    timestamp: Optional[str] = Field(default=None, description="ISO-8601 time the finding refers to")
    evidence_ids: list[str] = Field(default_factory=list, description="exact evidence_id values returned by tools")


class SpecialistSubmission(BaseModel):
    findings: list[FindingIn] = Field(min_length=1, max_length=15)
    earliest_symptom: Optional[str] = Field(default=None, description="ISO time + what, of the earliest anomaly seen")
    summary: str
    uncertainties: list[str] = Field(default_factory=list)


class SpecialistAgent(BaseAgent):
    submit_name = "submit_findings"
    submit_description = "Submit structured findings. Every observed_fact/derived_observation must cite evidence_ids."
    submit_model = SpecialistSubmission

    def validate_submission(self, output: SpecialistSubmission) -> Optional[str]:
        problems = []
        cited = [i for f in output.findings for i in f.evidence_ids]
        bad = unknown_ids(self.state, cited)
        if bad:
            problems.append(f"these evidence_ids do not exist in collected evidence: {bad[:8]} (cite only ids returned by tools)")
        uncited = [f.statement[:60] for f in output.findings
                   if f.kind in (FindingKind.OBSERVED_FACT, FindingKind.DERIVED_OBSERVATION) and not f.evidence_ids]
        if uncited:
            problems.append(f"facts/derived observations without evidence_ids: {uncited[:3]}")
        return "; ".join(problems) or None

    def windows(self) -> str:
        t0 = self.state.incident.symptom_start
        return (f"Reported symptom start T0={fmt_time(t0)}. Suggested analysis window {fmt_time(t0 - timedelta(minutes=30))} "
                f"to {fmt_time(t0 + timedelta(minutes=25))}; baseline window {fmt_time(t0 - timedelta(minutes=60))} to "
                f"{fmt_time(t0 - timedelta(minutes=30))}. Telemetry exists from T0-60m to T0+30m.")

    def to_output(self, sub: SpecialistSubmission, task: InvestigationTask) -> AgentOutput:
        findings = []
        for f in sub.findings:
            valid = [i for i in f.evidence_ids if i in self.state.evidence]  # strip any residual unknown ids
            findings.append(AgentFinding(agent=self.name, task_id=task.task_id, kind=f.kind, statement=f.statement,
                                         service=f.service, timestamp=f.timestamp, round=task.round,
                                         evidence=[EvidenceRef(evidence_id=i) for i in valid]))
        return AgentOutput(findings=findings, earliest_symptom=sub.earliest_symptom, summary=sub.summary,
                           uncertainties=sub.uncertainties)

    def task_briefing(self, task: InvestigationTask, extra: str = "") -> str:
        inc = self.state.incident
        return (
            f"INCIDENT {inc.incident_id} ({inc.severity}): {inc.title}\n{inc.description}\n"
            f"Reported affected services: {', '.join(inc.affected_services) or 'unknown'}\n{self.windows()}\n\n"
            f"YOUR TASK (round {task.round}, id {task.task_id}): {task.objective}\n"
            f"Services to focus on: {', '.join(task.services) or 'use judgement'}\n"
            + (f"Focus areas: {', '.join(task.focus)}\n" if task.focus else "")
            + (f"\nCONTEXT:\n{extra}\n" if extra else "")
        )
