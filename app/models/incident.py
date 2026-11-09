"""Incident report as received by the system (no ground truth here)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

IncidentSeverity = Literal["SEV1", "SEV2", "SEV3", "SEV4"]


class IncidentReport(BaseModel):
    incident_id: str = Field(pattern=r"^[A-Z]+-[0-9A-Za-z-]+$")
    title: str = Field(min_length=3)
    description: str
    severity: IncidentSeverity = "SEV2"
    reported_at: datetime
    symptom_start: datetime
    affected_services: list[str] = Field(default_factory=list)
    reporter: str = "on-call"

    @field_validator("affected_services")
    @classmethod
    def _normalise(cls, v: list[str]) -> list[str]:
        return sorted({s.strip().lower() for s in v if s.strip()})
