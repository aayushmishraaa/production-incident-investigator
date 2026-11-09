"""Tool base class and the ToolExecutor that every agent goes through.

The executor provides: input validation, a shared tool-call budget, per-call
timeouts, bounded retries with backoff for retryable errors, fault injection,
evidence registration into shared state, and structured logging.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, ClassVar, Optional

from pydantic import BaseModel, ValidationError

from app.models.evidence import EvidenceGap, EvidenceRecord, Reliability
from app.models.investigation import InvestigationState, ToolCallRecord
from app.models.tool import RETRYABLE_ERRORS, ToolError, ToolErrorCode, ToolResult
from app.tools.data_store import OperationalDataStore
from app.tools.failure_simulator import FailureSimulator, SimulatedToolFailure

logger = logging.getLogger("tools")

PartialFn = Callable[[list[dict[str, Any]]], tuple[list[dict[str, Any]], bool]]


@dataclass
class ToolOutput:
    data: list[dict[str, Any]]
    evidence: list[EvidenceRecord] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    is_partial: bool = False


class BaseTool(ABC):
    name: ClassVar[str]
    description: ClassVar[str]
    input_model: ClassVar[type[BaseModel]]

    @abstractmethod
    def execute(self, inp: BaseModel, store: OperationalDataStore, partial: PartialFn) -> ToolOutput:
        ...

    def schema(self) -> dict[str, Any]:
        schema = self.input_model.model_json_schema()
        schema.pop("title", None)
        return {"name": self.name, "description": self.description, "input_schema": schema}


class ToolExecutor:
    """Shared by all agents of one investigation (so the budget is global)."""

    def __init__(self, state: InvestigationState, store: OperationalDataStore, tools: list[BaseTool],
                 simulator: Optional[FailureSimulator] = None):
        self.state = state
        self.store = store
        self.tools = {t.name: t for t in tools}
        cfg = state.config
        self.simulator = simulator or FailureSimulator(
            store.failure_profile, cfg.random_failure_rate, cfg.seed, cfg.tool_timeout_s)
        self._lock = asyncio.Lock()

    def schemas(self, names: list[str]) -> list[dict[str, Any]]:
        return [self.tools[n].schema() for n in names if n in self.tools]

    async def _reserve_call(self) -> bool:
        async with self._lock:
            if self.state.stats.tool_calls >= self.state.config.max_tool_calls:
                return False
            self.state.stats.tool_calls += 1
            return True

    async def call(self, tool_name: str, arguments: dict[str, Any], *, agent: str,
                   task_id: Optional[str] = None) -> ToolResult:
        start = time.perf_counter()
        call_id = f"call-{uuid.uuid4().hex[:8]}"
        tool = self.tools.get(tool_name)
        if tool is None:
            return self._finish(call_id, tool_name, agent, task_id, arguments, start, 0,
                                error=ToolError(code=ToolErrorCode.INVALID_QUERY, message=f"unknown tool {tool_name}"))
        try:
            inp = tool.input_model.model_validate(arguments)
        except ValidationError as e:
            msg = "; ".join(f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors()[:5])
            return self._finish(call_id, tool_name, agent, task_id, arguments, start, 0,
                                error=ToolError(code=ToolErrorCode.INVALID_QUERY, message=msg))

        cfg = self.state.config
        attempts = 0
        last_error: Optional[ToolError] = None
        while attempts <= cfg.max_tool_retries:
            if not await self._reserve_call():
                last_error = ToolError(code=ToolErrorCode.BUDGET_EXHAUSTED,
                                       message="investigation tool-call budget exhausted")
                break
            attempts += 1
            if attempts > 1:
                self.state.stats.tool_retries += 1
            try:
                output = await asyncio.wait_for(self._run(tool, inp), timeout=cfg.tool_timeout_s)
                return self._finish(call_id, tool_name, agent, task_id, arguments, start, attempts, output=output)
            except asyncio.TimeoutError:
                last_error = ToolError(code=ToolErrorCode.TOOL_TIMEOUT, retryable=True,
                                       message=f"{tool_name} exceeded {cfg.tool_timeout_s}s")
            except SimulatedToolFailure as e:
                last_error = ToolError(code=e.code, message=str(e), retryable=e.code in RETRYABLE_ERRORS)
            except ValueError as e:
                last_error = ToolError(code=ToolErrorCode.INVALID_QUERY, message=str(e))
            except Exception as e:  # noqa: BLE001 - tool bugs must not crash agents
                logger.exception("tool %s crashed", tool_name)
                last_error = ToolError(code=ToolErrorCode.INTERNAL_TOOL_ERROR, message=repr(e), retryable=True)
            self.state.stats.tool_failures += 1
            logger.warning("tool %s attempt %d failed: %s", tool_name, attempts, last_error.code.value)
            if not last_error.retryable:
                break
            await asyncio.sleep(0.05 * (2 ** (attempts - 1)))
        return self._finish(call_id, tool_name, agent, task_id, arguments, start, attempts, error=last_error)

    async def _run(self, tool: BaseTool, inp: BaseModel) -> ToolOutput:
        await self.simulator.before_call(tool.name)
        await asyncio.sleep(0.01)  # yield; emulates I/O so concurrent calls interleave
        return tool.execute(inp, self.store, lambda d: self.simulator.apply_partial(tool.name, d))

    def _finish(self, call_id: str, tool_name: str, agent: str, task_id: Optional[str],
                arguments: dict[str, Any], start: float, attempts: int,
                output: Optional[ToolOutput] = None, error: Optional[ToolError] = None) -> ToolResult:
        elapsed = (time.perf_counter() - start) * 1000
        ev_ids: list[str] = []
        if output is not None:
            for rec in output.evidence:
                rec.task_id, rec.collected_by, rec.tool_call_id = task_id, agent, call_id
                if output.is_partial and rec.reliability == Reliability.HIGH:
                    rec.reliability = Reliability.LOW
                self.state.evidence.setdefault(rec.evidence_id, rec)
                ev_ids.append(rec.evidence_id)
            if output.is_partial:
                self.state.stats.partial_results += 1
                self.state.evidence_gaps.append(EvidenceGap(
                    description=f"{tool_name} returned incomplete data for {self._scope(arguments)}",
                    reason=ToolErrorCode.PARTIAL_DATA.value, raised_by=agent, service=arguments.get("service")))
            result = ToolResult(tool_name=tool_name, success=True, data=output.data, is_partial=output.is_partial,
                                warnings=output.warnings, execution_time_ms=round(elapsed, 2), attempts=attempts,
                                evidence_ids=ev_ids)
        else:
            assert error is not None
            self.state.evidence_gaps.append(EvidenceGap(
                description=f"{tool_name} failed for {self._scope(arguments)}: {error.message}",
                reason=error.code.value, raised_by=agent, service=arguments.get("service")))
            result = ToolResult(tool_name=tool_name, success=False, error=error, execution_time_ms=round(elapsed, 2),
                                attempts=attempts)
        self.state.tool_calls.append(ToolCallRecord(
            call_id=call_id, tool_name=tool_name, agent=agent, task_id=task_id, arguments=arguments,
            success=result.success, is_partial=result.is_partial,
            error_code=result.error.code.value if result.error else None, attempts=attempts,
            execution_time_ms=result.execution_time_ms, evidence_ids=ev_ids))
        logger.info("tool=%s agent=%s ok=%s partial=%s attempts=%d ms=%.1f evidence=%d", tool_name, agent,
                    result.success, result.is_partial, attempts, elapsed, len(ev_ids))
        return result

    @staticmethod
    def _scope(arguments: dict[str, Any]) -> str:
        return ", ".join(f"{k}={v}" for k, v in arguments.items() if k in ("service", "metrics", "keyword", "symptoms")) or "all"
