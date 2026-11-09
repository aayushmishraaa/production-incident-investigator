"""AGENT 1: Orchestrator -- plans, dispatches, tracks and terminates the investigation.

The LLM is used for the initial investigation plan (what to investigate, which services,
which tasks can run in parallel). Coordination decisions (DAG, follow-ups, limits,
termination, final status) are deterministic code so they are auditable and bounded.
The Orchestrator never proposes root causes.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.agents.base_agent import BaseAgent, fmt_time
from app.models.agent import AgentName, InvestigationTask
from app.models.evidence import EvidenceGap, SourceType
from app.models.hypothesis import VerdictType
from app.models.investigation import FinalStatus, InvestigationState

SYSTEM = """You are the Orchestrator of a multi-agent production incident investigation.
You do NOT diagnose and must not propose root causes. You plan evidence gathering.

Available specialist agents:
- observability: logs and metrics (error rates, latency, CPU/memory, traffic, timeouts, DB connections, cache, disk IO).
- dependency: deployments, configuration changes, service dependency graph (upstream/downstream).

Use get_service_dependencies to understand which services surround the affected ones, then create 2-4 INDEPENDENT tasks that can run in parallel (at least one per agent). Scope services broadly enough to cover upstream dependencies (databases, caches, called services), not just the reported service. Finish by calling submit_plan."""


class PlannedTask(BaseModel):
    agent: str = Field(pattern="^(observability|dependency)$")
    objective: str
    services: list[str] = Field(default_factory=list, max_length=8)
    focus: list[str] = Field(default_factory=list)


class PlanSubmission(BaseModel):
    incident_summary: str
    key_services: list[str] = Field(default_factory=list)
    tasks: list[PlannedTask] = Field(min_length=2, max_length=4)
    rationale: str = ""


class OrchestratorAgent(BaseAgent):
    name = AgentName.ORCHESTRATOR
    system_prompt = SYSTEM
    tool_names = ["get_service_dependencies"]
    submit_name = "submit_plan"
    submit_description = "Submit the investigation plan (parallel evidence-gathering tasks)."
    submit_model = PlanSubmission

    def validate_submission(self, output: PlanSubmission) -> Optional[str]:
        known = set(self.executor.store.services()) if self.executor else set()
        bad = sorted({s for t in output.tasks for s in t.services if known and s not in known})
        agents = {t.agent for t in output.tasks}
        problems = []
        if bad:
            problems.append(f"unknown services {bad}; valid: {sorted(known)}")
        if agents != {"observability", "dependency"}:
            problems.append("plan must include at least one observability AND one dependency task")
        return "; ".join(problems) or None

    # ---------------------------------------------------------------- planning
    async def plan(self) -> list[InvestigationTask]:
        inc = self.state.incident
        briefing = (f"INCIDENT {inc.incident_id} ({inc.severity}) reported {fmt_time(inc.reported_at)}: {inc.title}\n"
                    f"{inc.description}\nSymptom start: {fmt_time(inc.symptom_start)}. Reported affected services: "
                    f"{', '.join(inc.affected_services)}.")
        try:
            plan = await self.run_loop(briefing, max_steps=4)
            self.state.plan = plan.model_dump()
            planned = plan.tasks
        except Exception as e:  # noqa: BLE001 - fall back to a safe default plan
            self.state.errors.append(f"orchestrator planning failed, using default plan: {e!r}")
            self.state.log("orchestrator", "plan_fallback", error=repr(e))
            planned = self.default_plan()
            self.state.plan = {"incident_summary": inc.title, "tasks": [t.model_dump() for t in planned], "fallback": True}
        return [InvestigationTask(agent=AgentName(t.agent), objective=t.objective, services=t.services,
                                  focus=t.focus, round=1) for t in planned]

    def default_plan(self) -> list[PlannedTask]:
        svcs = self.state.incident.affected_services or ["api-gateway"]
        return [
            PlannedTask(agent="observability", objective="Characterise symptoms: compare logs and metrics of affected "
                        "services and their direct dependencies against baseline; find the earliest anomaly.",
                        services=svcs, focus=["logs", "metrics"]),
            PlannedTask(agent="dependency", objective="Identify deployments, configuration changes and dependency "
                        "relationships relevant to the affected services and assess timing against onset.",
                        services=svcs, focus=["deployments", "config", "topology"]),
        ]

    # ---------------------------------------------------------------- coordination (deterministic)
    def coverage_gaps(self) -> list[EvidenceGap]:
        """Identify missing evidence after a gathering round (for affected services)."""
        gaps = []
        have = {(e.source_type, e.service) for e in self.state.evidence.values()}
        for svc in self.state.incident.affected_services:
            if (SourceType.METRIC, svc) not in have:
                gaps.append(EvidenceGap(description=f"no metric evidence collected for affected service {svc}",
                                        source_type=SourceType.METRIC, service=svc, raised_by="orchestrator"))
        if not any(e.source_type in (SourceType.DEPLOYMENT, SourceType.CONFIG) for e in self.state.evidence.values()) and \
                not any(c.tool_name in ("get_deployments", "get_config_changes") and c.success for c in self.state.tool_calls):
            gaps.append(EvidenceGap(description="change history (deployments/config) not successfully retrieved",
                                    raised_by="orchestrator"))
        return gaps

    def followup_tasks(self, verdict_payload: dict, depends_on: list[str]) -> list[InvestigationTask]:
        tasks, seen = [], set()
        for req in verdict_payload.get("evidence_requests", [])[:3]:
            key = (req["target_agent"], req["request"][:80])
            if key in seen:
                continue
            seen.add(key)
            tasks.append(InvestigationTask(
                agent=AgentName(req["target_agent"]), objective=f"FOLLOW-UP requested by critic: {req['request']}"
                + (f" (reason: {req.get('reason')})" if req.get("reason") else ""),
                services=req.get("services", []), round=self.state.round, depends_on=depends_on,
                created_by=AgentName.CRITIC))
        return tasks

    def limits_reached(self) -> Optional[str]:
        s, cfg = self.state, self.state.config
        if s.round >= cfg.max_rounds:
            return f"maximum investigation rounds ({cfg.max_rounds}) reached"
        if s.stats.tool_calls >= cfg.max_tool_calls:
            return f"tool-call budget ({cfg.max_tool_calls}) exhausted"
        if s.stats.usage_total.llm_calls >= cfg.max_llm_calls:
            return "LLM call budget exhausted"
        if s.stats.usage_total.cost_usd >= cfg.max_cost_usd:
            return "cost budget exhausted"
        return None

    def decide_final_status(self) -> FinalStatus:
        s, cfg = self.state, self.state.config
        evidence_tasks = [t for t in s.tasks if t.agent in (AgentName.OBSERVABILITY, AgentName.DEPENDENCY)]
        if evidence_tasks and all(t.status.value == "failed" for t in evidence_tasks) and not s.evidence:
            return FinalStatus.INVESTIGATION_FAILED
        verdict = s.latest_verdict()
        top = s.top_hypothesis()
        if verdict is None or top is None or top.category.value == "unknown":
            return FinalStatus.INCONCLUSIVE
        others = sorted((h.confidence for h in s.hypotheses if h is not top and h.status != "rejected"), reverse=True)
        margin = top.confidence - (others[0] if others else 0.0)
        blocking = {i.hypothesis_id for i in verdict.precheck_issues if i.severity == "blocking"}
        if verdict.verdict == VerdictType.APPROVED:
            if top.confidence >= cfg.approve_confidence and margin >= 0.10:
                return FinalStatus.ROOT_CAUSE_IDENTIFIED
            return FinalStatus.PROBABLE_ROOT_CAUSE if top.confidence >= 0.40 else FinalStatus.INCONCLUSIVE
        if verdict.verdict == VerdictType.NEEDS_MORE_EVIDENCE and top.hypothesis_id not in blocking \
                and top.status != "rejected" and top.confidence >= 0.50 and margin >= 0.05:
            return FinalStatus.PROBABLE_ROOT_CAUSE
        return FinalStatus.INCONCLUSIVE
