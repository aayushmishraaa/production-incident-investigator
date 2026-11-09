from __future__ import annotations

import os

os.environ.setdefault("LLM_PROVIDER", "stub")

import pytest  # noqa: E402

from app.llm.mock_provider import StubProvider  # noqa: E402
from app.models.incident import IncidentReport  # noqa: E402
from app.models.investigation import InvestigationConfig  # noqa: E402
from app.orchestration.state import create_runtime  # noqa: E402
from app.tools.data_store import load_incident_report  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_results(tmp_path, monkeypatch):
    """Keep test artefacts (db, ledger, reports) out of the real results/ directory."""
    monkeypatch.setenv("RESULTS_DIR", str(tmp_path / "results"))
    monkeypatch.setenv("DB_PATH", str(tmp_path / "results" / "test.db"))
    yield


def incident(iid: str = "INC-001") -> IncidentReport:
    return IncidentReport(**load_incident_report(iid))


def fast_config(**kw) -> InvestigationConfig:
    base = dict(tool_timeout_s=0.3, max_rounds=3, max_tool_calls=60, investigation_timeout_s=60)
    base.update(kw)
    return InvestigationConfig(**base)


@pytest.fixture
def runtime_factory():
    def make(iid: str = "INC-001", llm=None, **cfg):
        return create_runtime(incident(iid), llm or StubProvider(), fast_config(**cfg))
    return make
