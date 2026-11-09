"""Shared investigation state and configuration."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.models.agent import (
    AgentFinding, AgentMessage, AgentName, AgentStatus, InvestigationTask, new_id,
)
from app.models.evidence import EvidenceGap, EvidenceRecord
from app.models.hypothesis import CriticVerdict, Hypothesis
from app.models.incident import IncidentReport


class FinalStatus(str, Enum):
    RUNNING = "RUNNING"
    ROOT_CAUSE_IDENTIFIED = "ROOT_CAUSE_IDENTIFIED"
    PROBABLE_ROOT_CAUSE = "PROBABLE_ROOT_CAUSE"
    INCONCLUSIVE = "INCONCLUSIVE"
    INVESTIGATION_FAILED = "INVESTIGATION_FAILED"


class InvestigationConfig(BaseModel):
    max_rounds: int = Field(default=3, ge=1, le=10)
    max_tool_calls: int = Field(default=60, ge=1, le=1000)
    max_tool_retries: int = Field(default=2, ge=0, le=5)
    max_agent_retries: int = Field(default=1, ge=0, le=5)
    max_agent_steps: int = Field(default=6, ge=2, le=30)
    tool_timeout_s: float = Field(default=2.0, gt=0)
    investigation_timeout_s: float = Field(default=300.0, gt=0)
    max_llm_calls: int = Field(default=80, ge=1)
    max_cost_usd: float = Field(default=0.25, gt=0)
    approve_confidence: float = Field(default=0.6, ge=0, le=1)
    parallelism: int = Field(default=4, ge=1, le=16)
    random_failure_rate: float = Field(default=0.0, ge=0, le=1)
    seed: int = 7


class ToolCallRecord(BaseModel):
    call_id: str
    tool_name: str
    agent: str
    task_id: Optional[str] = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    success: bool
    is_partial: bool = False
    error_code: Optional[str] = None
    attempts: int = 1
    execution_time_ms: float = 0.0
    evidence_ids: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    llm_calls: int = 0
    cost_usd: float = 0.0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens + self.cache_read_tokens + self.cache_write_tokens

    def add(self, other: "TokenUsage") -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cache_read_tokens += other.cache_read_tokens
        self.cache_write_tokens += other.cache_write_tokens
        self.llm_calls += other.llm_calls
        self.cost_usd += other.cost_usd


class ExecutionStats(BaseModel):
    tool_calls: int = 0               # counts every attempt (including retries)
    tool_failures: int = 0
    tool_retries: int = 0
    partial_results: int = 0
    agent_failures: int = 0
    agent_retries: int = 0
    invalid_llm_outputs: int = 0
    tokens_available: bool = False    # False for the stub provider: no real token counts
    usage_total: TokenUsage = Field(default_factory=TokenUsage)
    usage_by_agent: dict[str, TokenUsage] = Field(default_factory=dict)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_s: float = 0.0
    termination_reason: str = ""


class TimelineEvent(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    actor: str
    event: str
    detail: dict[str, Any] = Field(default_factory=dict)


class InvestigationState(BaseModel):
    """Single source of truth shared by all agents during an investigation."""

    investigation_id: str = Field(default_factory=lambda: new_id("inv"))
    system: str = "multi_agent"
    incident: IncidentReport
    config: InvestigationConfig = Field(default_factory=InvestigationConfig)
    plan: dict[str, Any] = Field(default_factory=dict)
    tasks: list[InvestigationTask] = Field(default_factory=list)
    agent_status: dict[str, AgentStatus] = Field(default_factory=dict)
    messages: list[AgentMessage] = Field(default_factory=list)
    evidence: dict[str, EvidenceRecord] = Field(default_factory=dict)
    evidence_gaps: list[EvidenceGap] = Field(default_factory=list)
    findings: list[AgentFinding] = Field(default_factory=list)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    hypothesis_history: list[list[Hypothesis]] = Field(default_factory=list)
    critic_verdicts: list[CriticVerdict] = Field(default_factory=list)
    round: int = 1
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    stats: ExecutionStats = Field(default_factory=ExecutionStats)
    timeline: list[TimelineEvent] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    final_status: FinalStatus = FinalStatus.RUNNING
    report: Optional[dict[str, Any]] = None

    # ---- helpers -------------------------------------------------------
    def log(self, actor: str, event: str, **detail: Any) -> None:
        self.timeline.append(TimelineEvent(actor=actor, event=event, detail=detail))

    def task(self, task_id: str) -> InvestigationTask:
        for t in self.tasks:
            if t.task_id == task_id:
                return t
        raise KeyError(task_id)

    def tool_failures(self) -> list[ToolCallRecord]:
        return [c for c in self.tool_calls if not c.success or c.is_partial]

    def record_usage(self, agent: str, usage: TokenUsage) -> None:
        self.stats.usage_total.add(usage)
        self.stats.usage_by_agent.setdefault(agent, TokenUsage()).add(usage)

    def top_hypothesis(self) -> Optional[Hypothesis]:
        live = [h for h in self.hypotheses if h.status != "rejected"]
        return max(live, key=lambda h: h.confidence) if live else None

    def latest_verdict(self) -> Optional[CriticVerdict]:
        return self.critic_verdicts[-1] if self.critic_verdicts else None

    def agent_names(self) -> list[str]:
        return [a.value for a in AgentName]
