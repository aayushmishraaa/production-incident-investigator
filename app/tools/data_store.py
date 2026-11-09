"""Read-only access to one simulated production environment.

Ground truth is deliberately NOT loadable from here: this module refuses any path
under data/ground_truth, and agents only ever see data through tools built on it.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import get_settings

FORBIDDEN_DIR = "ground_truth"


def parse_ts(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _safe_path(base: Path, *parts: str) -> Path:
    path = base.joinpath(*parts).resolve()
    if FORBIDDEN_DIR in path.parts:
        raise PermissionError("Operational tools may not read evaluation ground truth")
    return path


class OperationalDataStore:
    def __init__(self, environment_id: str, data_dir: Path | None = None):
        self.environment_id = environment_id
        self.data_dir = Path(data_dir or get_settings().data_dir)
        self._logs: list[dict[str, Any]] | None = None
        self._metrics: dict[str, Any] | None = None

    def _json(self, *parts: str, default: Any = None) -> Any:
        path = _safe_path(self.data_dir, *parts)
        if not path.exists():
            return default
        return json.loads(path.read_text())

    @property
    def logs(self) -> list[dict[str, Any]]:
        if self._logs is None:
            path = _safe_path(self.data_dir, "logs", f"{self.environment_id}.jsonl")
            self._logs = [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []
        return self._logs

    @property
    def metrics(self) -> dict[str, Any]:
        if self._metrics is None:
            self._metrics = self._json("metrics", f"{self.environment_id}.json", default={})
        return self._metrics

    @property
    def deployments(self) -> list[dict[str, Any]]:
        return self._json("deployments", f"{self.environment_id}.json", default=[])

    @property
    def configurations(self) -> list[dict[str, Any]]:
        return self._json("configurations", f"{self.environment_id}.json", default=[])

    @property
    def failure_profile(self) -> dict[str, Any]:
        return self._json("failures", f"{self.environment_id}.json", default={})

    @property
    def service_graph(self) -> dict[str, Any]:
        return _load_shared(str(self.data_dir), "dependencies", "service_graph.json")

    @property
    def historical_incidents(self) -> list[dict[str, Any]]:
        return _load_shared(str(self.data_dir), "historical_incidents", "historical_incidents.json")

    def services(self) -> list[str]:
        return list(self.service_graph.get("services", []))


@lru_cache(maxsize=8)
def _load_shared(data_dir: str, *parts: str) -> Any:
    return json.loads(_safe_path(Path(data_dir), *parts).read_text())


def list_incident_reports(data_dir: Path | None = None) -> list[dict[str, Any]]:
    base = Path(data_dir or get_settings().data_dir) / "incidents"
    return [json.loads(p.read_text()) for p in sorted(base.glob("*.json"))]


def load_incident_report(incident_id: str, data_dir: Path | None = None) -> dict[str, Any]:
    path = _safe_path(Path(data_dir or get_settings().data_dir), "incidents", f"{incident_id}.json")
    if not path.exists():
        raise FileNotFoundError(f"Unknown incident {incident_id}")
    return json.loads(path.read_text())
