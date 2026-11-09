"""Final investigation report schema."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from app.models.investigation import FinalStatus

INCONCLUSIVE_STATEMENT = "Root cause could not be conclusively established with the available evidence."


class LabelledStatement(BaseModel):
    label: str   # CONFIRMED FACT | OBSERVED EVIDENCE | INFERENCE | ASSUMPTION | UNKNOWN
    statement: str
    evidence_ids: list[str] = Field(default_factory=list)


class ReportHypothesis(BaseModel):
    rank: int
    hypothesis_id: str
    category: str
    culprit_service: Optional[str]
    description: str
    confidence: float
    confidence_explanation: list[str]
    supporting_evidence: list[dict[str, Any]]
    contradicting_evidence: list[dict[str, Any]]
    missing_evidence: list[str]
    critic_decision: Optional[str] = None


class InvestigationReport(BaseModel):
    investigation_id: str
    system: str
    incident_id: str
    title: str
    severity: str
    affected_services: list[str]
    start_time: str
    executive_summary: str
    timeline: list[dict[str, Any]]
    observed_symptoms: list[LabelledStatement]
    investigation_performed: list[str]
    hypotheses: list[ReportHypothesis]
    critic_review: dict[str, Any]
    evidence_gaps: list[str]
    probable_root_cause: Optional[dict[str, Any]]
    root_cause_statement: str
    corrective_actions: list[str]
    preventive_actions: list[str]
    monitoring_recommendations: list[str]
    limitations: list[str]
    final_status: FinalStatus
    conclusion: str
    statistics: dict[str, Any] = Field(default_factory=dict)
