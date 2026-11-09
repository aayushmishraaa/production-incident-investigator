"""Scripted stub LLM for offline tests and keyless smoke runs.

NOT an evaluation subject: it exists so the orchestration/tooling can be tested without
API cost. It follows GENERIC heuristics (it never sees incident ids or ground truth) and
reports no token usage (tokens_available=False). Tests can override behaviour per agent
via `overrides={agent_name: callable(ctx) -> LLMResponse | Exception}`.
"""
from __future__ import annotations

import asyncio
import json
import re
import uuid
from typing import Any, Callable, Optional

from app.llm.provider import LLMProvider, LLMResponse, ToolCall
from app.models.investigation import TokenUsage

METRIC_TO_CATEGORY = {
    "db_conn_util_pct": "db_connection_pool_exhaustion", "cpu_pct": "resource_saturation",
    "cache_hit_rate": "cache_degradation", "request_rate": "traffic_surge",
    "disk_io_wait_ms": "infrastructure_degradation", "memory_pct": "resource_saturation",
}


def _tc(name: str, args: dict[str, Any]) -> ToolCall:
    return ToolCall(id=f"toolu_{uuid.uuid4().hex[:12]}", name=name, input=args)


def _first_user_text(messages: list[dict[str, Any]]) -> str:
    c = messages[0]["content"]
    return c if isinstance(c, str) else json.dumps(c)


def _tool_payloads(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for m in messages:
        if m["role"] != "user" or isinstance(m["content"], str):
            continue
        for block in m["content"]:
            if block.get("type") == "tool_result" and not block.get("is_error"):
                try:
                    out.append(json.loads(block["content"]))
                except (json.JSONDecodeError, TypeError):
                    pass
    return out


def _turns(messages: list[dict[str, Any]]) -> int:
    return sum(1 for m in messages if m["role"] == "assistant")


class StubProvider(LLMProvider):
    name = "stub"
    model = "stub-heuristic"
    tokens_available = False

    def __init__(self, overrides: Optional[dict[str, Callable[[dict[str, Any]], Any]]] = None, latency_s: float = 0.0):
        self.overrides = overrides or {}
        self.latency_s = latency_s
        self.calls: list[dict[str, Any]] = []

    async def complete(self, *, agent: str, system: str, messages: list[dict[str, Any]],
                       tools: list[dict[str, Any]], max_tokens: Optional[int] = None) -> LLMResponse:
        if self.latency_s:
            await asyncio.sleep(self.latency_s)
        tool_names = [t["name"] for t in tools]
        ctx = {"agent": agent, "system": system, "messages": messages, "tools": tool_names, "turn": _turns(messages)}
        self.calls.append({"agent": agent, "turn": ctx["turn"]})
        if agent in self.overrides:
            out = self.overrides[agent](ctx)
            if isinstance(out, Exception):
                raise out
            if out is not None:
                return self._finish(out)
        submit = next((n for n in tool_names if n.startswith("submit")), None)
        handler = getattr(self, f"_{submit}", None)
        resp = handler(ctx) if handler else LLMResponse(text="no-op")
        return self._finish(resp)

    @staticmethod
    def _finish(resp: LLMResponse) -> LLMResponse:
        resp.usage = TokenUsage(llm_calls=1)  # no real token accounting for the stub
        resp.stop_reason = "tool_use" if resp.tool_calls else "end_turn"
        resp.assistant_content = ([{"type": "text", "text": resp.text}] if resp.text else []) + \
            [{"type": "tool_use", "id": c.id, "name": c.name, "input": c.input} for c in resp.tool_calls]
        return resp

    # ------------------------------------------------------------------ orchestrator
    def _submit_plan(self, ctx: dict) -> LLMResponse:
        text = _first_user_text(ctx["messages"])
        m = re.search(r"Reported affected services: ([^.\n]+)", text)
        svcs = [s.strip() for s in m.group(1).split(",")] if m else []
        return LLMResponse(tool_calls=[_tc("submit_plan", {
            "incident_summary": text.split("\n")[0][:200], "key_services": svcs,
            "tasks": [{"agent": "observability", "objective": "Compare logs/metrics of affected services vs baseline",
                       "services": svcs, "focus": ["logs", "metrics"]},
                      {"agent": "dependency", "objective": "Review deployments, config changes and dependencies",
                       "services": svcs, "focus": ["deployments", "config", "topology"]}]})])

    # ------------------------------------------------------------------ specialists
    def _submit_findings(self, ctx: dict) -> LLMResponse:
        text = _first_user_text(ctx["messages"])
        svcs = re.search(r"Services to focus on: ([^\n]+)", text)
        services = [s.strip() for s in svcs.group(1).split(",")] if svcs and "judgement" not in svcs.group(1) else ["api-gateway"]
        win = re.search(r"analysis window (\S+) to (\S+);", text)
        start, end = (win.group(1), win.group(2)) if win else (None, None)
        if ctx["turn"] == 0:
            calls = []
            if "query_logs" in ctx["tools"]:
                for s in services[:4]:
                    calls.append(_tc("query_metrics", {"service": s, "start": start, "end": end, "metrics": [
                        "error_rate", "p95_latency_ms", "cpu_pct", "request_rate", "db_conn_util_pct", "timeout_rate"]}))
                    calls.append(_tc("query_logs", {"service": s, "severity": ["WARN", "ERROR"], "limit": 5}))
            else:
                calls.append(_tc("get_deployments", {}))
                calls.append(_tc("get_config_changes", {}))
                calls.append(_tc("get_service_dependencies", {"service": services[0]}))
            return LLMResponse(tool_calls=calls)
        findings = []
        for p in _tool_payloads(ctx["messages"]):
            for row in p.get("data", []):
                if row.get("evidence_id", "").startswith("met-") and row.get("change_pct") is not None \
                        and abs(row["change_pct"]) >= 50:
                    findings.append({"kind": "observed_fact", "statement": f"{row['metric']} changed {row['change_pct']}% "
                                     f"(onset {row.get('onset')})", "service": row["evidence_id"].split("-")[1],
                                     "timestamp": row.get("onset"), "evidence_ids": [row["evidence_id"]]})
                elif row.get("type") == "pattern" and row.get("severity") == "ERROR":
                    findings.append({"kind": "observed_fact", "statement": f"{row['count']}x {row['pattern']}",
                                     "service": row["service"], "timestamp": row["first_seen"],
                                     "evidence_ids": [row["evidence_id"]]})
                elif row.get("deployment_id"):
                    findings.append({"kind": "observed_fact", "statement": f"deployment {row['service']} {row['to_version']} at {row['timestamp']}",
                                     "service": row["service"], "timestamp": row["timestamp"], "evidence_ids": [row["deployment_id"]]})
                elif row.get("change_id"):
                    findings.append({"kind": "observed_fact", "statement": f"config {row['key']} {row['old_value']}->{row['new_value']}",
                                     "service": row["service"], "timestamp": row["timestamp"], "evidence_ids": [row["change_id"]]})
            if not p.get("success", True) or p.get("is_partial"):
                findings.append({"kind": "missing_evidence", "statement": "a query failed or was partial", "evidence_ids": []})
        if not findings:
            findings = [{"kind": "missing_evidence", "statement": "no significant anomalies or changes found", "evidence_ids": []}]
        return LLMResponse(tool_calls=[_tc("submit_findings", {"findings": findings[:15], "summary": f"{len(findings)} findings",
                                                               "uncertainties": []})])

    # ------------------------------------------------------------------ reasoning
    def _submit_hypotheses(self, ctx: dict) -> LLMResponse:
        text = _first_user_text(ctx["messages"])
        cat = re.findall(r"^\s+(\S+) \| (\w+) \| (\S+) \| (\w+) \| (.*)$", text, flags=re.M)
        hyps = []
        for eid, typ, svc, _rel, desc in cat:
            if typ == "metric":
                metric = eid.split("-")[-3] if eid.count("-") >= 4 else ""
                for name, category in METRIC_TO_CATEGORY.items():
                    if name in eid:
                        m = re.search(r"change (-?[\d.]+)%", desc)
                        if m and abs(float(m.group(1))) >= 50:
                            hyps.append((category, svc, eid))
            elif typ in ("deployment", "config"):
                hyps.append(("deployment_regression" if typ == "deployment" else "configuration_regression", svc, eid))
        out, seen = [], set()
        for category, svc, eid in hyps:
            if (category, svc) in seen:
                continue
            seen.add((category, svc))
            out.append({"hypothesis_id": f"H{len(out) + 1}", "category": category, "culprit_service": svc,
                        "description": f"{category.replace('_', ' ')} in {svc}", "mechanism": "stub heuristic",
                        "supporting_evidence": [{"evidence_id": eid, "strength": "moderate"}]})
        if not out:
            out = [{"hypothesis_id": "H1", "category": "unknown", "culprit_service": None,
                    "description": "insufficient evidence", "mechanism": "n/a",
                    "missing_evidence": ["telemetry for affected services"]}]
        return LLMResponse(tool_calls=[_tc("submit_hypotheses", {"hypotheses": out[:4],
                                                                 "ranking_rationale": "stub ordering"})])

    # ------------------------------------------------------------------ critic
    def _submit_verdict(self, ctx: dict) -> LLMResponse:
        text = _first_user_text(ctx["messages"])
        hyps = re.findall(r'"hypothesis_id": "(H\d+)"', text)
        blocking = set(re.findall(r"^\s+(H\d+) BLOCKING", text, flags=re.M))
        assessments = [{"hypothesis_id": h, "decision": "needs_evidence" if h in blocking else "accept",
                        "reasoning": "stub review"} for h in hyps]
        clean = [h for h in hyps if h not in blocking]
        rnd = re.search(r"round (\d+) of max (\d+)", text)
        last_round = rnd and rnd.group(1) == rnd.group(2)
        if clean:
            verdict = "APPROVED"
        else:
            verdict = "INCONCLUSIVE" if last_round or not hyps else "NEEDS_MORE_EVIDENCE"
        reqs = [] if verdict != "NEEDS_MORE_EVIDENCE" else [
            {"target_agent": "observability", "request": "verify timing of earliest anomaly", "services": []}]
        return LLMResponse(tool_calls=[_tc("submit_verdict", {"verdict": verdict, "summary": "stub critic",
                                                              "assessments": assessments, "evidence_requests": reqs})])

    # ------------------------------------------------------------------ reporting
    def _submit_report_narrative(self, ctx: dict) -> LLMResponse:
        return LLMResponse(tool_calls=[_tc("submit_report_narrative", {
            "executive_summary": "Stub narrative summary.", "corrective_actions": ["Mitigate impact"],
            "preventive_actions": ["Add tests"], "monitoring_recommendations": ["Alert on p95 latency"],
            "limitations": ["Generated by stub LLM"], "conclusion": "See status."})])

    # ------------------------------------------------------------------ single agent baseline
    def _submit_investigation(self, ctx: dict) -> LLMResponse:
        if ctx["turn"] == 0:
            text = _first_user_text(ctx["messages"])
            m = re.search(r"Reported affected services: ([^.\n]+)", text)
            svcs = [s.strip() for s in m.group(1).split(",")] if m else ["api-gateway"]
            win = re.search(r"analysis window (\S+) to (\S+);", text)
            calls = [_tc("get_deployments", {}), _tc("get_config_changes", {})]
            for s in svcs[:3]:
                calls.append(_tc("query_metrics", {"service": s, "start": win.group(1), "end": win.group(2),
                                                   "metrics": ["error_rate", "p95_latency_ms", "cpu_pct"]}))
            return LLMResponse(tool_calls=calls)
        ids = [r.get("evidence_id") or r.get("deployment_id") or r.get("change_id")
               for p in _tool_payloads(ctx["messages"]) for r in p.get("data", [])]
        ids = [i for i in ids if i]
        return LLMResponse(tool_calls=[_tc("submit_investigation", {
            "hypotheses": [{"hypothesis_id": "H1", "category": "unknown", "culprit_service": None,
                            "description": "stub", "mechanism": "stub", "confidence": 0.2,
                            "supporting_evidence": [{"evidence_id": i} for i in ids[:2]]}],
            "final_status": "INCONCLUSIVE", "executive_summary": "stub", "corrective_actions": ["mitigate"],
            "preventive_actions": ["test"], "monitoring_recommendations": ["alert"], "limitations": [],
            "evidence_gaps": [], "conclusion": "stub"})])
