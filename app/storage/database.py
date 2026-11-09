"""SQLite connection management."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

from app.config import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS investigations (
    investigation_id TEXT PRIMARY KEY,
    incident_id      TEXT NOT NULL,
    system           TEXT NOT NULL,
    final_status     TEXT NOT NULL,
    created_at       TEXT NOT NULL,
    duration_s       REAL,
    state_json       TEXT NOT NULL,
    report_json      TEXT
);
CREATE INDEX IF NOT EXISTS idx_inv_incident ON investigations(incident_id);
"""


def connect(path: Optional[Path] = None) -> sqlite3.Connection:
    path = Path(path or get_settings().db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.executescript(SCHEMA)
    return conn
