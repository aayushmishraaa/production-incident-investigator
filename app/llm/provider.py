"""Provider-agnostic LLM interface used by every agent.

Messages use the Anthropic content-block shape (role + list of blocks) because it
represents tool calls/results explicitly; other providers adapt to it.
"""
from __future__ import annotations

import json
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.config import get_settings
from app.models.investigation import TokenUsage


class ToolCall(BaseModel):
    id: str
    name: str
    input: dict[str, Any] = Field(default_factory=dict)


class LLMResponse(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    text: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    stop_reason: str = "end_turn"
    usage: TokenUsage = Field(default_factory=TokenUsage)
    assistant_content: Any = None   # provider-native content to append to history


class LLMError(RuntimeError):
    """Provider failure (network, API error, refusal)."""


class BudgetExceededError(RuntimeError):
    """Raised when the global spend ledger would exceed the configured cap."""


class CostLedger:
    """Process-safe-ish cumulative spend ledger persisted to disk.

    It enforces the user's overall budget (TOTAL_COST_CAP_USD) across CLI runs.
    """

    _lock = threading.Lock()

    def __init__(self, path: Optional[Path] = None, cap: Optional[float] = None):
        s = get_settings()
        self.path = path or (s.results_dir / "cost_ledger.json")
        self.cap = cap if cap is not None else s.total_cost_cap_usd

    def _read(self) -> dict[str, Any]:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text())
            except json.JSONDecodeError:
                pass
        return {"total_usd": 0.0, "calls": 0, "input_tokens": 0, "output_tokens": 0}

    def total(self) -> float:
        return float(self._read()["total_usd"])

    def check(self) -> None:
        if self.total() >= self.cap:
            raise BudgetExceededError(f"Global LLM spend cap reached (${self.total():.4f} >= ${self.cap:.2f})")

    def add(self, usage: TokenUsage) -> None:
        with self._lock:
            data = self._read()
            data["total_usd"] = round(data["total_usd"] + usage.cost_usd, 6)
            data["calls"] += usage.llm_calls
            data["input_tokens"] += usage.input_tokens + usage.cache_read_tokens + usage.cache_write_tokens
            data["output_tokens"] += usage.output_tokens
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(data, indent=2))


class LLMProvider(ABC):
    name: str = "base"
    model: str = "n/a"
    tokens_available: bool = False

    @abstractmethod
    async def complete(
        self, *, agent: str, system: str, messages: list[dict[str, Any]],
        tools: list[dict[str, Any]], max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        ...

    @staticmethod
    def tool_results_message(results: list[tuple[str, str, bool]]) -> dict[str, Any]:
        """Build ONE user message holding all tool results (parallel tool use)."""
        return {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": tid, "content": content, "is_error": is_err}
                for tid, content, is_err in results
            ],
        }


def build_provider(name: Optional[str] = None) -> LLMProvider:
    name = (name or get_settings().llm_provider).lower()
    if name == "anthropic":
        from app.llm.real_provider import AnthropicProvider
        return AnthropicProvider()
    if name in ("stub", "mock"):
        from app.llm.mock_provider import StubProvider
        return StubProvider()
    raise ValueError(f"Unknown LLM provider '{name}' (expected 'anthropic' or 'stub')")
