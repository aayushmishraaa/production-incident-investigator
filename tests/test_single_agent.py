"""Single-agent baseline: same tools/limits, no multi-agent machinery."""
from __future__ import annotations

import inspect

from app.evaluation import single_agent
from app.evaluation.single_agent import SingleInvestigatorAgent, run_single_agent
from app.llm.mock_provider import StubProvider
from app.models.investigation import FinalStatus
from app.tools import ALL_TOOL_NAMES
from tests.conftest import fast_config, incident
from tests.helpers import call, resp, script


async def test_baseline_runs_and_produces_report():
    st = await run_single_agent(incident("INC-002"), StubProvider(), fast_config())
    assert st.system == "single_agent" and st.report and st.stats.tool_calls > 0
    assert st.messages == []                     # no inter-agent messaging
    assert {u for u in st.stats.usage_by_agent} == {"single_agent"}


def test_baseline_has_all_six_tools_and_no_coordination():
    assert SingleInvestigatorAgent.tool_names == ALL_TOOL_NAMES
    src = inspect.getsource(single_agent)
    for forbidden in ("MessageBus", "CriticAgent", "ReasoningAgent", "run_prechecks", "TaskManager", "rescore_all"):
        assert forbidden not in src


async def test_baseline_uses_llm_decided_status_and_confidence():
    def fn(ctx):
        if ctx["turn"] == 0:
            return resp(call("get_deployments", {}))
        return resp(call("submit_investigation", {
            "hypotheses": [{"hypothesis_id": "H1", "category": "deployment_regression", "culprit_service": "auth-service",
                            "description": "bad deploy", "mechanism": "m", "confidence": 0.9,
                            "supporting_evidence": [{"evidence_id": "dep-x"}]}],
            "final_status": "ROOT_CAUSE_IDENTIFIED", "executive_summary": "s", "corrective_actions": ["rollback"],
            "preventive_actions": ["tests"], "monitoring_recommendations": ["alerts"], "conclusion": "c"}))
    st = await run_single_agent(incident("INC-002"), StubProvider(overrides={"single_agent": fn}), fast_config())
    assert st.final_status == FinalStatus.ROOT_CAUSE_IDENTIFIED
    assert st.hypotheses[0].confidence == 0.9


async def test_baseline_respects_same_tool_budget():
    def fn(ctx):
        return resp(*[call("query_logs", {"service": "redis"}) for _ in range(5)])
    st = await run_single_agent(incident("INC-001"), StubProvider(overrides={"single_agent": fn}),
                                fast_config(max_tool_calls=7, max_agent_steps=2))
    assert st.stats.tool_calls == 7
    assert st.final_status == FinalStatus.INVESTIGATION_FAILED


async def test_baseline_failure_is_reported():
    from app.llm.provider import LLMError
    st = await run_single_agent(incident("INC-001"), StubProvider(overrides={"single_agent": lambda c: LLMError("x")}),
                                fast_config())
    assert st.final_status == FinalStatus.INVESTIGATION_FAILED and st.report
