"""The ONLY module allowed to read evaluation ground truth.

Agents, tools and the orchestration layer never import this module (enforced by
tests/test_evidence_grounding.py::test_ground_truth_isolation).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from app.config import get_settings


def load_ground_truth(incident_id: str, data_dir: Optional[Path] = None) -> dict[str, Any]:
    path = Path(data_dir or get_settings().data_dir) / "ground_truth" / f"{incident_id}.json"
    return json.loads(path.read_text())


def all_ground_truth(data_dir: Optional[Path] = None) -> dict[str, dict[str, Any]]:
    base = Path(data_dir or get_settings().data_dir) / "ground_truth"
    return {p.stem: json.loads(p.read_text()) for p in sorted(base.glob("*.json"))}
