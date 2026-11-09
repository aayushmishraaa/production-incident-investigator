"""Anthropic Claude provider (official SDK, async)."""
from __future__ import annotations

import logging
from typing import Any, Optional

import anthropic

from app.config import get_settings
from app.llm.provider import CostLedger, LLMError, LLMProvider, LLMResponse, ToolCall
from app.models.investigation import TokenUsage

logger = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    name = "anthropic"
    tokens_available = True

    def __init__(self, model: Optional[str] = None, ledger: Optional[CostLedger] = None):
        s = get_settings()
        self.settings = s
        self.model = model or s.model
        self.client = anthropic.AsyncAnthropic(max_retries=3, timeout=90.0)
        self.ledger = ledger or CostLedger()

    def _cost(self, u: TokenUsage) -> float:
        s = self.settings
        return (u.input_tokens * s.price_input + u.output_tokens * s.price_output
                + u.cache_write_tokens * s.price_cache_write + u.cache_read_tokens * s.price_cache_read) / 1_000_000

    async def complete(self, *, agent: str, system: str, messages: list[dict[str, Any]],
                       tools: list[dict[str, Any]], max_tokens: Optional[int] = None) -> LLMResponse:
        self.ledger.check()
        try:
            resp = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens or self.settings.max_output_tokens,
                system=system,
                messages=messages,
                tools=tools,
                tool_choice={"type": "auto"},
                output_config={"effort": self.settings.effort},
                cache_control={"type": "ephemeral"},
            )
        except anthropic.BadRequestError as e:
            raise LLMError(f"bad request: {e.message}") from e
        except anthropic.RateLimitError as e:
            raise LLMError("rate limited") from e
        except anthropic.APIStatusError as e:
            raise LLMError(f"API error {e.status_code}: {e.message}") from e
        except anthropic.APIConnectionError as e:
            raise LLMError("connection error") from e

        u = resp.usage
        usage = TokenUsage(
            input_tokens=u.input_tokens or 0,
            output_tokens=u.output_tokens or 0,
            cache_read_tokens=getattr(u, "cache_read_input_tokens", 0) or 0,
            cache_write_tokens=getattr(u, "cache_creation_input_tokens", 0) or 0,
            llm_calls=1,
        )
        usage.cost_usd = self._cost(usage)
        self.ledger.add(usage)

        if resp.stop_reason == "refusal":
            raise LLMError("model refused the request")

        text_parts, calls = [], []
        for block in resp.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                calls.append(ToolCall(id=block.id, name=block.name, input=dict(block.input or {})))
        logger.debug("%s: stop=%s in=%s out=%s", agent, resp.stop_reason, usage.input_tokens, usage.output_tokens)
        return LLMResponse(text="\n".join(text_parts), tool_calls=calls, stop_reason=resp.stop_reason or "end_turn",
                           usage=usage, assistant_content=resp.content)
