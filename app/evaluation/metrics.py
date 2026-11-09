"""Evaluation metric calculations (pure functions; unit-tested)."""
from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from typing import Any, Iterable, Optional

from app.models.investigation import FinalStatus, InvestigationState

INCONCLUSIVE = "inconclusive"
DIAGNOSED = {FinalStatus.ROOT_CAUSE_IDENTIFIED, FinalStatus.PROBABLE_ROOT_CAUSE}


# ------------------------------------------------------------------ per-run scoring
def prediction(state: InvestigationState) -> tuple[str, Optional[str]]:
    if state.final_status in DIAGNOSED:
        top = state.top_hypothesis()
        if top is not None and top.category.value != "unknown":
            return top.category.value, top.culprit_service
    return INCONCLUSIVE, None


def correctness(pred_cat: str, pred_svc: Optional[str], gt: dict[str, Any]) -> dict[str, bool]:
    if gt.get("expected_inconclusive"):
        correct = pred_cat == INCONCLUSIVE
        strict = correct
    else:
        correct = pred_cat == gt["root_cause_category"]
        strict = correct and pred_svc == gt["culprit_service"]
    behaviour = correct or (gt.get("acceptable_inconclusive", False) and pred_cat == INCONCLUSIVE)
    return {"correct": correct, "strict_correct": strict, "behaviour_correct": behaviour}


def _expanded_citations(state: InvestigationState, ids: Iterable[str]) -> set[str]:
    out = set()
    for i in ids:
        out.add(i)
        rec = state.evidence.get(i)
        if rec is not None and isinstance(rec.value, dict) and rec.value.get("log_ids"):
            out.update(rec.value["log_ids"])
    return out


def grounding(state: InvestigationState, gt: dict[str, Any]) -> dict[str, Any]:
    cited = [r.evidence_id for h in state.hypotheses for r in h.supporting_evidence + h.contradicting_evidence]
    valid = [i for i in cited if i in state.evidence]
    unsupported = sum(1 for h in state.hypotheses
                      if not any(r.evidence_id in state.evidence for r in h.supporting_evidence))
    top = state.top_hypothesis()
    top_support = [r.evidence_id for r in top.supporting_evidence if r.evidence_id in state.evidence] if top else []
    on_culprit = [i for i in top_support if state.evidence[i].service == top.culprit_service] if top else []
    support_ids = [r.evidence_id for h in state.hypotheses for r in h.supporting_evidence]
    expanded = _expanded_citations(state, support_ids)
    keys = list(gt.get("key_evidence_ids", []))
    prefixes = list(gt.get("key_metric_prefixes", []))
    hits = sum(1 for k in keys if k in expanded) + sum(1 for p in prefixes if any(i.startswith(p) for i in expanded))
    n_keys = len(keys) + len(prefixes)
    decoys = set(gt.get("decoy_evidence_ids", []))
    pred_cat, _ = prediction(state)
    decoy_supported_top = bool(top and decoys & {r.evidence_id for r in top.supporting_evidence}) \
        and state.final_status in DIAGNOSED
    decoy_handled = None
    if gt.get("decoy_category") or decoys:
        decoy_handled = not decoy_supported_top and pred_cat != gt.get("decoy_category")
    return {
        "citations_total": len(cited),
        "citations_valid": len(valid),
        "citation_validity": round(len(valid) / len(cited), 4) if cited else None,
        "hallucinated_citations": len(cited) - len(valid),
        "top_citation_accuracy": round(len(on_culprit) / len(top_support), 4) if top_support else None,
        "hypotheses": len(state.hypotheses),
        "unsupported_hypotheses": unsupported,
        "hypotheses_with_contradictions": sum(1 for h in state.hypotheses if h.contradicting_evidence),
        "key_evidence_recall": round(hits / n_keys, 4) if n_keys else None,
        "decoy_handled": decoy_handled,
    }


def completeness(state: InvestigationState, behaviour_correct: bool, grounding_row: dict[str, Any]) -> dict[str, Any]:
    tools_used = {c.tool_name for c in state.tool_calls if c.success}
    checks = {
        "investigated_sources": len(tools_used) / 6,
        "competing_hypotheses": len(state.hypotheses) >= 2,
        "addressed_contradictions": grounding_row["hypotheses_with_contradictions"] > 0,
        "identified_missing_evidence": any(h.missing_evidence for h in state.hypotheses) or bool(state.evidence_gaps),
        "defensible_conclusion": behaviour_correct and grounding_row["hallucinated_citations"] == 0,
    }
    score = statistics.fmean([checks["investigated_sources"]] + [float(v) for k, v in checks.items() if k != "investigated_sources"])
    return {**{f"cmp_{k}": v for k, v in checks.items()}, "completeness_score": round(score, 4)}


def run_record(state: InvestigationState, gt: dict[str, Any], run: int) -> dict[str, Any]:
    pred_cat, pred_svc = prediction(state)
    corr = correctness(pred_cat, pred_svc, gt)
    g = grounding(state, gt)
    st = state.stats
    tokens = st.usage_total
    return {
        "system": state.system, "incident_id": state.incident.incident_id, "run": run,
        "investigation_id": state.investigation_id, "final_status": state.final_status.value,
        "predicted_category": pred_cat, "predicted_service": pred_svc,
        "gt_category": INCONCLUSIVE if gt.get("expected_inconclusive") else gt["root_cause_category"],
        "gt_service": gt["culprit_service"], **corr,
        "diagnosed": pred_cat != INCONCLUSIVE, "rounds": state.round,
        "duration_s": round(st.duration_s, 3), "tool_calls": st.tool_calls, "tool_failures": st.tool_failures,
        "tool_retries": st.tool_retries, "partial_results": st.partial_results,
        "agent_failures": st.agent_failures, "invalid_llm_outputs": st.invalid_llm_outputs,
        "messages": len(state.messages), "tokens_available": st.tokens_available,
        "llm_calls": tokens.llm_calls,
        "input_tokens": tokens.input_tokens + tokens.cache_read_tokens + tokens.cache_write_tokens if st.tokens_available else None,
        "output_tokens": tokens.output_tokens if st.tokens_available else None,
        "total_tokens": tokens.total_tokens if st.tokens_available else None,
        "cost_usd": round(tokens.cost_usd, 6) if st.tokens_available else None,
        "tokens_by_agent": {k: v.total_tokens for k, v in st.usage_by_agent.items()} if st.tokens_available else None,
        **g, **completeness(state, corr["behaviour_correct"], g),
        "termination_reason": st.termination_reason,
    }


# ------------------------------------------------------------------ aggregation
def _pct(values: list[float], q: float) -> Optional[float]:
    if not values:
        return None
    s = sorted(values)
    k = (len(s) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return round(s[lo] + (s[hi] - s[lo]) * (k - lo), 3)


def classification_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Macro precision/recall/F1 over root-cause categories; inconclusive = abstention."""
    classes = sorted({r["gt_category"] for r in rows if r["gt_category"] != INCONCLUSIVE})
    per = {}
    for c in classes:
        tp = sum(1 for r in rows if r["predicted_category"] == c and r["gt_category"] == c)
        fp = sum(1 for r in rows if r["predicted_category"] == c and r["gt_category"] != c)
        fn = sum(1 for r in rows if r["gt_category"] == c and r["predicted_category"] != c)
        p = tp / (tp + fp) if tp + fp else None
        rcl = tp / (tp + fn) if tp + fn else None
        f1 = 2 * p * rcl / (p + rcl) if p and rcl else (0.0 if p is not None and rcl is not None else None)
        per[c] = {"precision": p, "recall": rcl, "f1": f1, "support": tp + fn}
    def macro(key: str) -> Optional[float]:
        vals = [v[key] for v in per.values() if v[key] is not None]
        return round(statistics.fmean(vals), 4) if vals else None
    return {"per_class": per, "macro_precision": macro("precision"), "macro_recall": macro("recall"), "macro_f1": macro("f1")}


def confusion(rows: list[dict[str, Any]]) -> dict[str, Any]:
    labels = sorted({r["gt_category"] for r in rows} | {r["predicted_category"] for r in rows})
    m = {g: Counter() for g in labels}
    for r in rows:
        m[r["gt_category"]][r["predicted_category"]] += 1
    return {"labels": labels, "matrix": [[m[g][p] for p in labels] for g in labels]}


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {}
    n = len(rows)
    diag = [r for r in rows if r["diagnosed"]]
    durations = [r["duration_s"] for r in rows]
    tok = [r["total_tokens"] for r in rows if r["total_tokens"] is not None]
    by_run = defaultdict(list)
    for r in rows:
        by_run[r["run"]].append(r["correct"])
    run_acc = [statistics.fmean(v) for v in by_run.values()]
    mean = lambda key: round(statistics.fmean([r[key] for r in rows if r[key] is not None]), 4) \
        if any(r[key] is not None for r in rows) else None  # noqa: E731
    agent_tokens: dict[str, list[int]] = defaultdict(list)
    for r in rows:
        for a, t in (r["tokens_by_agent"] or {}).items():
            agent_tokens[a].append(t)
    decoys = [r["decoy_handled"] for r in rows if r["decoy_handled"] is not None]
    successful = [r for r in rows if r["correct"]]
    return {
        "runs": n,
        "correct": sum(r["correct"] for r in rows),
        "incorrect": sum(1 for r in rows if not r["correct"] and r["diagnosed"]),
        "inconclusive": sum(1 for r in rows if not r["diagnosed"]),
        "accuracy": round(sum(r["correct"] for r in rows) / n, 4),
        "accuracy_run_std": round(statistics.pstdev(run_acc), 4) if len(run_acc) > 1 else 0.0,
        "strict_accuracy": round(sum(r["strict_correct"] for r in rows) / n, 4),
        "behaviour_accuracy": round(sum(r["behaviour_correct"] for r in rows) / n, 4),
        "coverage": round(len(diag) / n, 4),
        "accuracy_when_diagnosed": round(sum(r["correct"] for r in diag) / len(diag), 4) if diag else None,
        **{k: v for k, v in classification_metrics(rows).items() if k != "per_class"},
        "citation_validity": mean("citation_validity"),
        "hallucinated_citations_total": sum(r["hallucinated_citations"] for r in rows),
        "top_citation_accuracy": mean("top_citation_accuracy"),
        "unsupported_hypotheses_rate": round(sum(r["unsupported_hypotheses"] for r in rows) /
                                             max(1, sum(r["hypotheses"] for r in rows)), 4),
        "key_evidence_recall": mean("key_evidence_recall"),
        "decoy_handling_rate": round(statistics.fmean(decoys), 4) if decoys else None,
        "contradiction_coverage": round(sum(r["hypotheses_with_contradictions"] for r in rows) /
                                        max(1, sum(r["hypotheses"] for r in rows)), 4),
        "tool_calls_total": sum(r["tool_calls"] for r in rows),
        "tool_calls_mean": round(statistics.fmean(r["tool_calls"] for r in rows), 2),
        "tool_failures_total": sum(r["tool_failures"] for r in rows),
        "tool_retries_total": sum(r["tool_retries"] for r in rows),
        "tool_calls_per_successful_investigation": round(statistics.fmean(r["tool_calls"] for r in successful), 2) if successful else None,
        "latency_mean_s": round(statistics.fmean(durations), 3),
        "latency_median_s": round(statistics.median(durations), 3),
        "latency_p95_s": _pct(durations, 0.95) if n >= 10 else None,
        "latency_total_s": round(sum(durations), 2),
        "tokens_available": bool(tok),
        "tokens_total": sum(tok) if tok else None,
        "tokens_mean": round(statistics.fmean(tok), 1) if tok else None,
        "input_tokens_total": sum(r["input_tokens"] for r in rows if r["input_tokens"] is not None) if tok else None,
        "output_tokens_total": sum(r["output_tokens"] for r in rows if r["output_tokens"] is not None) if tok else None,
        "cost_usd_total": round(sum(r["cost_usd"] or 0 for r in rows), 4) if tok else None,
        "tokens_by_agent_mean": {a: round(statistics.fmean(v), 1) for a, v in agent_tokens.items()} or None,
        "llm_calls_mean": round(statistics.fmean(r["llm_calls"] for r in rows), 2),
        "completeness_score": mean("completeness_score"),
        "judge_score_mean": mean("judge_score") if "judge_score" in rows[0] else None,
        "per_class": classification_metrics(rows)["per_class"],
        "confusion": confusion(rows),
    }
