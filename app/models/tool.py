"""Tool input/output schemas shared by every operational tool."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class ToolErrorCode(str, Enum):
    TOOL_TIMEOUT = "TOOL_TIMEOUT"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    INVALID_QUERY = "INVALID_QUERY"
    PARTIAL_DATA = "PARTIAL_DATA"
    INTERNAL_TOOL_ERROR = "INTERNAL_TOOL_ERROR"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"


RETRYABLE_ERRORS = {ToolErrorCode.TOOL_TIMEOUT, ToolErrorCode.SERVICE_UNAVAILABLE, ToolErrorCode.INTERNAL_TOOL_ERROR}


class ToolError(BaseModel):
    code: ToolErrorCode
    message: str
    retryable: bool = False


class ToolResult(BaseModel):
    """Uniform envelope returned by every tool call."""

    tool_name: str
    success: bool
    data: list[dict[str, Any]] = Field(default_factory=list)
    error: Optional[ToolError] = None
    is_partial: bool = False
    warnings: list[str] = Field(default_factory=list)
    execution_time_ms: float = 0.0
    attempts: int = 1
    evidence_ids: list[str] = Field(default_factory=list)

    def to_llm_payload(self, max_items: int = 40) -> dict[str, Any]:
        """Compact representation handed back to an LLM agent."""
        payload: dict[str, Any] = {
            "success": self.success,
            "is_partial": self.is_partial,
            "attempts": self.attempts,
        }
        if self.error:
            payload["error"] = {"code": self.error.code.value, "message": self.error.message}
            payload["note"] = (
                "The query FAILED. Absence of data is NOT evidence that the system is healthy. "
                "Record this as an evidence gap."
            )
        if self.warnings:
            payload["warnings"] = self.warnings
        if self.is_partial:
            payload["note"] = "Result is INCOMPLETE; some records are missing. Do not conclude absence."
        payload["data"] = self.data[:max_items]
        if len(self.data) > max_items:
            payload["truncated"] = f"{len(self.data) - max_items} more records omitted; narrow the query."
        return payload


# ---------------------------------------------------------------- tool inputs

class TimeWindow(BaseModel):
    start: datetime
    end: datetime

    @model_validator(mode="after")
    def _ordered(self) -> "TimeWindow":
        if self.end <= self.start:
            raise ValueError("time window end must be after start")
        return self


Severity = Literal["DEBUG", "INFO", "WARN", "ERROR", "FATAL"]


class LogQueryInput(BaseModel):
    service: Optional[str] = None
    severity: Optional[list[Severity]] = None
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    keyword: Optional[str] = None
    limit: int = Field(default=30, ge=1, le=200)


MetricName = Literal[
    "cpu_pct", "memory_pct", "request_rate", "error_rate", "p50_latency_ms", "p95_latency_ms",
    "p99_latency_ms", "db_conn_util_pct", "timeout_rate", "cache_hit_rate", "disk_io_wait_ms",
]


class MetricsQueryInput(BaseModel):
    service: str
    metrics: list[MetricName] = Field(min_length=1, max_length=6)
    start: datetime
    end: datetime
    baseline_start: Optional[datetime] = None
    baseline_end: Optional[datetime] = None

    @model_validator(mode="after")
    def _windows(self) -> "MetricsQueryInput":
        if self.end <= self.start:
            raise ValueError("end must be after start")
        if (self.baseline_start is None) != (self.baseline_end is None):
            raise ValueError("baseline_start and baseline_end must be provided together")
        if self.baseline_start and self.baseline_end and self.baseline_end <= self.baseline_start:
            raise ValueError("baseline_end must be after baseline_start")
        return self


class DeploymentQueryInput(BaseModel):
    service: Optional[str] = None
    start: Optional[datetime] = None
    end: Optional[datetime] = None


class ConfigQueryInput(BaseModel):
    service: Optional[str] = None
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    key: Optional[str] = None


class DependencyQueryInput(BaseModel):
    service: str
    direction: Literal["upstream", "downstream", "both"] = "both"
    depth: int = Field(default=2, ge=1, le=4)


class HistoricalQueryInput(BaseModel):
    symptoms: list[str] = Field(min_length=1)
    services: list[str] = Field(default_factory=list)
    limit: int = Field(default=3, ge=1, le=10)

    @field_validator("symptoms")
    @classmethod
    def _non_empty(cls, v: list[str]) -> list[str]:
        cleaned = [s.strip() for s in v if s and s.strip()]
        if not cleaned:
            raise ValueError("at least one non-empty symptom is required")
        return cleaned
