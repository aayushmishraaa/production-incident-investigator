"""FastAPI service. Run: uvicorn app.main:app --reload  (docs at /docs)."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Literal, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.config import get_settings
from app.evaluation.evaluator import Evaluator
from app.evaluation.single_agent import run_single_agent
from app.llm.provider import build_provider
from app.models.incident import IncidentReport
from app.models.investigation import FinalStatus, InvestigationConfig, InvestigationState
from app.orchestration.state import create_runtime
from app.orchestration.workflow import run_investigation
from app.reporting.report_generator import save_report
from app.models.report import InvestigationReport
from app.storage.repository import InvestigationRepository
from app.tools.data_store import list_incident_reports, load_incident_report

logging.basicConfig(level=get_settings().log_level)
app = FastAPI(title="Multi-Agent Production Incident Investigator", version="1.0.0",
              description="Six cooperating agents investigate simulated production incidents.")

_live: dict[str, InvestigationState] = {}
_tasks: set[asyncio.Task] = set()
_eval_status: dict[str, Any] = {"status": "idle"}
repo = InvestigationRepository()


class InvestigateRequest(BaseModel):
    incident_id: Optional[str] = Field(default=None, description="Use a bundled synthetic incident (e.g. INC-001)")
    incident: Optional[IncidentReport] = Field(default=None, description="Or supply a full incident report")
    environment_id: Optional[str] = Field(default=None, description="Operational data environment for a custom report")
    system: Literal["multi_agent", "single_agent"] = "multi_agent"
    provider: Optional[Literal["anthropic", "stub"]] = None
    config: InvestigationConfig = Field(default_factory=InvestigationConfig)
    wait: bool = Field(default=False, description="Block until finished (otherwise poll GET /investigations/{id})")


class InvestigateResponse(BaseModel):
    investigation_id: str
    status: str
    incident_id: str
    system: str
    execution: dict[str, Any]


class EvaluateRequest(BaseModel):
    provider: Optional[Literal["anthropic", "stub"]] = None
    runs: int = Field(default=1, ge=1, le=5)
    incidents: Optional[list[str]] = None
    concurrency: int = Field(default=4, ge=1, le=8)


def _get(inv_id: str) -> InvestigationState:
    state = _live.get(inv_id) or repo.get_state(inv_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"investigation {inv_id} not found")
    return state


async def _execute(state_holder: dict, req: InvestigateRequest, incident: IncidentReport) -> InvestigationState:
    llm = build_provider(req.provider)
    if req.system == "single_agent":
        state = await run_single_agent(incident, llm, req.config)
    else:
        rt = create_runtime(incident, llm, req.config, environment_id=req.environment_id)
        state_holder["state"] = rt.state
        _live[rt.state.investigation_id] = rt.state
        state = await run_investigation(incident, llm, req.config, runtime=rt)
    _live[state.investigation_id] = state
    repo.save(state)
    if state.report:
        save_report(InvestigationReport.model_validate(state.report))
    return state


@app.get("/health")
async def health() -> dict[str, Any]:
    s = get_settings()
    return {"status": "ok", "llm_provider": s.llm_provider, "model": s.model,
            "incidents_available": len(list_incident_reports())}


@app.get("/incidents")
async def incidents() -> list[dict[str, Any]]:
    return list_incident_reports()


@app.post("/investigate", response_model=InvestigateResponse, status_code=202)
async def investigate(req: InvestigateRequest) -> InvestigateResponse:
    if bool(req.incident_id) == bool(req.incident):
        raise HTTPException(status_code=422, detail="provide exactly one of incident_id or incident")
    try:
        incident = req.incident or IncidentReport(**load_incident_report(req.incident_id))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    holder: dict[str, Any] = {}
    if req.wait or req.system == "single_agent":
        state = await _execute(holder, req, incident)
        return InvestigateResponse(investigation_id=state.investigation_id, status=state.final_status.value,
                                   incident_id=incident.incident_id, system=req.system,
                                   execution={"duration_s": round(state.stats.duration_s, 2),
                                              "tool_calls": state.stats.tool_calls, "rounds": state.round})
    task = asyncio.create_task(_execute(holder, req, incident))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    for _ in range(50):  # wait until the runtime registers its state id
        if "state" in holder:
            break
        await asyncio.sleep(0.01)
    state = holder["state"]
    return InvestigateResponse(investigation_id=state.investigation_id, status=FinalStatus.RUNNING.value,
                               incident_id=incident.incident_id, system=req.system,
                               execution={"mode": "background", "poll": f"/investigations/{state.investigation_id}",
                                          "config": req.config.model_dump()})


@app.get("/investigations")
async def list_investigations(limit: int = 50) -> list[dict[str, Any]]:
    return repo.list(limit)


@app.get("/investigations/{inv_id}")
async def get_investigation(inv_id: str) -> dict[str, Any]:
    s = _get(inv_id)
    return {"investigation_id": s.investigation_id, "status": s.final_status.value, "round": s.round,
            "state": json.loads(s.model_dump_json(exclude={"report"}))}


@app.get("/investigations/{inv_id}/report")
async def get_report(inv_id: str) -> dict[str, Any]:
    s = _get(inv_id)
    if not s.report:
        raise HTTPException(status_code=409, detail=f"report not ready (status {s.final_status.value})")
    return s.report


@app.get("/investigations/{inv_id}/evidence")
async def get_evidence(inv_id: str) -> dict[str, Any]:
    s = _get(inv_id)
    return {"count": len(s.evidence), "evidence": [e.model_dump(mode="json") for e in s.evidence.values()],
            "gaps": [g.model_dump(mode="json") for g in s.evidence_gaps]}


@app.get("/investigations/{inv_id}/timeline")
async def get_timeline(inv_id: str) -> dict[str, Any]:
    s = _get(inv_id)
    return {"investigation_timeline": [e.model_dump(mode="json") for e in s.timeline],
            "incident_timeline": (s.report or {}).get("timeline", [])}


@app.post("/evaluate", status_code=202)
async def evaluate(req: EvaluateRequest, background: BackgroundTasks) -> dict[str, Any]:
    if _eval_status.get("status") == "running":
        raise HTTPException(status_code=409, detail="an evaluation is already running")

    async def job():
        _eval_status.update(status="running")
        try:
            res = await Evaluator(provider=req.provider, runs=req.runs, incidents=req.incidents,
                                  concurrency=req.concurrency).run()
            _eval_status.update(status="completed", summary=res["summary"])
        except Exception as e:  # noqa: BLE001
            _eval_status.update(status="failed", error=repr(e))

    background.add_task(job)
    return {"status": "started", "poll": "/evaluate/results"}


@app.get("/evaluate/results")
async def evaluate_results() -> dict[str, Any]:
    path = get_settings().results_dir / "evaluation" / "evaluation_results.json"
    if _eval_status.get("status") == "running":
        return {"status": "running"}
    if not path.exists():
        raise HTTPException(status_code=404, detail="no evaluation results yet; POST /evaluate first")
    data = json.loads(path.read_text())
    return {"status": _eval_status.get("status", "completed"), "conditions": data["conditions"],
            "summary": data["summary"], "skipped": data["skipped"]}
