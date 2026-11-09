"""Bounded retry / failure recovery for agent tasks."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Optional

from app.agents.base_agent import BudgetStop
from app.llm.provider import BudgetExceededError
from app.models.agent import InvestigationTask, TaskStatus
from app.models.investigation import InvestigationState

logger = logging.getLogger("recovery")

NON_RETRYABLE = (BudgetStop, BudgetExceededError)


async def run_task_with_recovery(state: InvestigationState, task: InvestigationTask,
                                 fn: Callable[[InvestigationTask], Awaitable[Any]]) -> Optional[Any]:
    """Run an agent task with up to config.max_agent_retries retries.

    Returns the result, or None if the task ultimately failed (failure recorded in state).
    Budget exhaustion is re-raised so the workflow can terminate gracefully.
    """
    max_attempts = 1 + state.config.max_agent_retries
    task.status = TaskStatus.RUNNING
    task.started_at = datetime.now(timezone.utc)
    state.log(task.agent.value, "task_started", task_id=task.task_id, objective=task.objective[:120])
    while task.attempts < max_attempts:
        task.attempts += 1
        try:
            result = await fn(task)
            task.status = TaskStatus.COMPLETED
            task.finished_at = datetime.now(timezone.utc)
            state.log(task.agent.value, "task_completed", task_id=task.task_id, attempts=task.attempts)
            return result
        except NON_RETRYABLE as e:
            task.status, task.error = TaskStatus.FAILED, repr(e)
            task.finished_at = datetime.now(timezone.utc)
            state.log(task.agent.value, "task_budget_stop", task_id=task.task_id, error=repr(e))
            raise
        except Exception as e:  # noqa: BLE001 - any agent crash is recoverable at this level
            state.stats.agent_failures += 1
            task.error = repr(e)
            state.errors.append(f"{task.agent.value} task {task.task_id} attempt {task.attempts} failed: {e!r}")
            state.log(task.agent.value, "task_failed_attempt", task_id=task.task_id, attempt=task.attempts, error=repr(e)[:300])
            logger.warning("agent %s task %s attempt %d failed: %r", task.agent.value, task.task_id, task.attempts, e)
            if task.attempts < max_attempts:
                state.stats.agent_retries += 1
                await asyncio.sleep(0.1)
    task.status = TaskStatus.FAILED
    task.finished_at = datetime.now(timezone.utc)
    return None
