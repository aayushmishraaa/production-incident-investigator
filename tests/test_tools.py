"""Every operational tool: structured I/O, validation, errors, timeouts, partial data."""
from __future__ import annotations

import asyncio
import time

import pytest

from app.models.evidence import Reliability
from app.models.tool import ToolErrorCode
from app.tools.data_store import OperationalDataStore
from app.tools.failure_simulator import FailureSimulator

W = {"start": "2026-09-02T13:30:00Z", "end": "2026-09-02T14:25:00Z"}


async def test_log_tool_filters_and_patterns(runtime_factory):
    rt = runtime_factory("INC-001")
    r = await rt.executor.call("query_logs", {"service": "payment-service", "severity": ["ERROR"],
                                              "keyword": "acquiring connection"}, agent="test")
    assert r.success and not r.is_partial
    summary, patterns = r.data[0], [d for d in r.data if d["type"] == "pattern"]
    assert summary["total_matched"] >= 20 and len(patterns) == 1
    assert all(d["service"] == "payment-service" for d in r.data if d["type"] == "record")
    assert patterns[0]["evidence_id"] in rt.state.evidence


async def test_log_tool_time_range(runtime_factory):
    rt = runtime_factory("INC-001")
    r = await rt.executor.call("query_logs", {"start": "2026-09-02T13:59:00Z", "end": "2026-09-02T14:00:00Z"}, agent="t")
    assert all("2026-09-02T13:59" in d["timestamp"] or d["timestamp"] == "2026-09-02T14:00:00Z"
               for d in r.data if d["type"] == "record")


async def test_metrics_tool_baseline_comparison_and_onset(runtime_factory):
    rt = runtime_factory("INC-005")
    r = await rt.executor.call("query_metrics", {"service": "postgres", "metrics": ["disk_io_wait_ms", "cpu_pct"],
                                                 "start": "2026-09-14T11:10:00Z", "end": "2026-09-14T11:55:00Z"}, agent="t")
    io, cpu = r.data
    assert io["change_pct"] > 1000 and io["onset"].startswith("2026-09-14T11:2")
    assert cpu["onset"] is None
    rec = rt.state.evidence[io["evidence_id"]]
    assert rec.value["onset"] == io["onset"] and rec.reliability == Reliability.HIGH


async def test_metrics_tool_explicit_baseline_and_missing_data(runtime_factory):
    rt = runtime_factory("INC-006")
    r = await rt.executor.call("query_metrics", {"service": "postgres", "metrics": ["db_conn_util_pct"],
                                                 "start": "2026-09-17T20:50:00Z", "end": "2026-09-17T21:20:00Z",
                                                 "baseline_start": "2026-09-17T20:10:00Z",
                                                 "baseline_end": "2026-09-17T20:40:00Z"}, agent="t")
    row = r.data[0]
    assert row["missing_points"] > 10 and "missing" in row["note"]
    assert rt.state.evidence[row["evidence_id"]].reliability == Reliability.LOW


@pytest.mark.parametrize("args", [
    {"service": "payment-service", "metrics": ["bogus"], **W},
    {"service": "payment-service", "metrics": ["cpu_pct"], "start": W["end"], "end": W["start"]},
    {"service": "nope", "metrics": ["cpu_pct"], **W},
    {"service": "payment-service", "metrics": ["cpu_pct"], "baseline_start": W["start"], **W},
])
async def test_metrics_tool_invalid_queries(runtime_factory, args):
    rt = runtime_factory()
    r = await rt.executor.call("query_metrics", args, agent="t")
    assert not r.success and r.error.code == ToolErrorCode.INVALID_QUERY and r.attempts <= 1


async def test_deployment_tool(runtime_factory):
    rt = runtime_factory("INC-002")
    r = await rt.executor.call("get_deployments", {"service": "auth-service"}, agent="t")
    assert r.success and r.data[0]["to_version"] == "2.14.0"
    assert r.data[0]["deployment_id"] in rt.state.evidence


async def test_configuration_tool_diff(runtime_factory):
    rt = runtime_factory("INC-007")
    r = await rt.executor.call("get_config_changes", {"key": "timeout"}, agent="t")
    d = r.data[0]
    assert d["diff"]["before"] == "3000" and d["diff"]["after"] == "300"
    assert d["diff"]["numeric_ratio_after_over_before"] == 0.1


async def test_dependency_tool_up_and_downstream(runtime_factory):
    rt = runtime_factory("INC-003")
    r = await rt.executor.call("get_service_dependencies", {"service": "payment-service", "depth": 2}, agent="t")
    d = r.data[0]
    assert "auth-service" in d["upstream_dependencies"]
    assert "api-gateway" in d["downstream_dependents"]
    assert any("auth-service" in c for c in d["upstream_chains"])


async def test_dependency_tool_topology_changes(runtime_factory):
    rt = runtime_factory("INC-008")  # after topology-v2 effective date
    r = await rt.executor.call("get_service_dependencies", {"service": "order-service"}, agent="t")
    assert any(c.get("added_edge") == "order-service -> redis" for c in r.data[0]["topology_changes"])
    assert "redis" in r.data[0]["upstream_dependencies"]


async def test_historical_tool_similarity(runtime_factory):
    rt = runtime_factory()
    r = await rt.executor.call("search_historical_incidents",
                               {"symptoms": ["cache hit rate drop", "evictions"], "services": ["redis"]}, agent="t")
    assert r.data[0]["id"] == "HIST-2025-061"
    assert rt.state.evidence[r.data[0]["evidence_id"]].reliability == Reliability.LOW
    assert any("analogies" in w for w in r.warnings)


async def test_historical_tool_rejects_empty_symptoms(runtime_factory):
    rt = runtime_factory()
    r = await rt.executor.call("search_historical_incidents", {"symptoms": ["  "]}, agent="t")
    assert r.error.code == ToolErrorCode.INVALID_QUERY


async def test_unknown_tool(runtime_factory):
    r = await runtime_factory().executor.call("drop_database", {}, agent="t")
    assert r.error.code == ToolErrorCode.INVALID_QUERY


async def test_tool_timeout_is_real_and_retried(runtime_factory):
    rt = runtime_factory(max_tool_retries=2)
    rt.executor.simulator = FailureSimulator({"query_logs": {"fail_first_n": 2, "error": "TOOL_TIMEOUT"}},
                                             timeout_s=0.3)
    t0 = time.perf_counter()
    r = await rt.executor.call("query_logs", {"service": "payment-service"}, agent="t")
    assert r.success and r.attempts == 3
    assert time.perf_counter() - t0 >= 0.6       # two genuine timeouts happened
    assert rt.state.stats.tool_retries == 2 and rt.state.stats.tool_failures == 2


async def test_tool_retry_exhaustion_returns_structured_error(runtime_factory):
    rt = runtime_factory(max_tool_retries=1)
    rt.executor.simulator = FailureSimulator({"get_deployments": {"fail_first_n": 5, "error": "SERVICE_UNAVAILABLE"}})
    r = await rt.executor.call("get_deployments", {}, agent="t")
    assert not r.success and r.error.code == ToolErrorCode.SERVICE_UNAVAILABLE and r.attempts == 2
    payload = r.to_llm_payload()
    assert "NOT evidence" in payload["note"]
    assert any(g.reason == "SERVICE_UNAVAILABLE" for g in rt.state.evidence_gaps)


async def test_partial_results_flagged_and_downgraded(runtime_factory):
    rt = runtime_factory("INC-009")
    r = await rt.executor.call("query_logs", {"service": "user-service", "severity": ["ERROR"]}, agent="t")
    assert r.success and r.is_partial
    assert all(rt.state.evidence[e].reliability == Reliability.LOW for e in r.evidence_ids)
    assert any(g.reason == "PARTIAL_DATA" for g in rt.state.evidence_gaps)
    assert "INCOMPLETE" in r.to_llm_payload()["note"]


async def test_internal_tool_error_is_caught(runtime_factory, monkeypatch):
    rt = runtime_factory(max_tool_retries=0)
    tool = rt.executor.tools["get_deployments"]
    monkeypatch.setattr(tool, "execute", lambda *a, **k: 1 / 0)
    r = await rt.executor.call("get_deployments", {}, agent="t")
    assert r.error.code == ToolErrorCode.INTERNAL_TOOL_ERROR


async def test_tool_call_budget_enforced(runtime_factory):
    rt = runtime_factory(max_tool_calls=2)
    for _ in range(2):
        assert (await rt.executor.call("get_deployments", {}, agent="t")).success
    r = await rt.executor.call("get_deployments", {}, agent="t")
    assert r.error.code == ToolErrorCode.BUDGET_EXHAUSTED and rt.state.stats.tool_calls == 2


async def test_independent_tools_execute_concurrently(runtime_factory):
    rt = runtime_factory()
    orig = rt.executor._run

    async def slow(tool, inp):
        await asyncio.sleep(0.2)
        return await orig(tool, inp)
    rt.executor._run = slow
    t0 = time.perf_counter()
    rs = await asyncio.gather(*(rt.executor.call(n, a, agent="t") for n, a in [
        ("get_deployments", {}), ("get_config_changes", {}), ("query_logs", {"service": "redis"}),
        ("get_service_dependencies", {"service": "redis"})]))
    assert all(r.success for r in rs)
    assert time.perf_counter() - t0 < 0.6     # 4 x 0.2s sequential would be >= 0.8s


def test_random_failure_rate_is_seeded():
    a = FailureSimulator(random_failure_rate=0.5, seed=1)
    b = FailureSimulator(random_failure_rate=0.5, seed=1)
    assert [a.rng.random() for _ in range(5)] == [b.rng.random() for _ in range(5)]


def test_data_store_refuses_ground_truth():
    store = OperationalDataStore("INC-001")
    with pytest.raises(PermissionError):
        store._json("ground_truth", "INC-001.json")
    with pytest.raises(PermissionError):
        store._json("logs", "..", "ground_truth", "INC-001.json")
