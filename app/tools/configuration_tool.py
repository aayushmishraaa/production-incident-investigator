"""TOOL 4: configuration change history with version diffs."""
from __future__ import annotations

from app.models.evidence import EvidenceRecord, SourceType
from app.models.tool import ConfigQueryInput
from app.tools.base import BaseTool, PartialFn, ToolOutput
from app.tools.data_store import OperationalDataStore, parse_ts


def _numeric_ratio(old: str, new: str) -> float | None:
    try:
        o, n = float(old), float(new)
        return round(n / o, 3) if o else None
    except (TypeError, ValueError):
        return None


class ConfigurationHistoryTool(BaseTool):
    name = "get_config_changes"
    description = ("List configuration changes (service, key, old -> new value, timestamp, author, ticket) with a "
                   "computed diff, optionally filtered by service, key substring and ISO time range. Each change_id "
                   "is its evidence id.")
    input_model = ConfigQueryInput

    def execute(self, inp: ConfigQueryInput, store: OperationalDataStore, partial: PartialFn) -> ToolOutput:
        if inp.service and inp.service not in store.services():
            raise ValueError(f"unknown service '{inp.service}'")
        out = []
        for c in store.configurations:
            ts = parse_ts(c["timestamp"])
            if inp.service and c["service"] != inp.service:
                continue
            if inp.key and inp.key.lower() not in c["key"].lower():
                continue
            if inp.start and ts < parse_ts(inp.start) or inp.end and ts > parse_ts(inp.end):
                continue
            ratio = _numeric_ratio(c["old_value"], c["new_value"])
            out.append({**c, "diff": {"changed_setting": c["key"], "before": c["old_value"], "after": c["new_value"],
                                      "numeric_ratio_after_over_before": ratio}})
        out, is_partial = partial(out)
        out.sort(key=lambda c: c["timestamp"])
        evidence = [EvidenceRecord(
            evidence_id=c["change_id"], source_type=SourceType.CONFIG, source_id=c["change_id"],
            timestamp=parse_ts(c["timestamp"]), service=c["service"], value=c,
            description=f"Config change on {c['service']}: {c['key']} {c['old_value']} -> {c['new_value']} at "
                        f"{c['timestamp']} ({c['ticket']})") for c in out]
        warnings = [] if out else ["no configuration changes matched the query"]
        return ToolOutput(data=out, evidence=evidence, warnings=warnings, is_partial=is_partial)
