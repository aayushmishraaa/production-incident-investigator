"""Anthropic provider adapter (fake client, no network) and the CLI."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.cli import main
from app.llm.provider import BudgetExceededError, CostLedger, LLMError
from app.llm.real_provider import AnthropicProvider


class FakeMessages:
    def __init__(self, stop_reason="tool_use"):
        self.kwargs = None
        self.stop_reason = stop_reason

    async def create(self, **kw):
        self.kwargs = kw
        return SimpleNamespace(
            stop_reason=self.stop_reason,
            content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text="checking"),
                     SimpleNamespace(type="tool_use", id="toolu_1", name="query_logs", input={"service": "redis"})],
            usage=SimpleNamespace(input_tokens=1000, output_tokens=200, cache_read_input_tokens=500,
                                  cache_creation_input_tokens=0))


def make(tmp_path, stop="tool_use", cap=3.0):
    p = AnthropicProvider.__new__(AnthropicProvider)
    from app.config import get_settings
    p.settings, p.model = get_settings(), "claude-haiku-5-5"
    p.client = SimpleNamespace(messages=FakeMessages(stop))
    p.ledger = CostLedger(tmp_path / "ledger.json", cap=cap)
    return p


async def test_provider_parses_tool_calls_usage_and_cost(tmp_path):
    p = make(tmp_path)
    r = await p.complete(agent="observability", system="s", messages=[{"role": "user", "content": "x"}], tools=[])
    assert r.tool_calls[0].name == "query_logs" and r.text == "checking"
    assert r.usage.input_tokens == 1000 and r.usage.cache_read_tokens == 500
    assert r.usage.cost_usd == pytest.approx((1000 * 0.10 + 200 * 0.50 + 500 * 0.01) / 1e6)
    kw = p.client.messages.kwargs
    assert kw["model"] == "claude-haiku-5-5" and kw["tool_choice"] == {"type": "auto"}
    assert "temperature" not in kw and kw["output_config"]["effort"]
    assert p.ledger.total() == pytest.approx(r.usage.cost_usd)


async def test_provider_refusal_raises(tmp_path):
    with pytest.raises(LLMError):
        await make(tmp_path, stop="refusal").complete(agent="a", system="s", messages=[], tools=[])


async def test_global_cost_cap_blocks_calls(tmp_path):
    p = make(tmp_path, cap=0.0)
    with pytest.raises(BudgetExceededError):
        await p.complete(agent="a", system="s", messages=[], tools=[])


def test_cli_incidents_and_investigate(capsys):
    assert main(["incidents"]) == 0
    assert "INC-001" in capsys.readouterr().out
    assert main(["investigate", "--incident", "INC-010", "--provider", "stub"]) == 0
    out = capsys.readouterr().out
    assert "INCONCLUSIVE" in out and "Tokens: unavailable" in out
    assert main(["investigate", "--incident", "INC-002", "--provider", "stub", "--system", "single_agent"]) == 0
    assert main(["history"]) == 0 and main(["spend"]) == 0
