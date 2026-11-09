"""Each agent tested independently (stub LLM, real tools/state)."""
from __future__ import annotations

import pytest

from app.agents.base_agent import AgentOutputError
from app.agents.critic_agent import CriticAgent, hypotheses_for_critic, run_prechecks
from app.agents.dependency_agent import DependencyAgent
from app.agents.observability_agent import ObservabilityAgent
from app.agents.orchestrator import OrchestratorAgent
from app.agents.reasoning_agent import ReasoningAgent
from app.agents.reporting_agent import ReportingAgent, fallback_narrative
from app.llm.mock_provider import StubProvider
from app.models.agent import AgentName, FindingKind, InvestigationTask
from app.models.hypothesis import VerdictType
from app.models.investigation import FinalStatus
from tests.helpers import call, hyp, resp, script, submit_hyps, verdict

WIN = {"start": "2026-09-14T11:10:00Z", "end": "2026-09-14T12:05:00Z"}


def task(agent, services=("payment-service",)):
    return InvestigationTask(agent=agent, objective="test", services=list(services))


async def collect(rt):
    """Pre-populate evidence for INC-005 the way specialists would."""
    ex = rt.executor
    await ex.call("query_metrics", {"service": "postgres", "metrics": ["disk_io_wait_ms", "p95_latency_ms"], **WIN}, agent="t")
    await ex.call("query_metrics", {"service": "payment-service", "metrics": ["p95_latency_ms", "error_rate"], **WIN}, agent="t")
    await ex.call("get_deployments", {}, agent="t")
    await ex.call("query_logs", {"service": "postgres", "severity": ["WARN", "ERROR"]}, agent="t")
    ev = rt.state.evidence
    pg_io = next(k for k in ev if k.startswith("met-postgres-disk_io"))
    pay = next(k for k in ev if k.startswith("met-payment-service-p95"))
    dep = next(k for k in ev if k.startswith("dep-"))
    return pg_io, pay, dep


# ------------------------------------------------------------------ observability
async def test_observability_agent_collects_and_cites(runtime_factory):
    rt = runtime_factory("INC-001")
    out = await ObservabilityAgent(rt.llm, rt.executor, rt.state).run(task(AgentName.OBSERVABILITY))
    assert out.findings and rt.state.stats.tool_calls > 0
    facts = [f for f in out.findings if f.kind == FindingKind.OBSERVED_FACT]
    assert facts and all(e.evidence_id in rt.state.evidence for f in facts for e in f.evidence)
    assert {c.tool_name for c in rt.state.tool_calls} == {"query_logs", "query_metrics"}


async def test_specialist_rejects_hallucinated_evidence_then_accepts_fix(runtime_factory):
    good = {"kind": "observed_fact", "statement": "deploys listed", "evidence_ids": []}
    llm = StubProvider(overrides={"dependency": script(
        resp(call("get_deployments", {}))),
    })
    rt = runtime_factory("INC-002", llm=llm)

    def turn1(ctx):
        return resp(call("submit_findings", {"findings": [{"kind": "observed_fact", "statement": "x",
                                                           "evidence_ids": ["dep-FAKE123"]}], "summary": "s"}))

    def turn2(ctx):
        real = next(k for k in rt.state.evidence if k.startswith("dep-"))
        return resp(call("submit_findings", {"findings": [{**good, "evidence_ids": [real]}], "summary": "s"}))
    llm.overrides["dependency"] = script(resp(call("get_deployments", {})), turn1, turn2)
    out = await DependencyAgent(llm, rt.executor, rt.state).run(task(AgentName.DEPENDENCY, ["auth-service"]))
    assert rt.state.stats.invalid_llm_outputs == 1
    assert out.findings[0].evidence[0].evidence_id.startswith("dep-")


async def test_dependency_agent_reports_changes(runtime_factory):
    rt = runtime_factory("INC-007")
    out = await DependencyAgent(rt.llm, rt.executor, rt.state).run(task(AgentName.DEPENDENCY, ["order-service"]))
    assert any("timeout_ms" in f.statement for f in out.findings)
    assert {c.tool_name for c in rt.state.tool_calls} >= {"get_deployments", "get_config_changes"}


async def test_agent_cannot_use_tools_outside_its_role(runtime_factory):
    llm = StubProvider(overrides={"observability": script(
        resp(call("get_deployments", {})),
        resp(call("submit_findings", {"findings": [{"kind": "missing_evidence", "statement": "none"}], "summary": "s"})))})
    rt = runtime_factory(llm=llm)
    await ObservabilityAgent(llm, rt.executor, rt.state).run(task(AgentName.OBSERVABILITY))
    assert rt.state.stats.tool_calls == 0   # denied before reaching the executor


# ------------------------------------------------------------------ invalid LLM output
async def test_text_only_and_malformed_outputs_are_recovered(runtime_factory):
    llm = StubProvider(overrides={"observability": script(
        resp(text="I think it's the database."),                               # no tool call
        resp(call("submit_findings", {"findings": "not-a-list"})),             # schema violation
        resp(call("submit_findings", {"findings": [{"kind": "missing_evidence", "statement": "n/a"}], "summary": "ok"})))})
    rt = runtime_factory(llm=llm)
    out = await ObservabilityAgent(llm, rt.executor, rt.state).run(task(AgentName.OBSERVABILITY))
    assert out.summary == "ok" and rt.state.stats.invalid_llm_outputs == 2


async def test_persistently_invalid_agent_raises(runtime_factory):
    llm = StubProvider(overrides={"observability": lambda ctx: resp(text="no tools")})
    rt = runtime_factory(llm=llm)
    with pytest.raises(AgentOutputError):
        await ObservabilityAgent(llm, rt.executor, rt.state).run(task(AgentName.OBSERVABILITY))


# ------------------------------------------------------------------ reasoning
async def test_reasoning_agent_hypotheses_scored_transparently(runtime_factory):
    rt = runtime_factory("INC-005")
    pg_io, pay, dep = await collect(rt)
    llm = StubProvider(overrides={"reasoning": script(submit_hyps(
        hyp("H1", "infrastructure_degradation", "postgres", [pg_io, pay], cause_time="2026-09-14T11:21:00Z"),
        hyp("H2", "deployment_regression", "payment-service", [dep], contra=[pg_io], cause_time="2026-09-14T11:32:00Z")))})
    t = task(AgentName.REASONING)
    await ReasoningAgent(llm, rt.executor, rt.state).run(t, findings_msgs=[])
    h1, h2 = rt.state.hypotheses
    assert h1.confidence > h2.confidence
    assert any("AFTER the first observed anomaly" in e for e in h2.score.explanation)
    assert any("not a calibrated probability" in e for e in h1.score.explanation)


async def test_reasoning_reads_findings_from_messages(runtime_factory):
    seen = {}

    def capture(ctx):
        seen["briefing"] = ctx["messages"][0]["content"]
        return submit_hyps(hyp("H1", "unknown", None, []))
    rt = runtime_factory(llm=StubProvider(overrides={"reasoning": capture}))
    msgs = [{"sender": "observability", "payload": {"task_id": "t1", "round": 1, "summary": "pool at 99%",
                                                     "findings": [{"kind": "observed_fact", "statement": "POOL-SIGNAL",
                                                                   "evidence": []}]}}]
    await ReasoningAgent(rt.llm, rt.executor, rt.state).run(task(AgentName.REASONING), msgs)
    assert "POOL-SIGNAL" in seen["briefing"] and "from observability" in seen["briefing"]


# ------------------------------------------------------------------ critic
async def _two_hypotheses(rt, pg_io, pay, dep, fake=False):
    support = [pg_io, pay] + (["met-FAKE-evidence"] if fake else [])
    llm = StubProvider(overrides={"reasoning": script(submit_hyps(
        hyp("H1", "infrastructure_degradation", "postgres", support, cause_time="2026-09-14T11:21:00Z"),
        hyp("H2", "deployment_regression", "payment-service", [dep], cause_time="2026-09-14T11:32:00Z")))})
    await ReasoningAgent(llm, rt.executor, rt.state).run(task(AgentName.REASONING), [])


async def test_critic_prechecks_detect_hallucination_timing_and_correlation(runtime_factory):
    rt = runtime_factory("INC-005")
    pg_io, pay, dep = await collect(rt)
    await _two_hypotheses(rt, pg_io, pay, dep, fake=True)
    issues = run_prechecks(rt.state)
    checks = {(i.hypothesis_id, i.check) for i in issues if i.severity == "blocking"}
    assert ("H1", "citation_exists") in checks
    assert ("H2", "temporal_precedence") in checks
    assert ("H2", "correlation_only") in checks


async def test_critic_can_reject_and_blocks_unsafe_approval(runtime_factory):
    rt = runtime_factory("INC-005")
    pg_io, pay, dep = await collect(rt)
    await _two_hypotheses(rt, pg_io, pay, dep)
    # LLM critic tries to approve the deployment hypothesis (H2) and reject H1
    llm = StubProvider(overrides={"critic": script(verdict("APPROVED", [
        {"hypothesis_id": "H1", "decision": "reject", "reasoning": "x"},
        {"hypothesis_id": "H2", "decision": "accept", "reasoning": "deploy right before"}]))})
    v = await CriticAgent(llm, rt.executor, rt.state).run(task(AgentName.CRITIC), hypotheses_for_critic(rt.state))
    h1, h2 = (rt.state.hypotheses[0], rt.state.hypotheses[1])
    assert h1.status == "rejected"
    assert h2.status == "needs_evidence"            # acceptance overridden by blocking pre-check
    assert v.verdict != VerdictType.APPROVED          # cannot approve unsupported conclusion
    assert "overridden" in next(a.reasoning for a in v.assessments if a.hypothesis_id == "H2")


async def test_critic_is_blind_to_confidence(runtime_factory):
    rt = runtime_factory("INC-005")
    pg_io, pay, dep = await collect(rt)
    await _two_hypotheses(rt, pg_io, pay, dep)
    seen = {}

    def capture(ctx):
        seen["b"] = ctx["messages"][0]["content"]
        return verdict("INCONCLUSIVE")
    await CriticAgent(StubProvider(overrides={"critic": capture}), rt.executor, rt.state).run(
        task(AgentName.CRITIC), hypotheses_for_critic(rt.state))
    assert '"confidence"' not in seen["b"] and "score" not in seen["b"]
    assert "AUTOMATED PRE-CHECKS" in seen["b"]


async def test_critic_has_own_tool_access(runtime_factory):
    rt = runtime_factory("INC-005")
    pg_io, pay, dep = await collect(rt)
    await _two_hypotheses(rt, pg_io, pay, dep)
    before = rt.state.stats.tool_calls
    llm = StubProvider(overrides={"critic": script(
        resp(call("query_metrics", {"service": "order-service", "metrics": ["p95_latency_ms"], **WIN})),
        verdict("APPROVED", [{"hypothesis_id": "H1", "decision": "accept", "reasoning": "verified"},
                             {"hypothesis_id": "H2", "decision": "reject", "reasoning": "after onset"}]))})
    v = await CriticAgent(llm, rt.executor, rt.state).run(task(AgentName.CRITIC), hypotheses_for_critic(rt.state))
    assert rt.state.stats.tool_calls == before + 1
    assert any(c.agent == "critic" for c in rt.state.tool_calls)
    assert v.verdict == VerdictType.APPROVED and rt.state.top_hypothesis().hypothesis_id == "H1"


# ------------------------------------------------------------------ orchestrator
async def test_orchestrator_plan_validation_and_parallel_tasks(runtime_factory):
    llm = StubProvider(overrides={"orchestrator": script(
        resp(call("submit_plan", {"incident_summary": "x", "tasks": [
            {"agent": "observability", "objective": "a", "services": ["paymnt"]},
            {"agent": "dependency", "objective": "b", "services": []}]})),
        resp(call("submit_plan", {"incident_summary": "x", "tasks": [
            {"agent": "observability", "objective": "a", "services": ["payment-service", "postgres"]},
            {"agent": "dependency", "objective": "b", "services": ["payment-service"]}]})))})
    rt = runtime_factory(llm=llm)
    tasks = await OrchestratorAgent(llm, rt.executor, rt.state).plan()
    assert rt.state.stats.invalid_llm_outputs == 1
    assert {t.agent for t in tasks} == {AgentName.OBSERVABILITY, AgentName.DEPENDENCY}
    assert all(not t.depends_on for t in tasks)    # independent -> parallelisable


async def test_orchestrator_falls_back_to_default_plan(runtime_factory):
    llm = StubProvider(overrides={"orchestrator": lambda ctx: RuntimeError("LLM down")})
    rt = runtime_factory(llm=llm)
    tasks = await OrchestratorAgent(llm, rt.executor, rt.state).plan()
    assert len(tasks) == 2 and rt.state.plan.get("fallback")


def test_orchestrator_final_status_rules(runtime_factory):
    from app.models.hypothesis import CriticVerdict, Hypothesis
    rt = runtime_factory()
    orch = OrchestratorAgent(rt.llm, rt.executor, rt.state)
    s = rt.state
    s.hypotheses = [Hypothesis(hypothesis_id="H1", category="cache_degradation", description="d", confidence=0.8, status="supported"),
                    Hypothesis(hypothesis_id="H2", category="traffic_surge", description="d", confidence=0.3)]
    s.critic_verdicts = [CriticVerdict(verdict="APPROVED", summary="")]
    assert orch.decide_final_status() == FinalStatus.ROOT_CAUSE_IDENTIFIED
    s.hypotheses[0].confidence = 0.5
    assert orch.decide_final_status() == FinalStatus.PROBABLE_ROOT_CAUSE
    s.critic_verdicts = [CriticVerdict(verdict="INCONCLUSIVE", summary="")]
    assert orch.decide_final_status() == FinalStatus.INCONCLUSIVE
    s.critic_verdicts = []
    assert orch.decide_final_status() == FinalStatus.INCONCLUSIVE


# ------------------------------------------------------------------ reporting
async def test_reporting_agent_and_fallback(runtime_factory):
    rt = runtime_factory()
    validated = {"incident": {"title": "t"}, "final_status": "INCONCLUSIVE", "leading_hypothesis": None}
    n = await ReportingAgent(rt.llm, rt.executor, rt.state).run(task(AgentName.REPORTING), validated)
    assert n.corrective_actions
    fb = fallback_narrative(validated)
    assert "could not be conclusively established" in fb.executive_summary
