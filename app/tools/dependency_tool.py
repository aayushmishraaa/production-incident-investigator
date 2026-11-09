"""TOOL 5: service dependency graph."""
from __future__ import annotations

from datetime import datetime, timezone

from app.models.evidence import EvidenceRecord, Reliability, SourceType
from app.models.tool import DependencyQueryInput
from app.tools.base import BaseTool, PartialFn, ToolOutput
from app.tools.data_store import OperationalDataStore, parse_ts


def _edges_at(graph: dict, at: datetime) -> tuple[str, list[list[str]], list[dict]]:
    versions = sorted(graph["versions"], key=lambda v: v["effective_from"])
    current = versions[0]
    for v in versions:
        if parse_ts(v["effective_from"]) <= at:
            current = v
    return current["version"], current["edges"], versions


class ServiceDependencyTool(BaseTool):
    name = "get_service_dependencies"
    description = ("Return the service dependency graph around a service. 'upstream' = services it CALLS / depends "
                   "on; 'downstream' = services that call it (would be impacted). Traces chains up to `depth` hops and "
                   "lists topology changes between graph versions affecting the service.")
    input_model = DependencyQueryInput

    def __init__(self, reference_time: datetime | None = None):
        self.reference_time = reference_time or datetime.now(timezone.utc)

    def execute(self, inp: DependencyQueryInput, store: OperationalDataStore, partial: PartialFn) -> ToolOutput:
        graph = store.service_graph
        if inp.service not in graph["services"]:
            raise ValueError(f"unknown service '{inp.service}'. Known: {graph['services']}")
        version, edges, versions = _edges_at(graph, self.reference_time)
        calls: dict[str, set[str]] = {}
        callers: dict[str, set[str]] = {}
        for a, b in edges:
            calls.setdefault(a, set()).add(b)
            callers.setdefault(b, set()).add(a)

        def walk(adj: dict[str, set[str]]) -> list[list[str]]:
            chains, frontier = [], [[inp.service]]
            for _ in range(inp.depth):
                nxt = []
                for path in frontier:
                    for n in sorted(adj.get(path[-1], ())):
                        if n not in path:
                            nxt.append(path + [n])
                chains.extend(nxt)
                frontier = nxt
            return chains

        result: dict = {"service": inp.service, "graph_version": version}
        if inp.direction in ("upstream", "both"):
            result["upstream_dependencies"] = sorted(calls.get(inp.service, ()))
            result["upstream_chains"] = [" -> ".join(c) for c in walk(calls)]
        if inp.direction in ("downstream", "both"):
            result["downstream_dependents"] = sorted(callers.get(inp.service, ()))
            result["potentially_impacted"] = sorted({c[-1] for c in walk(callers)})
        changes = []
        for prev, cur in zip(versions, versions[1:]):
            before = {tuple(e) for e in prev["edges"]}
            after = {tuple(e) for e in cur["edges"]}
            for a, b in sorted(after - before):
                if inp.service in (a, b):
                    changes.append({"version": cur["version"], "effective_from": cur["effective_from"], "added_edge": f"{a} -> {b}"})
            for a, b in sorted(before - after):
                if inp.service in (a, b):
                    changes.append({"version": cur["version"], "effective_from": cur["effective_from"], "removed_edge": f"{a} -> {b}"})
        result["topology_changes"] = changes
        eid = f"topo-{inp.service}-{inp.direction}-d{inp.depth}"
        result["evidence_id"] = eid
        ev = EvidenceRecord(
            evidence_id=eid, source_type=SourceType.DEPENDENCY, source_id=f"graph:{version}", service=inp.service,
            timestamp=self.reference_time, reliability=Reliability.HIGH, value=result,
            description=f"{inp.service} depends on {result.get('upstream_dependencies', '?')}; called by "
                        f"{result.get('downstream_dependents', '?')} (graph {version})")
        return ToolOutput(data=[result], evidence=[ev])
