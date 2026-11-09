"""TOOL 3: deployment history."""
from __future__ import annotations

from app.models.evidence import EvidenceRecord, SourceType
from app.models.tool import DeploymentQueryInput
from app.tools.base import BaseTool, PartialFn, ToolOutput
from app.tools.data_store import OperationalDataStore, parse_ts


class DeploymentHistoryTool(BaseTool):
    name = "get_deployments"
    description = ("List deployments (service, timestamp, from/to version, status, change summary), optionally "
                   "filtered by service and ISO time range. Each deployment's deployment_id is its evidence id.")
    input_model = DeploymentQueryInput

    def execute(self, inp: DeploymentQueryInput, store: OperationalDataStore, partial: PartialFn) -> ToolOutput:
        if inp.service and inp.service not in store.services():
            raise ValueError(f"unknown service '{inp.service}'")
        out = []
        for d in store.deployments:
            ts = parse_ts(d["timestamp"])
            if inp.service and d["service"] != inp.service:
                continue
            if inp.start and ts < parse_ts(inp.start) or inp.end and ts > parse_ts(inp.end):
                continue
            out.append(d)
        out, is_partial = partial(out)
        out.sort(key=lambda d: d["timestamp"])
        evidence = [EvidenceRecord(
            evidence_id=d["deployment_id"], source_type=SourceType.DEPLOYMENT, source_id=d["deployment_id"],
            timestamp=parse_ts(d["timestamp"]), service=d["service"], value=d,
            description=f"Deployment of {d['service']} {d['from_version']}->{d['to_version']} at {d['timestamp']} "
                        f"({d['status']}): {d['changes']}") for d in out]
        warnings = [] if out else ["no deployments matched the query"]
        return ToolOutput(data=out, evidence=evidence, warnings=warnings, is_partial=is_partial)
