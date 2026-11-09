"""Transparent, rule-based hypothesis confidence scoring.

Confidence is an evidence-strength score in [0, 0.95]; it is NOT a calibrated
probability. Every component is recorded in Hypothesis.score.explanation.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from app.models.evidence import Reliability, SourceType
from app.models.hypothesis import Hypothesis, ScoreBreakdown
from app.models.investigation import InvestigationState
from app.tools.data_store import parse_ts

SUPPORT_W = {"strong": 0.22, "moderate": 0.12, "weak": 0.04}
CONTRA_W = {"strong": 0.30, "moderate": 0.15, "weak": 0.05}
REL_F = {Reliability.HIGH: 1.0, Reliability.MEDIUM: 0.8, Reliability.LOW: 0.5}
BASE = 0.10
SIGNIFICANT_CHANGE_PCT = 50.0


def observed_onset(state: InvestigationState) -> Optional[datetime]:
    """Earliest strong metric deviation in collected evidence (data-derived, not LLM-derived)."""
    onsets = []
    for rec in state.evidence.values():
        if rec.source_type != SourceType.METRIC or not isinstance(rec.value, dict):
            continue
        change, onset = rec.value.get("change_pct"), rec.value.get("onset")
        if onset and change is not None and abs(change) >= SIGNIFICANT_CHANGE_PCT:
            onsets.append(parse_ts(onset))
    return min(onsets) if onsets else None


def parse_optional(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return parse_ts(ts)
    except ValueError:
        return None


def score_hypothesis(h: Hypothesis, state: InvestigationState, critic_adjustment: float = 0.0) -> ScoreBreakdown:
    sb = ScoreBreakdown(critic_adjustment=critic_adjustment)
    expl = [f"base {BASE:.2f}"]
    invalid = 0
    source_types = set()
    for ref in h.supporting_evidence:
        rec = state.evidence.get(ref.evidence_id)
        if rec is None:
            invalid += 1
            continue
        w = SUPPORT_W[ref.strength] * REL_F[rec.reliability]
        if rec.source_type == SourceType.HISTORICAL:
            w *= 0.5   # analogy only
        sb.support += w
        source_types.add(rec.source_type)
        if rec.reliability != Reliability.HIGH:
            sb.reliability_penalty += SUPPORT_W[ref.strength] - w if rec.source_type != SourceType.HISTORICAL else 0
    sb.support = min(sb.support, 0.7)
    if len(source_types - {SourceType.HISTORICAL}) >= 2:
        sb.support += 0.08
        expl.append("+0.08 corroboration across >=2 independent source types")
    expl.append(f"+{sb.support:.2f} supporting evidence ({len(h.supporting_evidence)} refs, reliability-weighted, capped)")

    for ref in h.contradicting_evidence:
        rec = state.evidence.get(ref.evidence_id)
        if rec is None:
            invalid += 1
            continue
        sb.contradiction_penalty += CONTRA_W[ref.strength] * REL_F[rec.reliability]
    sb.contradiction_penalty = min(sb.contradiction_penalty, 0.45)
    if sb.contradiction_penalty:
        expl.append(f"-{sb.contradiction_penalty:.2f} contradicting evidence ({len(h.contradicting_evidence)} refs, capped 0.45)")

    onset = observed_onset(state)
    cause = parse_optional(h.cause_time)
    if onset and cause:
        if cause <= onset + timedelta(minutes=1):
            sb.temporal_precedence = 0.08
            expl.append(f"+0.08 proposed cause ({cause:%H:%M}) precedes/coincides with first observed anomaly ({onset:%H:%M})")
        else:
            sb.temporal_precedence = -0.30
            expl.append(f"-0.30 proposed cause ({cause:%H:%M}) is AFTER the first observed anomaly ({onset:%H:%M})")
    elif not cause:
        expl.append("+0.00 no cause time given; temporal precedence unverified")

    sb.gap_penalty = min(0.02 * len(h.missing_evidence), 0.08) + 0.05 * invalid
    failed_on_culprit = [c for c in state.tool_calls if (not c.success or c.is_partial)
                         and h.culprit_service and c.arguments.get("service") == h.culprit_service]
    if failed_on_culprit:
        sb.gap_penalty += 0.05
        expl.append(f"-0.05 tool failures/partial data for {h.culprit_service}")
    if invalid:
        expl.append(f"-{0.05 * invalid:.2f} {invalid} cited evidence id(s) do not exist")
    if h.missing_evidence:
        expl.append(f"-{min(0.02 * len(h.missing_evidence), 0.08):.2f} {len(h.missing_evidence)} acknowledged evidence gaps")
    if sb.reliability_penalty:
        expl.append(f"(reliability discount already applied: {sb.reliability_penalty:.2f})")
    if critic_adjustment:
        expl.append(f"{critic_adjustment:+.2f} critic review adjustment")

    total = BASE + sb.support - sb.contradiction_penalty + sb.temporal_precedence - sb.gap_penalty + critic_adjustment
    sb.total = round(max(0.0, min(total, 0.95)), 3)
    expl.append(f"= {sb.total:.2f} (evidence-strength score, not a calibrated probability)")
    sb.explanation = expl
    return sb


def rescore_all(state: InvestigationState, adjustments: Optional[dict[str, float]] = None) -> None:
    adjustments = adjustments or {}
    for h in state.hypotheses:
        adj = adjustments.get(h.hypothesis_id, h.score.critic_adjustment)
        h.score = score_hypothesis(h, state, adj)
        h.confidence = h.score.total
