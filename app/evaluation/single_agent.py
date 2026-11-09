"""Single-agent baseline: ONE LLM tool loop with all six tools.

Same incident data, same ToolExecutor (same tools, budget, timeouts, fault injection),
same model and limits as the multi-agent system. No orchestrator, specialists, critic,
message bus, deterministic scoring or pre-checks: the agent plans, gathers, reasons,
judges confidence and decides the final status itself.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.agents.base_agent import BaseAgent, BudgetStop, fmt_time
from app.agents.reasoning_agent import HypothesisIn
from app.agents.reporting_agent import NarrativeSubmission
from app.llm.provider import BudgetExceededError, LLMProvider
from app.models.agent import AgentName
from app.models.hypothesis import Hypothesis, ScoreBreakdown
from app.models.incident import IncidentReport
from app.models.investigation import FinalStatus, InvestigationConfig, InvestigationState
from app.orchestration.state import create_runtime
from app.reporting.report_generator import build_report
from app.tools import ALL_TOOL_NAMES

logger = logging.getLogger("single_agent")

SYSTEM = """You are an expert Site Reliability Engineer investigating a production incident on your own.
You have tools for logs, metrics, deployments, configuration changes, the service dependency graph and historical incidents.

Investigate systematically: characterise symptoms vs baseline, find the earliest anomaly, examine recent changes and dependencies, then develop 2-4 competing root-cause hypotheses with supporting AND contradicting evidence.
Rules:
- Temporal correlation is not causation; a cause must precede its effects. Distinguish symptoms from causes.
- A failed or partial tool result is NOT evidence of health; record it as an evidence gap.
- Cite exact evidence_id values from tool results (met-..., logpat-..., log-..., dep-..., cfg-..., topo-..., hist-...). Never invent evidence.
- Historical similarity is only an analogy.
- If evidence is insufficient or contradictory, choose final_status INCONCLUSIVE rather than guessing. Use ROOT_CAUSE_IDENTIFIED only when the evidence is strong and alternatives are ruled out; PROBABLE_ROOT_CAUSE when it is the best but unconfirmed explanation.
Issue independent tool calls in parallel. Finish by calling submit_investigation."""


class SingleHypothesis(HypothesisIn):
    confidence: float = Field(ge=0, le=1, description="your own confidence 0-1")


class SingleAgentSubmission(BaseModel):
    hypotheses: list[SingleHypothesis] = Field(min_length=1, max_length=5)
    final_status: Literal["ROOT_CAUSE_IDENTIFIED", "PROBABLE_ROOT_CAUSE", "INCONCLUSIVE"]
    executive_summary: str
    corrective_actions: list[str] = Field(min_length=1)
    preventive_actions: list[str] = Field(min_length=1)
    monitoring_recommendations: list[str] = Field(min_length=1)
    limitations: list[str] = Field(default_factory=list)
    evidence_gaps: list[str] = Field(default_factory=list)
    conclusion: str


class SingleInvestigatorAgent(BaseAgent):
    name = AgentName.SINGLE_AGENT
    system_prompt = SYSTEM
    tool_names = ALL_TOOL_NAMES
    submit_name = "submit_investigation"
    submit_description = "Submit the complete investigation result."
    submit_model = SingleAgentSubmission
    max_tokens = 6000

    def briefing(self) -> str:
        inc = self.state.incident
        t0 = inc.symptom_start
        return (f"INCIDENT {inc.incident_id} ({inc.severity}) reported {fmt_time(inc.reported_at)}: {inc.title}\n"
                f"{inc.description}\nReported affected services: {', '.join(inc.affected_services)}.\n"
                f"Reported symptom start T0={fmt_time(t0)}. Suggested analysis window {fmt_time(t0 - timedelta(minutes=30))} "
                f"to {fmt_time(t0 + timedelta(minutes=25))}; baseline window {fmt_time(t0 - timedelta(minutes=60))} to "
                f"{fmt_time(t0 - timedelta(minutes=30))}. Telemetry exists from T0-60m to T0+30m. "
                f"Tool-call budget: {self.state.config.max_tool_calls}.")


async def run_single_agent(incident: IncidentReport, llm: LLMProvider,
                           config: Optional[InvestigationConfig] = None) -> InvestigationState:
    rt = create_runtime(incident, llm, config, system="single_agent")
    state = rt.state
    state.stats.started_at = datetime.now(timezone.utc)
    agent = SingleInvestigatorAgent(llm, rt.executor, state)
    t0 = time.perf_counter()
    sub: Optional[SingleAgentSubmission] = None
    # equal step allowance: the multi-agent system runs ~6 agents x max_agent_steps
    steps = min(state.config.max_agent_steps * 3, state.config.max_llm_calls - 1)
    try:
        sub = await asyncio.wait_for(agent.run_loop(agent.briefing(), max_steps=steps),
                                     timeout=state.config.investigation_timeout_s)
        state.stats.termination_reason = "agent submitted"
    except asyncio.TimeoutError:
        state.stats.termination_reason = "investigation timeout"
    except (BudgetStop, BudgetExceededError) as e:
        state.stats.termination_reason = f"budget exhausted: {e}"
    except Exception as e:  # noqa: BLE001
        state.errors.append(repr(e))
        state.stats.termination_reason = f"agent failed: {e!r}"
        state.stats.agent_failures += 1

    if sub is not None:
        state.hypotheses = [Hypothesis(**h.model_dump(exclude={"confidence"}), confidence=h.confidence,
                                       score=ScoreBreakdown(total=h.confidence,
                                                            explanation=["self-reported by the single agent"]))
                            for h in sub.hypotheses]
        state.final_status = FinalStatus(sub.final_status)
        top = state.top_hypothesis()
        if top is None or top.category.value == "unknown":
            state.final_status = FinalStatus.INCONCLUSIVE
        narrative = NarrativeSubmission(
            executive_summary=sub.executive_summary, corrective_actions=sub.corrective_actions,
            preventive_actions=sub.preventive_actions, monitoring_recommendations=sub.monitoring_recommendations,
            limitations=sub.limitations + [f"[agent-reported gap] {g}" for g in sub.evidence_gaps][:8],
            conclusion=sub.conclusion)
    else:
        state.final_status = FinalStatus.INVESTIGATION_FAILED
        narrative = NarrativeSubmission(executive_summary="Single-agent investigation did not complete.",
                                        corrective_actions=["n/a"], preventive_actions=["n/a"],
                                        monitoring_recommendations=["n/a"], limitations=[state.stats.termination_reason],
                                        conclusion="Investigation failed.")
    state.stats.duration_s = time.perf_counter() - t0
    state.stats.finished_at = datetime.now(timezone.utc)
    state.report = build_report(state, narrative).model_dump(mode="json")
    return state
