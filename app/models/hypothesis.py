"""Hypotheses and critic verdicts."""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from app.models.evidence import EvidenceRef


class RootCauseCategory(str, Enum):
    """Generic root-cause taxonomy (not tied to any specific test incident)."""

    DB_CONNECTION_POOL_EXHAUSTION = "db_connection_pool_exhaustion"
    DEPLOYMENT_REGRESSION = "deployment_regression"
    UPSTREAM_DEPENDENCY_DEGRADATION = "upstream_dependency_degradation"
    RESOURCE_SATURATION = "resource_saturation"
    INFRASTRUCTURE_DEGRADATION = "infrastructure_degradation"
    CONFIGURATION_REGRESSION = "configuration_regression"
    CACHE_DEGRADATION = "cache_degradation"
    TRAFFIC_SURGE = "traffic_surge"
    UNKNOWN = "unknown"


class ScoreBreakdown(BaseModel):
    """Transparent, rule-based confidence components (NOT a calibrated probability)."""

    support: float = 0.0
    contradiction_penalty: float = 0.0
    temporal_precedence: float = 0.0
    reliability_penalty: float = 0.0
    gap_penalty: float = 0.0
    critic_adjustment: float = 0.0
    total: float = 0.0
    explanation: list[str] = Field(default_factory=list)


class Hypothesis(BaseModel):
    hypothesis_id: str
    category: RootCauseCategory
    culprit_service: Optional[str] = None
    description: str
    mechanism: str = ""
    supporting_evidence: list[EvidenceRef] = Field(default_factory=list)
    contradicting_evidence: list[EvidenceRef] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    recommended_investigation: list[str] = Field(default_factory=list)
    cause_time: Optional[str] = None       # ISO timestamp the proposed cause began
    confidence: float = 0.0               # computed by app.agents.scoring, never by the LLM
    score: ScoreBreakdown = Field(default_factory=ScoreBreakdown)
    status: str = "proposed"              # proposed | supported | rejected | needs_evidence
    round_proposed: int = 1

    def evidence_ids(self) -> set[str]:
        return {e.evidence_id for e in self.supporting_evidence + self.contradicting_evidence}


class VerdictType(str, Enum):
    APPROVED = "APPROVED"
    NEEDS_MORE_EVIDENCE = "NEEDS_MORE_EVIDENCE"
    REJECTED = "REJECTED"
    INCONCLUSIVE = "INCONCLUSIVE"


class PrecheckIssue(BaseModel):
    hypothesis_id: str
    check: str
    severity: str = Field(pattern="^(blocking|warning)$")
    detail: str


class EvidenceRequest(BaseModel):
    target_agent: str = Field(pattern="^(observability|dependency)$")
    request: str
    services: list[str] = Field(default_factory=list)
    reason: str = ""


class HypothesisAssessment(BaseModel):
    hypothesis_id: str
    decision: str = Field(pattern="^(accept|reject|needs_evidence)$")
    reasoning: str


class CriticVerdict(BaseModel):
    verdict: VerdictType
    summary: str
    assessments: list[HypothesisAssessment] = Field(default_factory=list)
    precheck_issues: list[PrecheckIssue] = Field(default_factory=list)
    unsupported_assumptions: list[str] = Field(default_factory=list)
    alternative_explanations: list[str] = Field(default_factory=list)
    evidence_requests: list[EvidenceRequest] = Field(default_factory=list)
    round: int = 1
