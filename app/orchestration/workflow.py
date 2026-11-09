"""Multi-agent investigation workflow (LangGraph StateGraph).

    plan -> gather -> reason -> critique -> decide --(NEEDS_MORE_EVIDENCE & budget left)--> gather
                                                   \\--(approved / inconclusive / limits)----> report -> END

`gather` runs all ready evidence tasks of the round concurrently (asyncio.gather under a
semaphore). Shared state lives in InvestigationState; agents exchange structured
AgentMessages through the MessageBus.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents.base_agent import BudgetStop
from app.agents.critic_agent import CriticAgent, hypotheses_for_critic, run_prechecks
from app.agents.dependency_agent import DependencyAgent
from app.agents.observability_agent import ObservabilityAgent
from app.agents.orchestrator import OrchestratorAgent
from app.agents.reasoning_agent import ReasoningAgent
from app.agents.reporting_agent import ReportingAgent, fallback_narrative
from app.llm.provider import BudgetExceededError, LLMProvider
from app.models.agent import AgentName, InvestigationTask, MessageType, TaskStatus
from app.models.hypothesis import CriticVerdict, VerdictType
from app.models.incident import IncidentReport
from app.models.investigation import FinalStatus, InvestigationConfig, InvestigationState
from app.orchestration.recovery import run_task_with_recovery
from app.orchestration.state import Runtime, create_runtime
from app.reporting.report_generator import build_report, validated_payload

logger = logging.getLogger("workflow")
EVIDENCE_AGENTS = {AgentName.OBSERVABILITY, AgentName.DEPENDENCY}
STOP_ERRORS = (BudgetStop, BudgetExceededError)


class GraphState(TypedDict, total=False):
    stop: bool
    next: str


class MultiAgentInvestigation:
    def __init__(self, runtime: Runtime):
        self.rt = runtime
        self.state: InvestigationState = runtime.state
        self.orchestrator = OrchestratorAgent(runtime.llm, runtime.executor, runtime.state)
        self.graph = self._build_graph()

    # ------------------------------------------------------------------ graph
    def _build_graph(self):
        g = StateGraph(GraphState)
        g.add_node("plan", self.node_plan)
        g.add_node("gather", self.node_gather)
        g.add_node("reason", self.node_reason)
        g.add_node("critique", self.node_critique)
        g.add_node("decide", self.node_decide)
        g.add_node("report", self.node_report)
        g.add_edge(START, "plan")
        g.add_conditional_edges("plan", lambda s: "report" if s.get("stop") else "gather")
        g.add_conditional_edges("gather", lambda s: "report" if s.get("stop") else "reason")
        g.add_conditional_edges("reason", lambda s: "report" if s.get("stop") else "critique")
        g.add_edge("critique", "decide")
        g.add_conditional_edges("decide", lambda s: s.get("next", "report"), {"gather": "gather", "report": "report"})
        g.add_edge("report", END)
        return g.compile()

    def _stop(self, reason: str) -> GraphState:
        self.state.stats.termination_reason = self.state.stats.termination_reason or reason
        self.state.log("orchestrator", "terminate", reason=reason)
        return {"stop": True}

    # ------------------------------------------------------------------ nodes
    async def node_plan(self, s: GraphState) -> GraphState:
        self.state.log("orchestrator", "investigation_started", incident=self.state.incident.incident_id)
        try:
            tasks = await self.orchestrator.plan()
        except STOP_ERRORS as e:
            return self._stop(f"budget exhausted during planning: {e}")
        self.rt.tasks.add(tasks)
        self.state.log("orchestrator", "plan_created", tasks=len(tasks), parallel=True)
        return {"stop": False}

    async def _run_evidence_task(self, task: InvestigationTask) -> dict[str, Any]:
        agent_cls = ObservabilityAgent if task.agent == AgentName.OBSERVABILITY else DependencyAgent
        agent = agent_cls(self.rt.llm, self.rt.executor, self.state)
        context = ""
        if task.created_by == AgentName.CRITIC:
            verdict = self.state.latest_verdict()
            context = f"The Critic reviewed the current hypotheses and said: {verdict.summary if verdict else ''}"
        out = await agent.run(task, context)
        self.state.findings.extend(out.findings)
        payload = {"task_id": task.task_id, "round": task.round, **out.model_dump(mode="json")}
        self.rt.bus.send(task.agent, AgentName.ORCHESTRATOR, MessageType.FINDINGS, payload)
        return payload

    async def node_gather(self, s: GraphState) -> GraphState:
        ready = self.rt.tasks.ready(EVIDENCE_AGENTS)
        results = await self.rt.tasks.run_wave(ready, self._run_evidence_task)
        stop_err = next((r for r in results if isinstance(r, STOP_ERRORS)), None)
        for t, r in zip(ready, results):
            if r is None or isinstance(r, BaseException):
                self.rt.bus.send(t.agent, AgentName.ORCHESTRATOR, MessageType.ERROR,
                                 {"task_id": t.task_id, "round": t.round, "failed": True, "error": t.error})
        # Orchestrator: collect, check coverage, forward validated findings to the Reasoning Agent
        incoming = self.rt.bus.inbox(AgentName.ORCHESTRATOR, [MessageType.FINDINGS, MessageType.ERROR])
        for gap in self.orchestrator.coverage_gaps():
            if gap.description not in {g.description for g in self.state.evidence_gaps}:
                self.state.evidence_gaps.append(gap)
        for m in incoming:
            payload = dict(m.payload)
            if m.message_type == MessageType.ERROR:
                payload.setdefault("summary", "task failed")
            self.rt.bus.send(AgentName.ORCHESTRATOR, AgentName.REASONING, MessageType.FINDINGS,
                             payload | {"origin": m.sender.value}, in_reply_to=m.message_id)
        if stop_err:
            return self._stop(f"budget exhausted while gathering evidence: {stop_err}")
        if self.state.stats.tool_calls >= self.state.config.max_tool_calls:
            self.state.log("orchestrator", "tool_budget_exhausted")
        return {"stop": False}

    async def node_reason(self, s: GraphState) -> GraphState:
        evidence_ids = [t.task_id for t in self.state.tasks if t.agent in EVIDENCE_AGENTS and t.round == self.state.round]
        task = InvestigationTask(agent=AgentName.REASONING, objective="Develop and rank competing hypotheses",
                                 depends_on=evidence_ids, round=self.state.round)
        self.rt.tasks.add([task])
        findings = [{"sender": m.payload.get("origin", m.sender.value), "payload": m.payload}
                    for m in self.rt.bus.inbox(AgentName.REASONING, [MessageType.FINDINGS], include_consumed=True)]
        feedback_msg = self.rt.bus.latest(AgentName.REASONING, MessageType.CRITIC_VERDICT)
        feedback = feedback_msg.payload if feedback_msg else None

        async def run(t: InvestigationTask):
            return await ReasoningAgent(self.rt.llm, self.rt.executor, self.state).run(t, findings, feedback)

        try:
            sub = await run_task_with_recovery(self.state, task, run)
        except STOP_ERRORS as e:
            return self._stop(f"budget exhausted during reasoning: {e}")
        if sub is None and not self.state.hypotheses:
            return self._stop("reasoning agent failed and no hypotheses exist")
        payload = {"task_id": task.task_id, "round": self.state.round,
                   "hypotheses": hypotheses_for_critic(self.state),
                   "evidence_requests": [r.model_dump() for r in sub.evidence_requests] if sub else []}
        self.rt.bus.send(AgentName.REASONING, AgentName.CRITIC, MessageType.HYPOTHESES, payload)
        self.rt.bus.send(AgentName.REASONING, AgentName.ORCHESTRATOR, MessageType.STATUS,
                         {"task_id": task.task_id, "hypotheses": len(self.state.hypotheses),
                          "ranking_rationale": sub.ranking_rationale if sub else "reused previous hypotheses"})
        return {"stop": False}

    async def node_critique(self, s: GraphState) -> GraphState:
        reasoning_task = [t for t in self.state.tasks if t.agent == AgentName.REASONING][-1]
        task = InvestigationTask(agent=AgentName.CRITIC, objective="Independently review hypotheses",
                                 depends_on=[reasoning_task.task_id], round=self.state.round)
        self.rt.tasks.add([task])
        msgs = self.rt.bus.inbox(AgentName.CRITIC, [MessageType.HYPOTHESES])
        hyps_payload = msgs[-1].payload["hypotheses"] if msgs else hypotheses_for_critic(self.state)

        async def run(t: InvestigationTask):
            return await CriticAgent(self.rt.llm, self.rt.executor, self.state).run(t, hyps_payload)

        stop = False
        try:
            verdict: Optional[CriticVerdict] = await run_task_with_recovery(self.state, task, run)
        except STOP_ERRORS as e:
            verdict, stop = None, True
            self.state.stats.termination_reason = f"budget exhausted during critique: {e}"
        if verdict is None:
            # Critic unavailable: never auto-approve. Use deterministic pre-checks only.
            issues = run_prechecks(self.state)
            verdict = CriticVerdict(verdict=VerdictType.NEEDS_MORE_EVIDENCE, round=self.state.round,
                                    summary="Critic agent unavailable; only automated pre-checks were applied. "
                                            "No hypothesis can be approved without critic review.",
                                    precheck_issues=issues)
        self.state.critic_verdicts.append(verdict)
        vp = verdict.model_dump(mode="json")
        self.rt.bus.send(AgentName.CRITIC, AgentName.ORCHESTRATOR, MessageType.CRITIC_VERDICT, vp)
        self.rt.bus.send(AgentName.CRITIC, AgentName.REASONING, MessageType.CRITIC_VERDICT, vp)
        for req in verdict.evidence_requests:
            self.rt.bus.send(AgentName.CRITIC, AgentName.ORCHESTRATOR, MessageType.EVIDENCE_REQUEST, req.model_dump())
        return {"stop": stop}

    async def node_decide(self, s: GraphState) -> GraphState:
        if s.get("stop"):
            return {"next": "report"}
        msg = self.rt.bus.inbox(AgentName.ORCHESTRATOR, [MessageType.CRITIC_VERDICT])
        self.rt.bus.inbox(AgentName.ORCHESTRATOR, [MessageType.EVIDENCE_REQUEST])  # consumed via verdict payload
        vp = msg[-1].payload if msg else {}
        verdict = vp.get("verdict")
        if verdict in (VerdictType.APPROVED.value, VerdictType.INCONCLUSIVE.value):
            self.state.stats.termination_reason = f"critic verdict {verdict}"
            return {"next": "report"}
        limit = self.orchestrator.limits_reached()
        if limit:
            self.state.stats.termination_reason = f"critic verdict {verdict}; {limit}"
            return {"next": "report"}
        critic_task = [t for t in self.state.tasks if t.agent == AgentName.CRITIC][-1]
        self.state.round += 1
        followups = self.orchestrator.followup_tasks(vp, depends_on=[critic_task.task_id])
        if not followups:
            self.state.stats.termination_reason = f"critic verdict {verdict}; no actionable evidence requests"
            return {"next": "report"}
        self.rt.tasks.add(followups)
        self.state.log("orchestrator", "followup_round", round=self.state.round, tasks=len(followups))
        return {"next": "gather"}

    async def node_report(self, s: GraphState) -> GraphState:
        await self.finalize()
        return {}

    async def finalize(self, use_llm: bool = True) -> None:
        self.state.final_status = self.orchestrator.decide_final_status()
        validated = validated_payload(self.state)
        task = InvestigationTask(agent=AgentName.REPORTING, objective="Write final report", round=self.state.round,
                                 depends_on=[t.task_id for t in self.state.tasks if t.agent == AgentName.CRITIC][-1:])
        self.rt.tasks.add([task])
        self.rt.bus.send(AgentName.ORCHESTRATOR, AgentName.REPORTING, MessageType.REPORT, validated)
        narrative = None
        if use_llm:
            async def run(t: InvestigationTask):
                return await ReportingAgent(self.rt.llm, self.rt.executor, self.state).run(t, validated)
            try:
                narrative = await run_task_with_recovery(self.state, task, run)
            except STOP_ERRORS as e:
                self.state.errors.append(f"reporting skipped: {e}")
        if narrative is None:
            narrative = fallback_narrative(validated)
            if task.status != TaskStatus.FAILED:
                task.status = TaskStatus.SKIPPED
        report = build_report(self.state, narrative)
        self.state.report = report.model_dump(mode="json")
        self.rt.bus.send(AgentName.REPORTING, AgentName.ORCHESTRATOR, MessageType.REPORT,
                         {"final_status": report.final_status.value})


async def run_investigation(incident: IncidentReport, llm: LLMProvider, config: Optional[InvestigationConfig] = None,
                            runtime: Optional[Runtime] = None) -> InvestigationState:
    rt = runtime or create_runtime(incident, llm, config, system="multi_agent")
    inv = MultiAgentInvestigation(rt)
    state = rt.state
    state.stats.started_at = datetime.now(timezone.utc)
    t0 = time.perf_counter()
    try:
        await asyncio.wait_for(inv.graph.ainvoke({"stop": False}, config={"recursion_limit": 60}),
                               timeout=state.config.investigation_timeout_s)
    except asyncio.TimeoutError:
        state.stats.termination_reason = f"investigation timeout ({state.config.investigation_timeout_s}s)"
        state.log("orchestrator", "timeout")
        await inv.finalize(use_llm=False)
    except Exception as e:  # noqa: BLE001 - last-resort guard so a report is always produced
        logger.exception("workflow crashed")
        state.errors.append(f"workflow crashed: {e!r}")
        state.stats.termination_reason = f"workflow error: {e!r}"
        try:
            await inv.finalize(use_llm=False)
        except Exception as e2:  # noqa: BLE001
            state.errors.append(f"finalize failed: {e2!r}")
        state.final_status = FinalStatus.INVESTIGATION_FAILED
        if state.report:
            state.report["final_status"] = FinalStatus.INVESTIGATION_FAILED.value
    state.stats.duration_s = time.perf_counter() - t0
    state.stats.finished_at = datetime.now(timezone.utc)
    if state.report:
        state.report["statistics"]["duration_s"] = round(state.stats.duration_s, 2)
    return state
