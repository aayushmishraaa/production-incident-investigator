from __future__ import annotations

import uuid
from typing import Any

from app.llm.provider import LLMResponse, ToolCall


def call(name: str, args: dict[str, Any]) -> ToolCall:
    return ToolCall(id=f"toolu_{uuid.uuid4().hex[:10]}", name=name, input=args)


def resp(*calls: ToolCall, text: str = "") -> LLMResponse:
    return LLMResponse(text=text, tool_calls=list(calls))


def script(*steps):
    """Override returning the n-th scripted response for the n-th assistant turn (last one repeats)."""
    def fn(ctx):
        step = steps[min(ctx["turn"], len(steps) - 1)]
        return step(ctx) if callable(step) else step
    return fn


def submit_hyps(*hyps, rationale="r") -> LLMResponse:
    return resp(call("submit_hypotheses", {"hypotheses": list(hyps), "ranking_rationale": rationale}))


def hyp(hid, category, service, support, contra=(), cause_time=None, strength="strong", missing=()):
    return {"hypothesis_id": hid, "category": category, "culprit_service": service, "description": f"{category} {service}",
            "mechanism": "m", "cause_time": cause_time,
            "supporting_evidence": [{"evidence_id": e, "strength": strength} for e in support],
            "contradicting_evidence": [{"evidence_id": e, "strength": "strong"} for e in contra],
            "missing_evidence": list(missing)}


def verdict(v, assessments=(), requests=()) -> LLMResponse:
    return resp(call("submit_verdict", {"verdict": v, "summary": f"critic says {v}",
                                        "assessments": list(assessments), "evidence_requests": list(requests)}))
