"""Workflow: structured messages, shared state, parallel waves, DAG deps, critic loop, limits."""
from __future__ import annotations

import asyncio
import time

from app.llm.mock_provider import StubProvider
from app.models.agent import AgentName, InvestigationTask, MessageType, TaskStatus
from app.models.investigation import FinalStatus
from app.orchestration.workflow import run_investigation
from tests.conftest import fast_config, incident
from tests.helpers import hyp, resp, call, script, submit_hyps, verdict


async def test_messages_are_structured_and_flow_between_agents():
    st = await run_investigation(incident("INC-001"), StubProvider(), fast_config())
    flows = {(m.sender.value, m.recipient.value, m.message_type.value) for m in st.messages}
    assert ("orchestrator", "observability", "task_assignment") in flows
    assert ("observability", "orchestrator", "findings") in flows
    assert ("dependency", "orchestrator", "findings") in flows
    assert ("orchestrator", "reasoning", "findings") in flows
    assert ("reasoning", "critic", "hypotheses") in flows
    assert ("critic", "orchestrator", "critic_verdict") in flows
    assert ("orchestrator", "reporting", "report") in flows
    assert all(m.investigation_id == st.investigation_id and m.payload is not None for m in st.messages)


async def test_shared_state_tracks_everything():
    st = await run_investigation(incident("INC-002"), StubProvider(), fast_config())
    assert st.evidence and st.findings and st.hypotheses and st.critic_verdicts and st.timeline
    assert st.agent_status["observability"].value == "completed"
    assert {t.agent for t in st.tasks} == set(AgentName) - {AgentName.SINGLE_AGENT, AgentName.ORCHESTRATOR}
    assert any(m.sender == AgentName.ORCHESTRATOR for m in st.messages)
    assert st.report and st.final_status != FinalStatus.RUNNING
    assert st.stats.duration_s > 0 and st.stats.termination_reason


async def test_task_dependencies_form_dag():
    st = await run_investigation(incident("INC-001"), StubProvider(), fast_config())
    reasoning = next(t for t in st.tasks if t.agent == AgentName.REASONING)
    critic = next(t for t in st.tasks if t.agent == AgentName.CRITIC)
    evidence = [t.task_id for t in st.tasks if t.agent in (AgentName.OBSERVABILITY, AgentName.DEPENDENCY) and t.round == 1]
    assert set(reasoning.depends_on) == set(evidence)
    assert critic.depends_on == [reasoning.task_id]
    # reasoning only started after all of its dependencies finished
    for dep in evidence:
        assert st.task(dep).finished_at <= reasoning.started_at


async def test_independent_agents_run_in_parallel():
    llm = StubProvider(latency_s=0.15)
    st = await run_investigation(incident("INC-001"), llm, fast_config())
    obs = next(t for t in st.tasks if t.agent == AgentName.OBSERVABILITY)
    dep = next(t for t in st.tasks if t.agent == AgentName.DEPENDENCY)
    # time windows overlap -> concurrent execution
    assert obs.started_at < dep.finished_at and dep.started_at < obs.finished_at


def _critic_needs_more_then_approve(st_holder):
    def fn(ctx):
        rnd = 1 if "round 1 of" in ctx["messages"][0]["content"] else 2
        if rnd == 1:
            return verdict("NEEDS_MORE_EVIDENCE", requests=[{"target_agent": "observability",
                                                             "request": "check postgres metrics", "services": ["postgres"]}])
        return None  # default stub critic for round 2
    return fn


async def test_critic_feedback_loop_triggers_followup_round():
    llm = StubProvider(overrides={"critic": _critic_needs_more_then_approve({})})
    st = await run_investigation(incident("INC-001"), llm, fast_config())
    assert st.round == 2
    followups = [t for t in st.tasks if t.created_by == AgentName.CRITIC]
    assert followups and followups[0].agent == AgentName.OBSERVABILITY and followups[0].services == ["postgres"]
    assert followups[0].status == TaskStatus.COMPLETED
    assert len([t for t in st.tasks if t.agent == AgentName.REASONING]) == 2   # reasoning reconsidered
    assert len(st.critic_verdicts) == 2                                         # critic re-reviewed
    req_msgs = [m for m in st.messages if m.message_type == MessageType.EVIDENCE_REQUEST]
    assert req_msgs and req_msgs[0].sender == AgentName.CRITIC
    # round-2 reasoning received the critic's feedback
    assert any(m.recipient == AgentName.REASONING and m.message_type == MessageType.CRITIC_VERDICT for m in st.messages)


async def test_max_rounds_bounds_the_loop():
    llm = StubProvider(overrides={"critic": lambda ctx: verdict("NEEDS_MORE_EVIDENCE", requests=[
        {"target_agent": "dependency", "request": f"more {ctx['turn']}", "services": []}])})
    st = await run_investigation(incident("INC-001"), llm, fast_config(max_rounds=2))
    assert st.round == 2 and len(st.critic_verdicts) == 2
    assert "maximum investigation rounds" in st.stats.termination_reason
    assert st.final_status in (FinalStatus.INCONCLUSIVE, FinalStatus.PROBABLE_ROOT_CAUSE)


async def test_tool_budget_limit_terminates():
    llm = StubProvider(overrides={"critic": lambda ctx: verdict("NEEDS_MORE_EVIDENCE", requests=[
        {"target_agent": "observability", "request": "again", "services": ["redis"]}])})
    st = await run_investigation(incident("INC-001"), llm, fast_config(max_tool_calls=9, max_rounds=5))
    assert st.stats.tool_calls <= 9
    assert st.report is not None


async def test_llm_call_budget_stops_gracefully():
    st = await run_investigation(incident("INC-001"), StubProvider(), fast_config(max_llm_calls=3))
    assert st.report is not None and "budget" in st.stats.termination_reason
    assert st.final_status in (FinalStatus.INCONCLUSIVE, FinalStatus.INVESTIGATION_FAILED)


async def test_investigation_timeout_produces_report():
    st = await run_investigation(incident("INC-001"), StubProvider(latency_s=0.3), fast_config(investigation_timeout_s=0.5))
    assert "timeout" in st.stats.termination_reason
    assert st.report is not None and st.final_status != FinalStatus.RUNNING


async def test_approved_well_supported_conclusion_is_identified(runtime_factory):
    """Collaboration path to ROOT_CAUSE_IDENTIFIED with real evidence ids gathered by specialists."""
    def reasoning(ctx):
        text = ctx["messages"][0]["content"]
        import re
        ids = re.findall(r"^\s+(met-payment-service-db_conn_util_pct\S*|logpat-payment-service-\S+) \|", text, re.M)
        return submit_hyps(hyp("H1", "db_connection_pool_exhaustion", "payment-service", ids[:4],
                               cause_time="2026-09-02T13:45:00Z"),
                           hyp("H2", "deployment_regression", "notification-service", [], cause_time="2026-09-02T13:54:00Z"))
    llm = StubProvider(overrides={"reasoning": reasoning})
    st = await run_investigation(incident("INC-001"), llm, fast_config())
    top = st.top_hypothesis()
    assert top.category.value == "db_connection_pool_exhaustion"
    assert st.final_status in (FinalStatus.ROOT_CAUSE_IDENTIFIED, FinalStatus.PROBABLE_ROOT_CAUSE)
