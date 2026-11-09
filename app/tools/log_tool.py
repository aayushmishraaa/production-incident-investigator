"""TOOL 1: application log search."""
from __future__ import annotations

import hashlib
import re
from collections import OrderedDict

from app.models.evidence import EvidenceRecord, Reliability, SourceType
from app.models.tool import LogQueryInput
from app.tools.base import BaseTool, PartialFn, ToolOutput
from app.tools.data_store import OperationalDataStore, parse_ts

_DIGITS = re.compile(r"\d+")


def template_of(message: str) -> str:
    return _DIGITS.sub("<n>", message)


class LogQueryTool(BaseTool):
    name = "query_logs"
    description = (
        "Search application/infrastructure logs. Filter by service, severities, ISO-8601 time range and a "
        "case-insensitive keyword. Returns message PATTERN summaries (count, first/last seen, evidence id) "
        "plus up to `limit` raw records (each with its log_id evidence id)."
    )
    input_model = LogQueryInput

    def execute(self, inp: LogQueryInput, store: OperationalDataStore, partial: PartialFn) -> ToolOutput:
        services = set(store.services())
        if inp.service and inp.service not in services:
            raise ValueError(f"unknown service '{inp.service}'. Known: {sorted(services)}")
        start = parse_ts(inp.start) if inp.start else None
        end = parse_ts(inp.end) if inp.end else None
        kw = inp.keyword.lower() if inp.keyword else None
        sev = set(inp.severity) if inp.severity else None

        matched = []
        for rec in store.logs:
            ts = parse_ts(rec["timestamp"])
            if inp.service and rec["service"] != inp.service:
                continue
            if sev and rec["severity"] not in sev:
                continue
            if start and ts < start or end and ts > end:
                continue
            if kw and kw not in rec["message"].lower():
                continue
            matched.append(rec)
        matched, is_partial = partial(matched)

        patterns: "OrderedDict[tuple[str, str, str], dict]" = OrderedDict()
        for rec in matched:
            key = (rec["service"], rec["severity"], template_of(rec["message"]))
            p = patterns.setdefault(key, {"count": 0, "first_seen": rec["timestamp"], "last_seen": rec["timestamp"],
                                          "example": rec["message"], "log_ids": []})
            p["count"] += 1
            p["last_seen"] = rec["timestamp"]
            p["log_ids"].append(rec["log_id"])

        rel = Reliability.LOW if is_partial else Reliability.HIGH
        evidence, summaries = [], []
        for (svc, severity, tmpl), p in sorted(patterns.items(), key=lambda kv: (-_sev_rank(kv[0][1]), -kv[1]["count"])):
            pid = f"logpat-{svc}-{hashlib.sha1(tmpl.encode()).hexdigest()[:8]}"
            summaries.append({"type": "pattern", "evidence_id": pid, "service": svc, "severity": severity,
                              "pattern": tmpl, "count": p["count"], "first_seen": p["first_seen"],
                              "last_seen": p["last_seen"], "example": p["example"]})
            evidence.append(EvidenceRecord(
                evidence_id=pid, source_type=SourceType.LOG, source_id=f"logs:{svc}", timestamp=parse_ts(p["first_seen"]),
                description=f"{p['count']}x {severity} on {svc}: '{p['example']}' (first {p['first_seen']}, last {p['last_seen']})",
                value={"count": p["count"], "pattern": tmpl, "log_ids": p["log_ids"]}, reliability=rel, service=svc))
        records = []
        for rec in sorted(matched, key=lambda r: (-_sev_rank(r["severity"]), r["timestamp"]))[: inp.limit]:
            records.append({"type": "record", **rec})
            evidence.append(EvidenceRecord(
                evidence_id=rec["log_id"], source_type=SourceType.LOG, source_id=f"logs:{rec['service']}",
                timestamp=parse_ts(rec["timestamp"]), description=f"{rec['severity']} {rec['service']}: {rec['message']}",
                value=rec["message"], reliability=rel, service=rec["service"]))
        warnings = [] if matched else ["no log records matched the query"]
        data = [{"type": "summary", "total_matched": len(matched), "patterns": len(summaries)}] + summaries[:25] + records
        return ToolOutput(data=data, evidence=evidence, warnings=warnings, is_partial=is_partial)


def _sev_rank(s: str) -> int:
    return {"DEBUG": 0, "INFO": 1, "WARN": 2, "ERROR": 3, "FATAL": 4}.get(s, 0)
