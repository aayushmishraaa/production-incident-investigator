"""Agent crashes, retries, failed parallel tasks, tool failures, inconclusive outcomes."""
from __future__ import annotations

from app.llm.mock_provider import StubProvider
from app.llm.provider import LLMError
from app.models.agent import AgentName, TaskStatus
from app.models.investigation import FinalStatus
from app.orchestration.workflow import run_investigation
from tests.conftest import fast_config, incident
from tests.helpers import hyp, submit_hyps


def flaky(n_failures: int):
    state = {"n": 0}

    def fn(ctx):
        if ctx["turn"] == 0 and state["n"] < n_failures:
            state["n"] += 1
            return LLMError("simulated provider crash")
        return None
    return fn


async def test_orchestrator_retries_crashed_agent_task():
    llm = StubProvider(overrides={"observability": flaky(1)})
    st = await run_investigation(incident("INC-001"), llm, fast_config(max_agent_retries=1))
    obs = next(t for t in st.tasks if t.agent == AgentName.OBSERVABILITY)
    assert obs.status == TaskStatus.COMPLETED and obs.attempts == 2
    assert st.stats.agent_failures == 1 and st.stats.agent_retries == 1


async def test_failed_parallel_task_does_not_kill_investigation():
    llm = StubProvider(overrides={"dependency": lambda ctx: LLMError("dependency agent down")})
    st = await run_investigation(incident("INC-001"), llm, fast_config(max_agent_retries=1))
    dep = next(t for t in st.tasks if t.agent == AgentName.DEPENDENCY)
    obs = next(t for t in st.tasks if t.agent == AgentName.OBSERVABILITY)
    assert dep.status == TaskStatus.FAILED and dep.attempts == 2
    assert obs.status == TaskStatus.COMPLETED
    assert st.hypotheses and st.report                     # continued with available evidence
    assert any("dependency" in l for l in st.report["limitations"])
    assert any(m.payload.get("failed") for m in st.messages)


async def test_all_evidence_agents_failing_yields_failed_or_inconclusive():
    boom = lambda ctx: LLMError("down")  # noqa: E731
    st = await run_investigation(incident("INC-001"), StubProvider(overrides={"observability": boom, "dependency": boom}),
                                 fast_config(max_agent_retries=0))
    assert st.final_status in (FinalStatus.INVESTIGATION_FAILED, FinalStatus.INCONCLUSIVE)
    assert st.report is not None


async def test_critic_crash_never_auto_approves():
    st = await run_investigation(incident("INC-001"), StubProvider(overrides={"critic": lambda ctx: LLMError("x")}),
                                 fast_config(max_agent_retries=0, max_rounds=1))
    assert st.critic_verdicts[-1].verdict.value == "NEEDS_MORE_EVIDENCE"
    assert "unavailable" in st.critic_verdicts[-1].summary
    assert st.final_status != FinalStatus.ROOT_CAUSE_IDENTIFIED


async def test_reporting_crash_uses_fallback_narrative():
    st = await run_investigation(incident("INC-001"), StubProvider(overrides={"reporting": lambda ctx: LLMError("x")}),
                                 fast_config(max_agent_retries=0))
    assert st.report and any("deterministically" in l for l in st.report["limitations"])


async def test_tool_failures_retried_and_reported_incident_9():
    st = await run_investigation(incident("INC-009"), StubProvider(), fast_config())
    assert st.stats.tool_failures >= 2 and st.stats.tool_retries >= 2
    assert st.stats.partial_results >= 1
    reasons = {g.reason for g in st.evidence_gaps}
    assert "PARTIAL_DATA" in reasons
    timeouts = [c for c in st.tool_calls if c.tool_name == "query_metrics" and c.attempts > 1]
    assert timeouts and all(c.success for c in timeouts)   # recovered after retry
    assert any("partial" in l.lower() for l in st.report["limitations"])


async def test_failed_tool_is_not_negative_evidence():
    """A failing deployment query must not become 'no deployments' evidence."""
    from app.tools.failure_simulator import FailureSimulator
    from app.orchestration.state import create_runtime
    rt = create_runtime(incident("INC-002"), StubProvider(), fast_config(max_tool_retries=0))
    rt.executor.simulator = FailureSimulator({"get_deployments": {"fail_first_n": 99, "error": "SERVICE_UNAVAILABLE"}})
    st = await run_investigation(rt.state.incident, rt.llm, rt.state.config, runtime=rt)
    assert not any(e.source_type.value == "deployment" for e in st.evidence.values())
    assert any(g.reason == "SERVICE_UNAVAILABLE" for g in st.evidence_gaps)
    assert any("treated as unknown, not healthy" in l for l in st.report["limitations"])
    payload_notes = [m for m in st.messages if m.sender == AgentName.DEPENDENCY]
    assert payload_notes  # dependency agent still reported (missing evidence) instead of silence


async def test_inconclusive_when_evidence_insufficient_incident_10():
    st = await run_investigation(incident("INC-010"), StubProvider(), fast_config())
    assert st.final_status == FinalStatus.INCONCLUSIVE
    assert "could not be conclusively established" in st.report["root_cause_statement"]
    assert "could not be conclusively established" in st.report["conclusion"]


async def test_inconclusive_not_forced_even_with_hypotheses():
    """Weakly supported hypotheses + critic INCONCLUSIVE -> no forced winner."""
    llm = StubProvider(overrides={
        "reasoning": lambda ctx: submit_hyps(hyp("H1", "traffic_surge", "api-gateway", [], missing=["traffic data"]),
                                             hyp("H2", "resource_saturation", "api-gateway", [])),
    })
    st = await run_investigation(incident("INC-010"), llm, fast_config(max_rounds=1))
    assert st.final_status == FinalStatus.INCONCLUSIVE
    assert st.report["probable_root_cause"] is None
