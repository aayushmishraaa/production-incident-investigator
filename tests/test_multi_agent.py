"""Multi-agent system over every synthetic incident (stub LLM): always terminates with a report."""
from __future__ import annotations

import pytest

from app.evaluation.multi_agent import run_multi_agent
from app.llm.mock_provider import StubProvider
from app.models.investigation import FinalStatus
from app.tools.data_store import list_incident_reports
from tests.conftest import fast_config, incident

IDS = [r["incident_id"] for r in list_incident_reports()]


def test_dataset_has_at_least_ten_incidents():
    assert len(IDS) >= 10


@pytest.mark.parametrize("iid", IDS)
async def test_every_incident_completes(iid):
    st = await run_multi_agent(incident(iid), StubProvider(), fast_config())
    assert st.final_status != FinalStatus.RUNNING and st.report
    assert st.report["final_status"] in {s.value for s in FinalStatus}
    assert len({m.sender for m in st.messages}) >= 5     # >= 5 distinct agents actually communicated


async def test_agents_genuinely_collaborate():
    """Reasoning output depends on what specialists found: removing their findings changes the hypotheses."""
    full = await run_multi_agent(incident("INC-008"), StubProvider(), fast_config(max_rounds=1))
    from app.llm.provider import LLMError
    blind = await run_multi_agent(
        incident("INC-008"),
        StubProvider(overrides={"observability": lambda c: LLMError("x"), "dependency": lambda c: LLMError("x")}),
        fast_config(max_rounds=1, max_agent_retries=0))
    cats_full = {h.category.value for h in full.hypotheses}
    cats_blind = {h.category.value for h in blind.hypotheses}
    assert cats_blind == {"unknown"}          # without specialist findings nothing can be hypothesised
    assert "unknown" not in cats_full and len(cats_full) >= 2
