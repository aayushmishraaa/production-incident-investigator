"""Persistent investigation history."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.models.investigation import InvestigationState
from app.storage.database import connect


class InvestigationRepository:
    def __init__(self, path: Optional[Path] = None):
        self.path = path

    def save(self, state: InvestigationState) -> None:
        with connect(self.path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO investigations VALUES (?,?,?,?,?,?,?,?)",
                (state.investigation_id, state.incident.incident_id, state.system, state.final_status.value,
                 (state.stats.started_at or datetime.now(timezone.utc)).isoformat(), state.stats.duration_s,
                 state.model_dump_json(), json.dumps(state.report, default=str) if state.report else None))

    def get_state(self, investigation_id: str) -> Optional[InvestigationState]:
        with connect(self.path) as conn:
            row = conn.execute("SELECT state_json FROM investigations WHERE investigation_id=?", (investigation_id,)).fetchone()
        return InvestigationState.model_validate_json(row[0]) if row else None

    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        with connect(self.path) as conn:
            rows = conn.execute("SELECT investigation_id, incident_id, system, final_status, created_at, duration_s "
                                "FROM investigations ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        keys = ["investigation_id", "incident_id", "system", "final_status", "created_at", "duration_s"]
        return [dict(zip(keys, r)) for r in rows]
