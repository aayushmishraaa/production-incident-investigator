"""Configurable fault injection for tools.

Two sources of faults:
* the environment's failure profile (data/failures/<ID>.json), e.g.
  {"query_metrics": {"fail_first_n": 2, "error": "TOOL_TIMEOUT"},
   "query_logs": {"partial": true, "drop_fraction": 0.5}}
* a global random failure rate (InvestigationConfig.random_failure_rate), seeded.
"""
from __future__ import annotations

import asyncio
import random
from typing import Any

from app.models.tool import ToolErrorCode


class SimulatedToolFailure(Exception):
    def __init__(self, code: ToolErrorCode, message: str):
        super().__init__(message)
        self.code = code


class FailureSimulator:
    def __init__(self, profile: dict[str, Any] | None = None, random_failure_rate: float = 0.0,
                 seed: int = 7, timeout_s: float = 2.0):
        self.profile = profile or {}
        self.random_failure_rate = random_failure_rate
        self.rng = random.Random(seed)
        self.timeout_s = timeout_s
        self.call_counts: dict[str, int] = {}

    async def before_call(self, tool_name: str) -> None:
        """Raise or hang (to trigger a real timeout) according to the profile."""
        n = self.call_counts.get(tool_name, 0)
        self.call_counts[tool_name] = n + 1
        spec = self.profile.get(tool_name, {})
        code = None
        if n < int(spec.get("fail_first_n", 0)):
            code = ToolErrorCode(spec.get("error", "SERVICE_UNAVAILABLE"))
        elif self.random_failure_rate and self.rng.random() < self.random_failure_rate:
            code = self.rng.choice([ToolErrorCode.TOOL_TIMEOUT, ToolErrorCode.SERVICE_UNAVAILABLE])
        if code is None:
            return
        if code == ToolErrorCode.TOOL_TIMEOUT:
            # genuinely exceed the executor's timeout so the timeout path is exercised
            await asyncio.sleep(self.timeout_s + 0.2)
        raise SimulatedToolFailure(code, f"simulated {code.value} for {tool_name}")

    def apply_partial(self, tool_name: str, data: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
        spec = self.profile.get(tool_name, {})
        if not spec.get("partial"):
            return data, False
        frac = float(spec.get("drop_fraction", 0.5))
        kept = [d for d in data if self.rng.random() >= frac]
        return kept, True
