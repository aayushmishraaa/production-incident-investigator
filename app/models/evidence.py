"""Evidence records. Every claim in a hypothesis must cite one of these by ID."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    LOG = "log"
    METRIC = "metric"
    DEPLOYMENT = "deployment"
    CONFIG = "config"
    DEPENDENCY = "dependency"
    HISTORICAL = "historical"


class Reliability(str, Enum):
    HIGH = "high"          # complete, direct measurement
    MEDIUM = "medium"      # derived / aggregated
    LOW = "low"            # partial result, delayed telemetry, or historical analogy


class EvidenceLabel(str, Enum):
    """Epistemic label used in reports."""

    CONFIRMED_FACT = "CONFIRMED FACT"
    OBSERVED_EVIDENCE = "OBSERVED EVIDENCE"
    INFERENCE = "INFERENCE"
    ASSUMPTION = "ASSUMPTION"
    UNKNOWN = "UNKNOWN"


class EvidenceRecord(BaseModel):
    evidence_id: str
    source_type: SourceType
    source_id: str
    timestamp: Optional[datetime] = None
    description: str
    value: Any = None
    reliability: Reliability = Reliability.HIGH
    service: Optional[str] = None
    task_id: Optional[str] = None
    collected_by: Optional[str] = None
    tool_call_id: Optional[str] = None


class EvidenceGap(BaseModel):
    description: str
    source_type: Optional[SourceType] = None
    service: Optional[str] = None
    reason: str = "not collected"   # e.g. TOOL_TIMEOUT, PARTIAL_DATA, missing telemetry
    raised_by: str = "system"
    resolved: bool = False


class EvidenceRef(BaseModel):
    """A citation of an evidence record inside a hypothesis or finding."""

    evidence_id: str
    note: str = ""
    strength: str = Field(default="moderate", pattern="^(strong|moderate|weak)$")
