"""AGENT 5: Critic -- independent review with deterministic pre-checks.

Independence mechanisms:
* deterministic pre-checks run BEFORE the LLM (citations exist, cause precedes effect,
  correlation-only support, historical-only support, failed tools on the culprit);
* the LLM critic is blind to the Reasoning Agent's confidence scores and rationale;
* it has its own read access to logs/metrics/deployments/config to verify claims;
* code enforces that it cannot APPROVE a hypothesis with blocking pre-check issues.
"""
from __future__ import annotations

import json
from datetime import timedelta
from typing import Optional

from pydantic import BaseModel, Field

from app.agents.base_agent import BaseAgent
from app.agents.scoring import observed_onset, parse_optional, rescore_all
from app.models.agent import AgentName, InvestigationTask
from app.models.evidence import SourceType
from app.models.hypothesis import (
    CriticVerdict, EvidenceRequest, Hypothesis, HypothesisAssessment, PrecheckIssue, RootCauseCategory, VerdictType,
)
from app.models.investigation import InvestigationState

SYSTEM = """You are the Critic Agent, an independent reviewer in a production incident investigation team.
Your job is to CHALLENGE the hypotheses produced by the Reasoning Agent, not to agree with them.

For each hypothesis:
- Verify the cited evidence actually says what is claimed (use get_evidence, and your own queries of logs/metrics/deployments/config where needed).
- Check timing: does the proposed cause precede the first anomaly? Did anything anomalous start earlier?
- Look for unsupported assumptions, symptoms mistaken for causes, temporal correlation presented as causation, reliance on historical analogy, and evidence from failed/partial tools being treated as proof of health.
- Consider alternative explanations that were not raised.
Automated pre-check results are provided; BLOCKING issues mean that hypothesis cannot be accepted as-is.

Decide per hypothesis: accept | reject | needs_evidence. Then an overall verdict:
- APPROVED: the leading hypothesis is well supported, consistent in time, and alternatives are adequately ruled out.
- NEEDS_MORE_EVIDENCE: a specific, obtainable piece of evidence would settle it. Give precise evidence_requests (target_agent observability or dependency, what to query, which services).
- REJECTED: all current hypotheses are unsupported or contradicted.
- INCONCLUSIVE: evidence is insufficient or contradictory and further queries are unlikely to resolve it.
You do not see confidence scores; judge the evidence itself. Finish by calling submit_verdict."""


class CriticSubmission(BaseModel):
    verdict: VerdictType
    summary: str
    assessments: list[HypothesisAssessment] = Field(default_factory=list)
    unsupported_assumptions: list[str] = Field(default_factory=list)
    alternative_explanations: list[str] = Field(default_factory=list)
    evidence_requests: list[EvidenceRequest] = Field(default_factory=list, max_length=4)


CHANGE_CATEGORIES = {RootCauseCategory.DEPLOYMENT_REGRESSION, RootCauseCategory.CONFIGURATION_REGRESSION}


def run_prechecks(state: InvestigationState) -> list[PrecheckIssue]:
    issues: list[PrecheckIssue] = []
    onset = observed_onset(state)
    failed_services = {c.arguments.get("service") for c in state.tool_calls if not c.success}
    succeeded = {(c.tool_name, c.arguments.get("service")) for c in state.tool_calls if c.success}
    for h in state.hypotheses:
        ids = [r.evidence_id for r in h.supporting_evidence + h.contradicting_evidence]
        missing = [i for i in ids if i not in state.evidence]
        if missing:
            issues.append(PrecheckIssue(hypothesis_id=h.hypothesis_id, check="citation_exists", severity="blocking",
                                        detail=f"cites non-existent evidence (possible hallucination): {missing[:6]}"))
        valid_support = [state.evidence[r.evidence_id] for r in h.supporting_evidence if r.evidence_id in state.evidence]
        if not valid_support and h.category != RootCauseCategory.UNKNOWN:
            issues.append(PrecheckIssue(hypothesis_id=h.hypothesis_id, check="has_support", severity="blocking",
                                        detail="no valid supporting evidence"))
            continue
        types = {e.source_type for e in valid_support}
        if types == {SourceType.HISTORICAL}:
            issues.append(PrecheckIssue(hypothesis_id=h.hypothesis_id, check="historical_only", severity="blocking",
                                        detail="supported only by historical analogy"))
        if h.category in CHANGE_CATEGORIES and types and types <= {SourceType.DEPLOYMENT, SourceType.CONFIG, SourceType.HISTORICAL}:
            issues.append(PrecheckIssue(hypothesis_id=h.hypothesis_id, check="correlation_only", severity="blocking",
                                        detail="change hypothesis supported only by the change record itself (temporal "
                                               "correlation); no log/metric evidence of the changed behaviour"))
        cause = parse_optional(h.cause_time)
        if onset and cause and cause > onset + timedelta(minutes=1):
            issues.append(PrecheckIssue(hypothesis_id=h.hypothesis_id, check="temporal_precedence", severity="blocking",
                                        detail=f"proposed cause at {cause:%H:%M} but anomalies already began at {onset:%H:%M}"))
        if not cause:
            issues.append(PrecheckIssue(hypothesis_id=h.hypothesis_id, check="cause_time", severity="warning",
                                        detail="no cause time given; temporal precedence cannot be verified"))
        if h.culprit_service and not any(e.service == h.culprit_service and e.source_type in (SourceType.METRIC, SourceType.LOG)
                                         for e in valid_support):
            issues.append(PrecheckIssue(hypothesis_id=h.hypothesis_id, check="culprit_symptom", severity="warning",
                                        detail=f"no log/metric evidence cited for culprit {h.culprit_service}"))
        if h.culprit_service in failed_services and not any(s == h.culprit_service for _, s in succeeded):
            issues.append(PrecheckIssue(hypothesis_id=h.hypothesis_id, check="failed_tool", severity="warning",
                                        detail=f"tool queries for {h.culprit_service} failed; absence of data is not evidence"))
        if len(types) == 1 and len(valid_support) >= 1:
            issues.append(PrecheckIssue(hypothesis_id=h.hypothesis_id, check="single_source", severity="warning",
                                        detail=f"all support comes from one source type ({next(iter(types)).value})"))
    return issues


class CriticAgent(BaseAgent):
    name = AgentName.CRITIC
    system_prompt = SYSTEM
    tool_names = ["query_logs", "query_metrics", "get_deployments", "get_config_changes"]
    uses_evidence_lookup = True
    submit_name = "submit_verdict"
    submit_description = "Submit the structured critic verdict."
    submit_model = CriticSubmission

    def briefing(self, hypotheses_payload: list[dict], issues: list[PrecheckIssue]) -> str:
        inc = self.state.incident
        onset = observed_onset(self.state)
        lines = [f"INCIDENT {inc.incident_id}: {inc.title}\n{inc.description}",
                 f"Reported symptom start {inc.symptom_start.isoformat()}; earliest strong metric anomaly "
                 f"{onset.isoformat() if onset else 'unknown'}. Investigation round {self.state.round} of max "
                 f"{self.state.config.max_rounds}.", "", "HYPOTHESES UNDER REVIEW (confidence withheld):"]
        for h in hypotheses_payload:
            lines.append(json.dumps(h, default=str))
        cited = {r["evidence_id"] for h in hypotheses_payload for r in h["supporting_evidence"] + h["contradicting_evidence"]}
        lines.append("\nCITED EVIDENCE AS RECORDED IN SHARED STATE:")
        for eid in sorted(cited):
            rec = self.state.evidence.get(eid)
            lines.append(f"  {eid}: " + ("NOT FOUND IN STATE" if rec is None else
                                         f"[{rec.source_type.value}/{rec.reliability.value}] {rec.description[:200]}"))
        lines.append("\nAUTOMATED PRE-CHECKS:")
        lines += [f"  {i.hypothesis_id} {i.severity.upper()} {i.check}: {i.detail}" for i in issues] or ["  none"]
        fails = self.state.tool_failures()
        if fails:
            lines.append("\nTOOL FAILURES / PARTIAL RESULTS SO FAR:")
            lines += [f"  {c.tool_name}({c.arguments.get('service', '')}) -> {c.error_code or 'PARTIAL_DATA'}" for c in fails[:12]]
        return "\n".join(lines)

    async def run(self, task: InvestigationTask, hypotheses_payload: list[dict]) -> CriticVerdict:
        issues = run_prechecks(self.state)
        sub: CriticSubmission = await self.run_loop(self.briefing(hypotheses_payload, issues), task)
        return self.enforce(sub, issues)

    def enforce(self, sub: CriticSubmission, issues: list[PrecheckIssue]) -> CriticVerdict:
        """Apply code-level guarantees on top of the LLM verdict and update hypothesis status/scores."""
        blocking = {i.hypothesis_id for i in issues if i.severity == "blocking"}
        decisions = {a.hypothesis_id: a for a in sub.assessments}
        adjustments: dict[str, float] = {}
        for h in self.state.hypotheses:
            a = decisions.get(h.hypothesis_id)
            decision = a.decision if a else "needs_evidence"
            if decision == "accept" and h.hypothesis_id in blocking:
                decision = "needs_evidence"
                decisions[h.hypothesis_id] = HypothesisAssessment(
                    hypothesis_id=h.hypothesis_id, decision=decision,
                    reasoning=(a.reasoning if a else "") + " [overridden: blocking pre-check issue]")
            h.status = {"accept": "supported", "reject": "rejected", "needs_evidence": "needs_evidence"}[decision]
            adjustments[h.hypothesis_id] = {"accept": 0.05, "reject": -0.40, "needs_evidence": -0.05}[decision]
        rescore_all(self.state, adjustments)

        verdict = sub.verdict
        top = self.state.top_hypothesis()
        if verdict == VerdictType.APPROVED and (top is None or top.status != "supported"):
            verdict = VerdictType.NEEDS_MORE_EVIDENCE if sub.evidence_requests else VerdictType.INCONCLUSIVE
        if verdict == VerdictType.NEEDS_MORE_EVIDENCE and not sub.evidence_requests:
            sub.evidence_requests = self._default_requests(top)
        return CriticVerdict(
            verdict=verdict, summary=sub.summary + ("" if verdict == sub.verdict else
                                                    f" [verdict changed from {sub.verdict.value} by enforcement rules]"),
            assessments=list(decisions.values()), precheck_issues=issues,
            unsupported_assumptions=sub.unsupported_assumptions, alternative_explanations=sub.alternative_explanations,
            evidence_requests=sub.evidence_requests, round=self.state.round)

    @staticmethod
    def _default_requests(top: Optional[Hypothesis]) -> list[EvidenceRequest]:
        svc = [top.culprit_service] if top and top.culprit_service else []
        return [EvidenceRequest(target_agent="observability", services=svc,
                                request="Verify the onset timing and metrics/logs of the leading hypothesis' culprit service",
                                reason="critic requested more evidence without specifics")]


def hypotheses_for_critic(state: InvestigationState) -> list[dict]:
    """Blind view: strip confidence and score so the critic judges evidence, not numbers."""
    return [h.model_dump(mode="json", exclude={"confidence", "score", "status", "round_proposed"}) for h in state.hypotheses]
