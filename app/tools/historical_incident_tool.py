"""TOOL 6: historical incident similarity search."""
from __future__ import annotations

import re

from app.models.evidence import EvidenceRecord, Reliability, SourceType
from app.models.tool import HistoricalQueryInput
from app.tools.base import BaseTool, PartialFn, ToolOutput
from app.tools.data_store import OperationalDataStore

_WORD = re.compile(r"[a-z0-9]+")
_STOP = {"the", "a", "an", "of", "on", "in", "to", "and", "high", "increase", "after", "from"}


def _tokens(texts: list[str]) -> set[str]:
    out: set[str] = set()
    for t in texts:
        out |= {w for w in _WORD.findall(t.lower()) if w not in _STOP}
    return out


def similarity(q_sym: list[str], q_svc: list[str], inc: dict) -> float:
    a, b = _tokens(q_sym), _tokens(inc["symptoms"] + [inc["title"]])
    sym = len(a & b) / len(a | b) if a | b else 0.0
    sa, sb = set(q_svc), set(inc["services"])
    svc = len(sa & sb) / len(sa | sb) if sa | sb else 0.0
    return round(0.7 * sym + 0.3 * svc, 3)


class HistoricalIncidentTool(BaseTool):
    name = "search_historical_incidents"
    description = ("Find previously resolved incidents similar to the given symptoms/services (Jaccard similarity "
                   "on symptom terms 70% + services 30%). Returns past root causes and remediations. Historical "
                   "similarity is an ANALOGY, never proof of the current root cause.")
    input_model = HistoricalQueryInput

    def execute(self, inp: HistoricalQueryInput, store: OperationalDataStore, partial: PartialFn) -> ToolOutput:
        scored = sorted(((similarity(inp.symptoms, inp.services, h), h) for h in store.historical_incidents),
                        key=lambda x: -x[0])
        top = [(s, h) for s, h in scored[: inp.limit] if s > 0]
        data, evidence = [], []
        for s, h in top:
            eid = f"hist-{h['id']}"
            data.append({"evidence_id": eid, "similarity": s, **h})
            evidence.append(EvidenceRecord(
                evidence_id=eid, source_type=SourceType.HISTORICAL, source_id=h["id"], reliability=Reliability.LOW,
                service=h["services"][0], value={"similarity": s, "root_cause_category": h["root_cause_category"]},
                description=f"Past incident {h['id']} '{h['title']}' (similarity {s}): {h['root_cause']}"))
        return ToolOutput(data=data, evidence=evidence,
                          warnings=["historical matches are analogies, not evidence of the current cause"])
