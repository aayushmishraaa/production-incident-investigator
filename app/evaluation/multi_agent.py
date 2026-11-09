"""Multi-agent system entry point used by the evaluator (thin wrapper for symmetry)."""
from __future__ import annotations

from typing import Optional

from app.llm.provider import LLMProvider
from app.models.incident import IncidentReport
from app.models.investigation import InvestigationConfig, InvestigationState
from app.orchestration.workflow import run_investigation


async def run_multi_agent(incident: IncidentReport, llm: LLMProvider,
                          config: Optional[InvestigationConfig] = None) -> InvestigationState:
    return await run_investigation(incident, llm, config)
