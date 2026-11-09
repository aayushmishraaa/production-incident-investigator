"""Metric calculations, report generation, persistence and API endpoints."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.evaluation.metrics import classification_metrics, confusion, correctness, run_record, summarize
from app.llm.mock_provider import StubProvider
from app.orchestration.workflow import run_investigation
from app.storage.repository import InvestigationRepository
from tests.conftest import fast_config, incident


def row(gt, pred, svc_ok=True, run=1, dur=1.0, tokens=None):
    return {"gt_category": gt, "predicted_category": pred, "diagnosed": pred != "inconclusive",
            "correct": gt == pred, "strict_correct": gt == pred and svc_ok, "behaviour_correct": gt == pred,
            "run": run, "duration_s": dur, "total_tokens": tokens, "input_tokens": tokens, "output_tokens": tokens,
            "cost_usd": 0.001 if tokens else None, "tokens_by_agent": None, "citation_validity": 1.0,
            "hallucinated_citations": 0, "top_citation_accuracy": 1.0, "unsupported_hypotheses": 0, "hypotheses": 2,
            "key_evidence_recall": 0.5, "decoy_handled": None, "hypotheses_with_contradictions": 1, "tool_calls": 10,
            "tool_failures": 0, "tool_retries": 0, "llm_calls": 5, "completeness_score": 0.8, "judge_score": None}


def test_correctness_rules():
    gt = {"root_cause_category": "cache_degradation", "culprit_service": "redis"}
    assert correctness("cache_degradation", "redis", gt) == {"correct": True, "strict_correct": True, "behaviour_correct": True}
    assert correctness("cache_degradation", "postgres", gt)["strict_correct"] is False
    assert correctness("inconclusive", None, gt)["correct"] is False          # inconclusive != correct diagnosis
    gt_inc = {"root_cause_category": "unknown", "culprit_service": None, "expected_inconclusive": True}
    assert correctness("inconclusive", None, gt_inc)["correct"] is True
    gt_acc = {"root_cause_category": "infrastructure_degradation", "culprit_service": "x", "acceptable_inconclusive": True}
    c = correctness("inconclusive", None, gt_acc)
    assert c["correct"] is False and c["behaviour_correct"] is True


def test_precision_recall_f1_and_confusion():
    rows = [row("a", "a"), row("a", "b"), row("b", "b"), row("b", "inconclusive")]
    m = classification_metrics(rows)
    assert m["per_class"]["a"]["precision"] == 1.0 and m["per_class"]["a"]["recall"] == 0.5
    assert m["per_class"]["b"]["precision"] == 0.5 and m["per_class"]["b"]["recall"] == 0.5
    assert m["macro_precision"] == 0.75
    c = confusion(rows)
    i = c["labels"].index
    assert c["matrix"][i("b")][i("inconclusive")] == 1


def test_summary_accuracy_coverage_latency():
    rows = [row("a", "a", dur=1), row("a", "inconclusive", dur=3), row("b", "a", dur=2), row("b", "b", run=2, dur=4)]
    s = summarize(rows)
    assert s["accuracy"] == 0.5 and s["coverage"] == 0.75 and s["accuracy_when_diagnosed"] == round(2 / 3, 4)
    assert s["inconclusive"] == 1 and s["incorrect"] == 1
    assert s["latency_median_s"] == 2.5 and s["latency_p95_s"] is None     # too few observations for P95
    assert s["tokens_available"] is False and s["tokens_total"] is None    # never fabricated


async def test_run_record_grounding_fields():
    from app.evaluation.ground_truth import load_ground_truth
    st = await run_investigation(incident("INC-007"), StubProvider(), fast_config())
    r = run_record(st, load_ground_truth("INC-007"), 1)
    assert r["tokens_available"] is False and r["total_tokens"] is None and r["cost_usd"] is None
    assert 0 <= r["completeness_score"] <= 1
    assert r["citation_validity"] in (None, 1.0) or 0 <= r["citation_validity"] <= 1
    assert r["key_evidence_recall"] is not None


async def test_evaluator_end_to_end_outputs(tmp_path):
    from app.evaluation.evaluator import Evaluator
    ev = Evaluator(provider="stub", runs=1, incidents=["INC-001", "INC-010"], out_dir=tmp_path / "eval", use_judge=False)
    res = await ev.run()
    assert set(res["summary"]) == {"multi_agent", "single_agent"}
    for f in ("evaluation_results.json", "evaluation_runs.csv", "summary_table.md", "runs.jsonl"):
        assert (tmp_path / "eval" / f).exists()
    assert res["conditions"]["token_note"]


async def test_persistence_roundtrip():
    st = await run_investigation(incident("INC-004"), StubProvider(), fast_config())
    repo = InvestigationRepository()
    repo.save(st)
    loaded = repo.get_state(st.investigation_id)
    assert loaded.final_status == st.final_status and len(loaded.evidence) == len(st.evidence)
    assert any(r["investigation_id"] == st.investigation_id for r in repo.list())


# ------------------------------------------------------------------ API
@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    from app.main import app
    return TestClient(app)


def test_api_health_and_incidents(client):
    assert client.get("/health").json()["status"] == "ok"
    inc = client.get("/incidents").json()
    assert len(inc) >= 10 and "root_cause_category" not in json.dumps(inc)


def test_api_investigate_flow(client):
    r = client.post("/investigate", json={"incident_id": "INC-002", "provider": "stub", "wait": True,
                                          "config": {"tool_timeout_s": 0.3}})
    assert r.status_code == 202
    inv = r.json()["investigation_id"]
    assert client.get(f"/investigations/{inv}").json()["state"]["incident"]["incident_id"] == "INC-002"
    rep = client.get(f"/investigations/{inv}/report").json()
    assert rep["final_status"] in ("ROOT_CAUSE_IDENTIFIED", "PROBABLE_ROOT_CAUSE", "INCONCLUSIVE", "INVESTIGATION_FAILED")
    assert client.get(f"/investigations/{inv}/evidence").json()["count"] > 0
    assert client.get(f"/investigations/{inv}/timeline").json()["investigation_timeline"]


def test_api_background_investigation_and_single_agent(client):
    r = client.post("/investigate", json={"incident_id": "INC-001", "provider": "stub", "config": {"tool_timeout_s": 0.3}})
    assert r.status_code == 202 and r.json()["status"] == "RUNNING"
    r2 = client.post("/investigate", json={"incident_id": "INC-001", "provider": "stub", "system": "single_agent"})
    assert r2.json()["system"] == "single_agent"


def test_api_validation_errors(client):
    assert client.post("/investigate", json={}).status_code == 422
    assert client.post("/investigate", json={"incident_id": "INC-999"}).status_code == 404
    assert client.post("/investigate", json={"incident_id": "INC-001", "config": {"max_rounds": 0}}).status_code == 422
    assert client.get("/investigations/inv-nope").status_code == 404


def test_api_evaluate_results_404_before_run(client):
    assert client.get("/evaluate/results").status_code == 404
