"""Factory for a fresh investigation runtime (state + tools + bus)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.llm.provider import LLMProvider
from app.models.incident import IncidentReport
from app.models.investigation import InvestigationConfig, InvestigationState
from app.orchestration.communication import MessageBus
from app.orchestration.task_manager import TaskManager
from app.tools import ToolExecutor, build_tools
from app.tools.data_store import OperationalDataStore
from app.tools.failure_simulator import FailureSimulator


@dataclass
class Runtime:
    state: InvestigationState
    llm: LLMProvider
    executor: ToolExecutor
    bus: MessageBus
    tasks: TaskManager


def create_runtime(incident: IncidentReport, llm: LLMProvider, config: Optional[InvestigationConfig] = None,
                   system: str = "multi_agent", environment_id: Optional[str] = None,
                   simulator: Optional[FailureSimulator] = None, store: Optional[OperationalDataStore] = None) -> Runtime:
    state = InvestigationState(incident=incident, config=config or InvestigationConfig(), system=system)
    state.stats.tokens_available = llm.tokens_available
    store = store or OperationalDataStore(environment_id or incident.incident_id)
    executor = ToolExecutor(state, store, build_tools(incident.symptom_start), simulator)
    bus = MessageBus(state)
    return Runtime(state=state, llm=llm, executor=executor, bus=bus, tasks=TaskManager(state, bus))
