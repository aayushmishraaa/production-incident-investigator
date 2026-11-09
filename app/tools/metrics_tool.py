"""TOOL 2: metrics query with baseline comparison and onset detection."""
from __future__ import annotations

import statistics
from datetime import timedelta

from app.models.evidence import EvidenceRecord, Reliability, SourceType
from app.models.tool import MetricsQueryInput
from app.tools.base import BaseTool, PartialFn, ToolOutput
from app.tools.data_store import OperationalDataStore, parse_ts


def detect_onset(points: list[tuple], base_mean: float, base_std: float) -> str | None:
    """First timestamp where the value deviates strongly from baseline for 2 consecutive points."""
    threshold = max(4 * base_std, 0.3 * abs(base_mean), 1e-6)
    run = 0
    for i, (ts, v) in enumerate(points):
        if v is not None and abs(v - base_mean) > threshold:
            run += 1
            if run == 2:
                return points[i - 1][0]
        else:
            run = 0
    return None


class MetricsQueryTool(BaseTool):
    name = "query_metrics"
    description = (
        "Query time-series metrics for one service over [start,end] and compare against a baseline window "
        "(default: the 30 minutes before start). Metrics: cpu_pct, memory_pct, request_rate, error_rate (%), "
        "p50/p95/p99_latency_ms, db_conn_util_pct, timeout_rate (%), cache_hit_rate (%), disk_io_wait_ms. "
        "Returns per-metric baseline vs window stats, change %, detected onset time, missing datapoints and a "
        "5-minute sampled series. Each metric result has an evidence_id."
    )
    input_model = MetricsQueryInput

    def execute(self, inp: MetricsQueryInput, store: OperationalDataStore, partial: PartialFn) -> ToolOutput:
        svc_metrics = store.metrics.get(inp.service)
        if svc_metrics is None:
            raise ValueError(f"unknown service '{inp.service}'. Known: {sorted(store.metrics)}")
        start, end = parse_ts(inp.start), parse_ts(inp.end)
        b_start = parse_ts(inp.baseline_start) if inp.baseline_start else start - timedelta(minutes=30)
        b_end = parse_ts(inp.baseline_end) if inp.baseline_end else start

        data, evidence, warnings = [], [], []
        for metric in inp.metrics:
            series = svc_metrics.get(metric)
            if series is None:
                data.append({"metric": metric, "available": False, "note": f"{metric} not collected for {inp.service}"})
                continue
            pts = [(parse_ts(ts), v) for ts, v in series]
            window = [(ts, v) for ts, v in pts if start <= ts <= end]
            base = [v for ts, v in pts if b_start <= ts < b_end and v is not None]
            vals = [v for _, v in window if v is not None]
            missing = sum(1 for _, v in window if v is None)
            if not window:
                data.append({"metric": metric, "available": False, "note": "no datapoints in requested window"})
                continue
            if not vals:
                data.append({"metric": metric, "available": False, "missing_points": missing,
                             "note": "ALL datapoints missing in window (telemetry gap) - this is NOT evidence of health"})
                warnings.append(f"{inp.service}.{metric}: telemetry missing for entire window")
                continue
            b_mean = statistics.fmean(base) if base else None
            b_std = statistics.pstdev(base) if len(base) > 1 else 0.0
            w_mean, w_max = statistics.fmean(vals), max(vals)
            change = None if not b_mean else round((w_mean - b_mean) / b_mean * 100, 1)
            onset = detect_onset([(ts.strftime("%Y-%m-%dT%H:%M:%SZ"), v) for ts, v in window], b_mean, b_std) if b_mean is not None else None
            sampled = [[ts.strftime("%H:%M"), v] for i, (ts, v) in enumerate(window) if i % 5 == 0]
            eid = f"met-{inp.service}-{metric}-{start:%H%M}-{end:%H%M}"
            miss_frac = missing / len(window)
            rel = Reliability.LOW if miss_frac > 0.2 else (Reliability.MEDIUM if missing else Reliability.HIGH)
            row = {"metric": metric, "evidence_id": eid, "baseline_mean": _r(b_mean), "window_mean": _r(w_mean),
                   "window_max": _r(w_max), "window_min": _r(min(vals)), "change_pct": change, "onset": onset,
                   "missing_points": missing, "total_points": len(window), "sampled_series_5m": sampled}
            if missing:
                row["note"] = f"{missing}/{len(window)} datapoints missing (delayed or incomplete telemetry)"
                warnings.append(f"{inp.service}.{metric}: {missing} datapoints missing")
            data.append(row)
            desc = (f"{inp.service} {metric}: baseline {_r(b_mean)} -> window mean {_r(w_mean)} (max {_r(w_max)}, "
                    f"change {change}%), onset {onset or 'none detected'}"
                    + (f", {missing} points missing" if missing else ""))
            evidence.append(EvidenceRecord(
                evidence_id=eid, source_type=SourceType.METRIC, source_id=f"metrics:{inp.service}:{metric}",
                timestamp=parse_ts(onset) if onset else start, description=desc,
                value={"baseline_mean": _r(b_mean), "window_mean": _r(w_mean), "window_max": _r(w_max),
                       "change_pct": change, "onset": onset, "missing_points": missing},
                reliability=rel, service=inp.service))
        return ToolOutput(data=data, evidence=evidence, warnings=warnings)


def _r(v):
    return None if v is None else round(v, 2)
