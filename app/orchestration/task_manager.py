"""Investigation task DAG: registration, dependency resolution and parallel waves."""
from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Iterable, Optional

from app.models.agent import AgentName, InvestigationTask, MessageType, TaskStatus
from app.models.investigation import InvestigationState
from app.orchestration.communication import MessageBus
from app.orchestration.recovery import run_task_with_recovery

DONE = {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.SKIPPED}


class TaskManager:
    def __init__(self, state: InvestigationState, bus: MessageBus):
        self.state = state
        self.bus = bus

    def add(self, tasks: Iterable[InvestigationTask]) -> list[InvestigationTask]:
        added = []
        for t in tasks:
            self.state.tasks.append(t)
            added.append(t)
            self.bus.send(AgentName.ORCHESTRATOR, t.agent, MessageType.TASK_ASSIGNMENT,
                          {"task_id": t.task_id, "objective": t.objective, "services": t.services,
                           "focus": t.focus, "round": t.round, "depends_on": t.depends_on})
        return added

    def deps_satisfied(self, task: InvestigationTask) -> bool:
        # failed dependencies do not block: downstream agents continue with available evidence
        return all(self.state.task(d).status in DONE for d in task.depends_on)

    def ready(self, agents: Optional[set[AgentName]] = None) -> list[InvestigationTask]:
        return [t for t in self.state.tasks if t.status == TaskStatus.PENDING and self.deps_satisfied(t)
                and (agents is None or t.agent in agents)]

    def ids(self, agents: set[AgentName], round_: int) -> list[str]:
        return [t.task_id for t in self.state.tasks if t.agent in agents and t.round == round_]

    async def run_wave(self, tasks: list[InvestigationTask],
                       runner: Callable[[InvestigationTask], Awaitable[Any]]) -> list[Optional[Any]]:
        """Run independent tasks concurrently (bounded by config.parallelism)."""
        sem = asyncio.Semaphore(self.state.config.parallelism)

        async def one(t: InvestigationTask) -> Optional[Any]:
            async with sem:
                return await run_task_with_recovery(self.state, t, runner)

        self.state.log("orchestrator", "wave_started", tasks=[t.task_id for t in tasks])
        results = await asyncio.gather(*(one(t) for t in tasks), return_exceptions=True)
        out = []
        for t, r in zip(tasks, results):
            if isinstance(r, BaseException):
                # budget stop inside one branch: keep others' results, propagate after collecting
                out.append(r)
            else:
                out.append(r)
        return out
