"""Deterministic report assembly (JSON + Markdown).

Structured sections (status, hypotheses, evidence, timeline, gaps) come straight from
validated shared state; only narrative prose comes from the Reporting Agent.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from app.config import get_settings
from app.models.evidence import EvidenceLabel, Reliability, SourceType
from app.models.investigation import FinalStatus, InvestigationState
from app.models.report import INCONCLUSIVE_STATEMENT, InvestigationReport, LabelledStatement, ReportHypothesis


def _label_for(rec) -> str:
    if rec.source_type in (SourceType.DEPLOYMENT, SourceType.CONFIG, SourceType.DEPENDENCY) and rec.reliability == Reliability.HIGH:
        return EvidenceLabel.CONFIRMED_FACT.value
    if rec.source_type == SourceType.HISTORICAL:
        return EvidenceLabel.INFERENCE.value
    return EvidenceLabel.OBSERVED_EVIDENCE.value


def _ref_details(state: InvestigationState, refs) -> list[dict[str, Any]]:
    out = []
    for r in refs:
        rec = state.evidence.get(r.evidence_id)
        out.append({"evidence_id": r.evidence_id, "strength": r.strength, "note": r.note,
                    "exists": rec is not None,
                    "label": _label_for(rec) if rec else EvidenceLabel.UNKNOWN.value,
                    "description": rec.description if rec else "NOT FOUND in collected evidence"})
    return out


def validated_payload(state: InvestigationState) -> dict[str, Any]:
    """What the Reporting Agent receives: validated, already-decided results."""
    ranked = sorted(state.hypotheses, key=lambda h: (h.status == "rejected", -h.confidence))
    top = state.top_hypothesis() if state.final_status in (FinalStatus.ROOT_CAUSE_IDENTIFIED, FinalStatus.PROBABLE_ROOT_CAUSE) else None
    verdict = state.latest_verdict()
    return {
        "incident": state.incident.model_dump(mode="json"),
        "final_status": state.final_status.value,
        "leading_hypothesis": top.model_dump(mode="json", include={"category", "culprit_service", "description",
                                                                   "mechanism", "confidence"}) if top else None,
        "hypotheses": [{"id": h.hypothesis_id, "category": h.category.value, "service": h.culprit_service,
                        "description": h.description, "confidence": h.confidence, "status": h.status,
                        "supporting": [r.evidence_id for r in h.supporting_evidence],
                        "contradicting": [r.evidence_id for r in h.contradicting_evidence]} for h in ranked],
        "critic": verdict.model_dump(mode="json", include={"verdict", "summary", "unsupported_assumptions",
                                                           "alternative_explanations"}) if verdict else None,
        "key_evidence": {eid: state.evidence[eid].description for h in ranked[:2]
                         for eid in [r.evidence_id for r in h.supporting_evidence] if eid in state.evidence},
        "evidence_gaps": sorted({g.description for g in state.evidence_gaps})[:15],
        "termination_reason": state.stats.termination_reason,
    }


def build_timeline(state: InvestigationState) -> list[dict[str, Any]]:
    events = []
    for rec in state.evidence.values():
        if rec.timestamp is None:
            continue
        if rec.source_type in (SourceType.DEPLOYMENT, SourceType.CONFIG):
            events.append((rec.timestamp, _label_for(rec), rec.description, rec.evidence_id))
        elif rec.source_type == SourceType.METRIC and isinstance(rec.value, dict) and rec.value.get("onset") \
                and abs(rec.value.get("change_pct") or 0) >= 50:
            events.append((rec.timestamp, EvidenceLabel.OBSERVED_EVIDENCE.value,
                           f"Anomaly onset: {rec.description}", rec.evidence_id))
        elif rec.evidence_id.startswith("logpat-") and isinstance(rec.value, dict) and \
                any(s in rec.description for s in ("ERROR", "WARN")) and rec.value.get("count", 0) >= 3:
            events.append((rec.timestamp, EvidenceLabel.OBSERVED_EVIDENCE.value, f"First log: {rec.description}", rec.evidence_id))
    inc = state.incident
    events.append((inc.symptom_start, EvidenceLabel.CONFIRMED_FACT.value, "Reported symptom start", None))
    events.append((inc.reported_at, EvidenceLabel.CONFIRMED_FACT.value, "Incident reported", None))
    events.sort(key=lambda e: e[0])
    return [{"time": t.strftime("%Y-%m-%dT%H:%M:%SZ"), "label": lab, "event": d[:240], "evidence_id": eid}
            for t, lab, d, eid in events[:40]]


def build_report(state: InvestigationState, narrative) -> InvestigationReport:
    ranked = sorted(state.hypotheses, key=lambda h: (h.status == "rejected", -h.confidence))
    verdict = state.latest_verdict()
    decisions = {a.hypothesis_id: a.decision for a in verdict.assessments} if verdict else {}
    hyps = [ReportHypothesis(
        rank=i, hypothesis_id=h.hypothesis_id, category=h.category.value, culprit_service=h.culprit_service,
        description=f"{h.description} Mechanism: {h.mechanism}".strip(), confidence=h.confidence,
        confidence_explanation=h.score.explanation, supporting_evidence=_ref_details(state, h.supporting_evidence),
        contradicting_evidence=_ref_details(state, h.contradicting_evidence), missing_evidence=h.missing_evidence,
        critic_decision=decisions.get(h.hypothesis_id)) for i, h in enumerate(ranked, 1)]

    symptoms = []
    for rec in state.evidence.values():
        if rec.source_type == SourceType.METRIC and isinstance(rec.value, dict) and abs(rec.value.get("change_pct") or 0) >= 50:
            symptoms.append(LabelledStatement(label=_label_for(rec), statement=rec.description, evidence_ids=[rec.evidence_id]))
    for f in state.findings:
        if f.kind.value == "observed_fact" and len(symptoms) < 25:
            symptoms.append(LabelledStatement(label=EvidenceLabel.OBSERVED_EVIDENCE.value, statement=f"[{f.agent.value}] {f.statement}",
                                              evidence_ids=[e.evidence_id for e in f.evidence]))
        elif f.kind.value == "possible_explanation" and len(symptoms) < 25:
            symptoms.append(LabelledStatement(label=EvidenceLabel.INFERENCE.value, statement=f"[{f.agent.value}] {f.statement}",
                                              evidence_ids=[e.evidence_id for e in f.evidence]))
    if verdict:
        symptoms += [LabelledStatement(label=EvidenceLabel.ASSUMPTION.value, statement=f"[critic: unsupported assumption] {a}")
                     for a in verdict.unsupported_assumptions[:5]]

    performed = []
    for t in state.tasks:
        n_calls = sum(1 for c in state.tool_calls if c.task_id == t.task_id)
        performed.append(f"Round {t.round} | {t.agent.value} | {t.status.value} | attempts {t.attempts} | "
                         f"{n_calls} tool calls | {t.objective[:160]}")

    status = state.final_status
    top = state.top_hypothesis()
    probable: Optional[dict[str, Any]] = None
    if status in (FinalStatus.ROOT_CAUSE_IDENTIFIED, FinalStatus.PROBABLE_ROOT_CAUSE) and top:
        probable = {"hypothesis_id": top.hypothesis_id, "category": top.category.value,
                    "culprit_service": top.culprit_service, "description": top.description,
                    "confidence": top.confidence,
                    "label": ("ROOT CAUSE IDENTIFIED (critic-approved; still an INFERENCE from evidence)"
                              if status == FinalStatus.ROOT_CAUSE_IDENTIFIED else
                              "MOST PROBABLE EXPLANATION (INFERENCE, not confirmed)")}
        statement = f"{probable['label']}: {top.category.value} in {top.culprit_service} - {top.description}"
    else:
        statement = INCONCLUSIVE_STATEMENT

    gaps = sorted({f"[UNKNOWN] {g.description} ({g.reason})" for g in state.evidence_gaps})
    limitations = list(narrative.limitations)
    fails = state.tool_failures()
    if fails:
        limitations.append(f"{sum(1 for c in fails if not c.success)} tool calls failed and {sum(1 for c in fails if c.is_partial)} "
                           "returned partial data; affected areas are treated as unknown, not healthy.")
    failed_tasks = [t for t in state.tasks if t.status.value == "failed"]
    if failed_tasks:
        limitations.append(f"{len(failed_tasks)} agent task(s) failed: " + "; ".join(f"{t.agent.value}: {t.error}"[:120] for t in failed_tasks))
    limitations.append("Confidence values are rule-based evidence-strength scores, not calibrated probabilities.")
    if state.stats.termination_reason:
        limitations.append(f"Investigation terminated because: {state.stats.termination_reason}")

    conclusion = narrative.conclusion
    if status in (FinalStatus.INCONCLUSIVE, FinalStatus.INVESTIGATION_FAILED) and INCONCLUSIVE_STATEMENT not in conclusion:
        conclusion = f"{INCONCLUSIVE_STATEMENT} {conclusion}"

    st = state.stats
    stats = {"rounds": state.round, "tool_calls": st.tool_calls, "tool_failures": st.tool_failures,
             "tool_retries": st.tool_retries, "partial_results": st.partial_results, "agent_failures": st.agent_failures,
             "agent_retries": st.agent_retries, "invalid_llm_outputs": st.invalid_llm_outputs,
             "messages_exchanged": len(state.messages), "evidence_records": len(state.evidence),
             "duration_s": round(st.duration_s, 2),
             "tokens": st.usage_total.model_dump() if st.tokens_available else "unavailable (stub LLM: no real token usage)",
             "tokens_by_agent": {k: v.model_dump() for k, v in st.usage_by_agent.items()} if st.tokens_available else None}

    return InvestigationReport(
        investigation_id=state.investigation_id, system=state.system, incident_id=state.incident.incident_id,
        title=state.incident.title, severity=state.incident.severity, affected_services=state.incident.affected_services,
        start_time=state.incident.symptom_start.isoformat(), executive_summary=narrative.executive_summary,
        timeline=build_timeline(state), observed_symptoms=symptoms, investigation_performed=performed,
        hypotheses=hyps, critic_review=(verdict.model_dump(mode="json") if verdict else {"verdict": "NOT_RUN"})
        | {"rounds_reviewed": len(state.critic_verdicts)},
        evidence_gaps=gaps, probable_root_cause=probable, root_cause_statement=statement,
        corrective_actions=narrative.corrective_actions, preventive_actions=narrative.preventive_actions,
        monitoring_recommendations=narrative.monitoring_recommendations, limitations=limitations,
        final_status=status, conclusion=conclusion, statistics=stats)


def to_markdown(r: InvestigationReport) -> str:
    L = [f"# Production Incident Investigation Report", "",
         "## Incident Information",
         f"- **Incident ID:** {r.incident_id}", f"- **Title:** {r.title}", f"- **Severity:** {r.severity}",
         f"- **Affected services:** {', '.join(r.affected_services)}", f"- **Start time:** {r.start_time}",
         f"- **Investigation ID:** {r.investigation_id} ({r.system})", f"- **Final status:** `{r.final_status.value}`", "",
         "## Executive Summary", r.executive_summary, "",
         "## Incident Timeline", "| Time (UTC) | Label | Event | Evidence |", "|---|---|---|---|"]
    L += [f"| {e['time']} | {e['label']} | {e['event'].replace('|', '/')} | {e['evidence_id'] or ''} |" for e in r.timeline]
    L += ["", "## Observed Symptoms"]
    L += [f"- **{s.label}:** {s.statement} {('(' + ', '.join(s.evidence_ids) + ')') if s.evidence_ids else ''}" for s in r.observed_symptoms]
    L += ["", "## Investigation Performed"] + [f"- {p}" for p in r.investigation_performed]
    L += ["", "## Root-Cause Hypotheses (ranked by evidence strength)"]
    for h in r.hypotheses:
        L += [f"### {h.rank}. {h.hypothesis_id} - `{h.category}` in `{h.culprit_service}` (confidence {h.confidence:.2f}, critic: {h.critic_decision or 'n/a'})",
              f"**INFERENCE:** {h.description}", "", "Confidence breakdown: " + "; ".join(h.confidence_explanation), "",
              "Supporting evidence:"]
        L += [f"- [{e['label']}] `{e['evidence_id']}` ({e['strength']}): {e['description'][:220]}" for e in h.supporting_evidence] or ["- none"]
        L += ["", "Contradicting evidence:"]
        L += [f"- [{e['label']}] `{e['evidence_id']}` ({e['strength']}): {e['description'][:220]}" for e in h.contradicting_evidence] or ["- none"]
        if h.missing_evidence:
            L += ["", "Remaining uncertainties / missing evidence:"] + [f"- [UNKNOWN] {m}" for m in h.missing_evidence]
        L.append("")
    cr = r.critic_review
    L += ["## Critic Review", f"- **Verdict:** `{cr.get('verdict')}` (rounds reviewed: {cr.get('rounds_reviewed')})",
          f"- **Reasoning:** {cr.get('summary', '')}"]
    for a in cr.get("assessments", []) or []:
        L.append(f"- {a['hypothesis_id']}: **{a['decision']}** - {a['reasoning']}")
    for i in cr.get("precheck_issues", []) or []:
        L.append(f"- pre-check {i['severity']} `{i['check']}` on {i['hypothesis_id']}: {i['detail']}")
    for a in cr.get("alternative_explanations", []) or []:
        L.append(f"- alternative: {a}")
    L += ["", "## Probable Root Cause", r.root_cause_statement, "",
          "## Corrective Actions"] + [f"- {a}" for a in r.corrective_actions]
    L += ["", "## Preventive Actions"] + [f"- {a}" for a in r.preventive_actions]
    L += ["", "## Monitoring Recommendations"] + [f"- {a}" for a in r.monitoring_recommendations]
    L += ["", "## Evidence Gaps"] + ([f"- {g}" for g in r.evidence_gaps] or ["- none recorded"])
    L += ["", "## Limitations"] + [f"- {x}" for x in r.limitations]
    L += ["", "## Final Status", f"`{r.final_status.value}`", "", r.conclusion, "",
          "## Execution Statistics", "```json", json.dumps(r.statistics, indent=2, default=str), "```", ""]
    return "\n".join(L)


def save_report(r: InvestigationReport, out_dir: Optional[Path] = None) -> tuple[Path, Path]:
    out_dir = out_dir or get_settings().results_dir / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{r.incident_id}_{r.system}_{r.investigation_id}"
    jp, mp = out_dir / f"{stem}.json", out_dir / f"{stem}.md"
    jp.write_text(r.model_dump_json(indent=2))
    mp.write_text(to_markdown(r))
    return jp, mp
