"""Shared LLM tool-calling loop for all agents.

Each agent = system prompt + its own tool subset + a 'submit' tool whose JSON schema
is the agent's output contract. The loop:
  1. call the LLM with history + tools
  2. execute any operational tool calls concurrently (through the shared ToolExecutor)
  3. when the agent calls its submit tool, validate the payload with Pydantic;
     on validation failure feed the error back (bounded) instead of crashing
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, ClassVar, Optional

from pydantic import BaseModel, ValidationError

from app.llm.provider import LLMProvider
from app.models.agent import AgentName, AgentStatus, InvestigationTask
from app.models.investigation import InvestigationState
from app.tools.base import ToolExecutor

logger = logging.getLogger("agents")


class AgentOutputError(RuntimeError):
    """Agent failed to produce a valid structured output within its step budget."""


class BudgetStop(RuntimeError):
    """An investigation-level execution limit (LLM calls / cost) was reached."""


def get_evidence_tool_schema() -> dict[str, Any]:
    return {
        "name": "get_evidence",
        "description": "Look up evidence records already collected in the shared investigation state by evidence_id.",
        "input_schema": {"type": "object", "properties": {"evidence_ids": {"type": "array", "items": {"type": "string"},
                                                                          "maxItems": 20}},
                         "required": ["evidence_ids"]},
    }


class BaseAgent:
    name: ClassVar[AgentName]
    system_prompt: ClassVar[str]
    tool_names: ClassVar[list[str]] = []
    submit_name: ClassVar[str] = "submit"
    submit_description: ClassVar[str] = "Submit your final structured output."
    submit_model: ClassVar[type[BaseModel]]
    uses_evidence_lookup: ClassVar[bool] = False
    max_tokens: ClassVar[int] = 4096

    def __init__(self, llm: LLMProvider, executor: Optional[ToolExecutor], state: InvestigationState):
        self.llm = llm
        self.executor = executor
        self.state = state
        self.transcript: list[dict[str, Any]] = []

    # ---------------------------------------------------------------- hooks
    def validate_submission(self, output: BaseModel) -> Optional[str]:
        """Return an error string to send back to the LLM, or None if acceptable."""
        return None

    # ---------------------------------------------------------------- tools
    def _tool_schemas(self) -> list[dict[str, Any]]:
        schemas = self.executor.schemas(self.tool_names) if self.executor and self.tool_names else []
        if self.uses_evidence_lookup:
            schemas.append(get_evidence_tool_schema())
        sub = self.submit_model.model_json_schema()
        sub.pop("title", None)
        schemas.append({"name": self.submit_name, "description": self.submit_description, "input_schema": sub})
        return schemas

    def _lookup_evidence(self, ids: list[str]) -> str:
        out = []
        for eid in ids[:20]:
            rec = self.state.evidence.get(eid)
            out.append({"evidence_id": eid, "found": False} if rec is None else
                       {"evidence_id": eid, "found": True, "source_type": rec.source_type.value, "service": rec.service,
                        "timestamp": rec.timestamp.isoformat() if rec.timestamp else None,
                        "reliability": rec.reliability.value, "description": rec.description})
        return json.dumps(out)

    def _check_budget(self) -> None:
        cfg, usage = self.state.config, self.state.stats.usage_total
        if usage.llm_calls >= cfg.max_llm_calls:
            raise BudgetStop(f"LLM call limit ({cfg.max_llm_calls}) reached")
        if usage.cost_usd >= cfg.max_cost_usd:
            raise BudgetStop(f"investigation cost budget (${cfg.max_cost_usd}) reached")

    # ---------------------------------------------------------------- loop
    async def run_loop(self, briefing: str, task: Optional[InvestigationTask] = None,
                       max_steps: Optional[int] = None) -> BaseModel:
        cfg = self.state.config
        max_steps = max_steps or cfg.max_agent_steps
        tools = self._tool_schemas()
        messages: list[dict[str, Any]] = [{"role": "user", "content": briefing}]
        self.state.agent_status[self.name.value] = AgentStatus.RUNNING
        invalid_feedback = 0
        task_id = task.task_id if task else None

        for step in range(max_steps + 1):
            self._check_budget()
            if step == max_steps:
                messages.append({"role": "user", "content": f"Step limit reached. Call {self.submit_name} NOW with "
                                 "what you have, listing anything unverified as missing evidence."})
            resp = await self.llm.complete(agent=self.name.value, system=self.system_prompt, messages=messages,
                                           tools=tools, max_tokens=self.max_tokens)
            self.state.record_usage(self.name.value, resp.usage)
            messages.append({"role": "assistant", "content": resp.assistant_content})
            self.transcript.append({"step": step, "text": resp.text[:500],
                                    "tool_calls": [{"name": c.name, "input": c.input} for c in resp.tool_calls]})

            if not resp.tool_calls:
                self.state.stats.invalid_llm_outputs += 1
                invalid_feedback += 1
                if invalid_feedback > 2:
                    raise AgentOutputError(f"{self.name.value} produced no tool call/submission")
                messages.append({"role": "user", "content": f"You must respond by calling tools; finish by calling "
                                 f"{self.submit_name} with valid JSON."})
                continue

            submit_calls = [c for c in resp.tool_calls if c.name == self.submit_name]
            op_calls = [c for c in resp.tool_calls if c.name != self.submit_name]
            results: list[tuple[str, str, bool]] = []

            if op_calls:
                outs = await asyncio.gather(*(self._exec(c.name, c.input, task_id) for c in op_calls))
                results.extend((c.id, out, err) for c, (out, err) in zip(op_calls, outs))

            for sc in submit_calls:
                try:
                    output = self.submit_model.model_validate(sc.input)
                    problem = self.validate_submission(output) if invalid_feedback < 2 else None
                except ValidationError as e:
                    output, problem = None, "; ".join(
                        f"{'.'.join(map(str, er['loc']))}: {er['msg']}" for er in e.errors()[:6])
                if problem is None and output is not None and not op_calls:
                    self.state.agent_status[self.name.value] = AgentStatus.COMPLETED
                    return output
                if problem is None and output is not None:
                    # submitted alongside other tool calls: accept, the other calls already ran
                    self.state.agent_status[self.name.value] = AgentStatus.COMPLETED
                    return output
                self.state.stats.invalid_llm_outputs += 1
                invalid_feedback += 1
                logger.warning("%s invalid submission: %s", self.name.value, problem)
                results.append((sc.id, f"Submission rejected: {problem}. Fix and call {self.submit_name} again.", True))
            messages.append(self.llm.tool_results_message(results))

        raise AgentOutputError(f"{self.name.value} exceeded {max_steps} steps without a valid submission")

    async def _exec(self, name: str, args: dict[str, Any], task_id: Optional[str]) -> tuple[str, bool]:
        if name == "get_evidence" and self.uses_evidence_lookup:
            return self._lookup_evidence(list(args.get("evidence_ids", []))), False
        if name not in self.tool_names or self.executor is None:
            return json.dumps({"error": f"tool {name} is not available to {self.name.value}"}), True
        result = await self.executor.call(name, args, agent=self.name.value, task_id=task_id)
        return json.dumps(result.to_llm_payload(), default=str), not result.success


def unknown_ids(state: InvestigationState, ids: list[str]) -> list[str]:
    return [i for i in ids if i not in state.evidence]


def fmt_time(dt) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


Briefing = Callable[..., str]
