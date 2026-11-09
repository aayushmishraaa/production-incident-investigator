"""Agent-level schemas: tasks, messages and findings."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.models.evidence import EvidenceRef


def _now() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


class AgentName(str, Enum):
    ORCHESTRATOR = "orchestrator"
    OBSERVABILITY = "observability"
    DEPENDENCY = "dependency"
    REASONING = "reasoning"
    CRITIC = "critic"
    REPORTING = "reporting"
    SINGLE_AGENT = "single_agent"


class AgentStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class InvestigationTask(BaseModel):
    task_id: str = Field(default_factory=lambda: new_id("task"))
    agent: AgentName
    objective: str
    services: list[str] = Field(default_factory=list)
    focus: list[str] = Field(default_factory=list)   # e.g. ["logs","metrics"] or ["deployments","config"]
    depends_on: list[str] = Field(default_factory=list)
    round: int = 1
    status: TaskStatus = TaskStatus.PENDING
    attempts: int = 0
    error: Optional[str] = None
    created_by: AgentName = AgentName.ORCHESTRATOR
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class MessageType(str, Enum):
    TASK_ASSIGNMENT = "task_assignment"
    FINDINGS = "findings"
    HYPOTHESES = "hypotheses"
    CRITIC_VERDICT = "critic_verdict"
    EVIDENCE_REQUEST = "evidence_request"
    REPORT = "report"
    ERROR = "error"
    STATUS = "status"


class AgentMessage(BaseModel):
    message_id: str = Field(default_factory=lambda: new_id("msg"))
    investigation_id: str
    sender: AgentName
    recipient: AgentName
    message_type: MessageType
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=_now)
    status: str = "delivered"   # delivered | consumed
    in_reply_to: Optional[str] = None


class FindingKind(str, Enum):
    OBSERVED_FACT = "observed_fact"
    DERIVED_OBSERVATION = "derived_observation"
    POSSIBLE_EXPLANATION = "possible_explanation"
    MISSING_EVIDENCE = "missing_evidence"
    CONTRADICTION = "contradiction"


class AgentFinding(BaseModel):
    finding_id: str = Field(default_factory=lambda: new_id("fnd"))
    agent: AgentName
    task_id: Optional[str] = None
    kind: FindingKind
    statement: str
    service: Optional[str] = None
    timestamp: Optional[str] = None
    evidence: list[EvidenceRef] = Field(default_factory=list)
    round: int = 1


class AgentOutput(BaseModel):
    """What a specialist (observability / dependency) agent submits."""

    findings: list[AgentFinding] = Field(default_factory=list)
    earliest_symptom: Optional[str] = None
    summary: str = ""
    uncertainties: list[str] = Field(default_factory=list)
