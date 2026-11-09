"""Evidence reference validation, fact/assumption labelling and ground-truth isolation."""
from __future__ import annotations

import ast
import json
from pathlib import Path

from app.llm.mock_provider import StubProvider
from app.models.evidence import EvidenceLabel
from app.orchestration.workflow import run_investigation
from tests.conftest import fast_config, incident

APP = Path(__file__).resolve().parent.parent / "app"


async def test_every_reported_citation_is_traceable():
    st = await run_investigation(incident("INC-007"), StubProvider(), fast_config())
    for h in st.report["hypotheses"]:
        for e in h["supporting_evidence"] + h["contradicting_evidence"]:
            assert e["exists"] == (e["evidence_id"] in st.evidence)
    for eid, rec in st.evidence.items():
        assert rec.collected_by and rec.tool_call_id      # provenance: which agent/tool call produced it
        assert any(eid in c.evidence_ids for c in st.tool_calls if c.call_id == rec.tool_call_id)


async def test_hallucinated_citation_flagged_in_report():
    from tests.helpers import hyp, submit_hyps
    llm = StubProvider(overrides={"reasoning": lambda ctx: submit_hyps(
        hyp("H1", "cache_degradation", "redis", ["met-redis-made-up"]))})
    st = await run_investigation(incident("INC-008"), llm, fast_config(max_rounds=1))
    h = st.report["hypotheses"][0]
    assert h["supporting_evidence"][0]["exists"] is False
    assert h["supporting_evidence"][0]["label"] == EvidenceLabel.UNKNOWN.value
    assert any(i["check"] == "citation_exists" for i in st.report["critic_review"]["precheck_issues"])
    assert st.final_status.value == "INCONCLUSIVE"


async def test_report_labels_facts_inferences_and_unknowns():
    st = await run_investigation(incident("INC-002"), StubProvider(), fast_config())
    labels = {s["label"] for s in st.report["observed_symptoms"]} | {e["label"] for e in st.report["timeline"]}
    assert EvidenceLabel.CONFIRMED_FACT.value in labels and EvidenceLabel.OBSERVED_EVIDENCE.value in labels
    md = (APP.parent / "results").exists()  # noqa: F841
    from app.models.report import InvestigationReport
    from app.reporting.report_generator import to_markdown
    text = to_markdown(InvestigationReport.model_validate(st.report))
    for needed in ("INFERENCE", "CONFIRMED FACT", "Critic Review", "Corrective Actions", "Preventive Actions",
                   "Monitoring Recommendations", "Limitations", "Final Status", "Incident Timeline"):
        assert needed in text


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module)
        elif isinstance(node, ast.Import):
            mods |= {a.name for a in node.names}
    return mods


def test_ground_truth_isolation_static():
    """No agent/tool/orchestration/llm/reporting module imports the ground-truth loader or mentions its directory."""
    for sub in ("agents", "tools", "orchestration", "llm", "reporting", "models"):
        for py in (APP / sub).glob("*.py"):
            assert "app.evaluation.ground_truth" not in _imports(py), py
            src = py.read_text()
            if py.name != "data_store.py":           # data_store only names it to REFUSE access
                assert "ground_truth" not in src, py


async def test_ground_truth_isolation_runtime(monkeypatch):
    """Instrument file reads during a full investigation: ground truth is never opened."""
    opened = []
    real_read_text = Path.read_text

    def spy(self, *a, **k):
        opened.append(str(self))
        return real_read_text(self, *a, **k)
    monkeypatch.setattr(Path, "read_text", spy)
    st = await run_investigation(incident("INC-005"), StubProvider(), fast_config())
    assert opened and not any("ground_truth" in p for p in opened)
    gt = json.loads(real_read_text(APP.parent / "data" / "ground_truth" / "INC-005.json"))
    blob = st.model_dump_json()
    assert gt["description"] not in blob and "root_cause_category" not in blob


def test_agent_prompts_contain_no_incident_answers():
    gts = [json.loads(p.read_text()) for p in (APP.parent / "data" / "ground_truth").glob("*.json")]
    prompts = ""
    for mod in ("orchestrator", "observability_agent", "dependency_agent", "reasoning_agent", "critic_agent", "reporting_agent"):
        prompts += (APP / "agents" / f"{mod}.py").read_text()
    prompts += (APP / "evaluation" / "single_agent.py").read_text()
    for gt in gts:
        assert gt["incident_id"] not in prompts
        assert gt["description"] not in prompts
        for eid in gt["key_evidence_ids"]:
            assert eid not in prompts
