"""Runs both systems over the synthetic incidents and produces evaluation artefacts."""
from __future__ import annotations

import asyncio
import csv
import json
import logging
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.config import get_settings
from app.evaluation.ground_truth import all_ground_truth
from app.evaluation.metrics import run_record, summarize
from app.evaluation.multi_agent import run_multi_agent
from app.evaluation.single_agent import run_single_agent
from app.evaluation.visualisation import make_charts
from app.llm.provider import CostLedger, LLMProvider, build_provider
from app.models.incident import IncidentReport
from app.models.investigation import InvestigationConfig, InvestigationState
from app.reporting.report_generator import to_markdown
from app.models.report import InvestigationReport
from app.storage.repository import InvestigationRepository
from app.tools.data_store import list_incident_reports

logger = logging.getLogger("evaluator")

SYSTEMS = {"multi_agent": run_multi_agent, "single_agent": run_single_agent}


class JudgeGrade(BaseModel):
    score: int = Field(ge=1, le=5)
    rationale: str


JUDGE_SYSTEM = """You grade incident investigation reports against a hidden ground truth.
Score the EXPLANATION quality 1-5: 5 = correct cause and mechanism with sound evidence-based reasoning and appropriate certainty; 3 = partially correct or correct but poorly justified / over-confident; 1 = wrong cause or fabricated reasoning. If the ground truth says an inconclusive result is expected or acceptable, a well-justified inconclusive report can score 4-5. Call submit_grade."""


async def judge(llm: LLMProvider, report: dict[str, Any], gt: dict[str, Any]) -> Optional[JudgeGrade]:
    if not llm.tokens_available:
        return None
    payload = {"ground_truth": {k: gt[k] for k in ("root_cause_category", "culprit_service", "description",
                                                   "expected_behaviour", "acceptable_inconclusive")},
               "report": {"final_status": report["final_status"], "root_cause_statement": report["root_cause_statement"],
                          "executive_summary": report["executive_summary"][:1500],
                          "hypotheses": [{k: h[k] for k in ("rank", "category", "culprit_service", "description", "confidence")}
                                         for h in report["hypotheses"][:4]],
                          "conclusion": report["conclusion"][:1000]}}
    schema = JudgeGrade.model_json_schema()
    schema.pop("title", None)
    try:
        resp = await llm.complete(agent="judge", system=JUDGE_SYSTEM, max_tokens=1000,
                                  messages=[{"role": "user", "content": json.dumps(payload, default=str)}],
                                  tools=[{"name": "submit_grade", "description": "Submit the grade", "input_schema": schema}])
        call = next((c for c in resp.tool_calls if c.name == "submit_grade"), None)
        return JudgeGrade.model_validate(call.input) if call else None
    except Exception as e:  # noqa: BLE001 - judge is optional/secondary
        logger.warning("judge failed: %r", e)
        return None


class Evaluator:
    def __init__(self, provider: Optional[str] = None, runs: int = 1, incidents: Optional[list[str]] = None,
                 systems: Optional[list[str]] = None, concurrency: int = 4, config: Optional[InvestigationConfig] = None,
                 out_dir: Optional[Path] = None, use_judge: bool = True, save_db: bool = True):
        self.settings = get_settings()
        self.provider_name = provider or self.settings.llm_provider
        self.runs = runs
        self.incident_filter = incidents
        self.systems = systems or list(SYSTEMS)
        self.concurrency = concurrency
        self.config = config or InvestigationConfig()
        self.out_dir = out_dir or self.settings.results_dir / "evaluation"
        self.use_judge = use_judge
        self.repo = InvestigationRepository() if save_db else None
        self.ledger = CostLedger()

    async def run(self) -> dict[str, Any]:
        gts = all_ground_truth()
        incidents = [IncidentReport(**r) for r in list_incident_reports()
                     if not self.incident_filter or r["incident_id"] in self.incident_filter]
        jobs = [(run, inc, sysname) for run in range(1, self.runs + 1) for inc in incidents for sysname in self.systems]
        random.Random(42).shuffle(jobs)  # interleave systems so load affects both equally
        sem = asyncio.Semaphore(self.concurrency)
        rows: list[dict[str, Any]] = []
        skipped: list[str] = []
        runs_dir = self.out_dir / "runs"
        runs_dir.mkdir(parents=True, exist_ok=True)
        ckpt = self.out_dir / "runs.jsonl"
        ckpt.write_text("")
        started = time.perf_counter()

        async def one(run: int, inc: IncidentReport, sysname: str) -> None:
            async with sem:
                if self.provider_name == "anthropic" and self.ledger.total() >= self.ledger.cap * 0.97:
                    skipped.append(f"{sysname}/{inc.incident_id}/run{run}: global cost cap reached")
                    return
                llm = build_provider(self.provider_name)
                cfg = self.config.model_copy(update={"seed": self.config.seed + run})
                state: InvestigationState = await SYSTEMS[sysname](inc, llm, cfg)
                gt = gts[inc.incident_id]
                row = run_record(state, gt, run)
                grade = await judge(llm, state.report, gt) if (self.use_judge and state.report) else None
                row["judge_score"] = grade.score if grade else None
                row["judge_rationale"] = grade.rationale if grade else None
                rows.append(row)
                stem = f"{inc.incident_id}_{sysname}_run{run}"
                (runs_dir / f"{stem}.json").write_text(json.dumps(state.report, indent=2, default=str))
                (runs_dir / f"{stem}.md").write_text(to_markdown(InvestigationReport.model_validate(state.report)))
                with open(ckpt, "a") as fh:
                    fh.write(json.dumps(row, default=str) + "\n")
                if self.repo:
                    self.repo.save(state)
                logger.info("%s %s run%d -> %s (%s) correct=%s %.1fs", sysname, inc.incident_id, run,
                            row["final_status"], row["predicted_category"], row["correct"], row["duration_s"])
                print(f"[{len(rows)}/{len(jobs)}] {sysname:12s} {inc.incident_id} run{run}: {row['final_status']:22s} "
                      f"pred={row['predicted_category']:32s} gt={row['gt_category']:32s} "
                      f"{'OK ' if row['correct'] else 'BAD'} {row['duration_s']:.1f}s spend=${self.ledger.total():.3f}",
                      flush=True)

        await asyncio.gather(*(one(*j) for j in jobs))
        return self.write_outputs(rows, skipped, time.perf_counter() - started)

    def write_outputs(self, rows: list[dict[str, Any]], skipped: list[str], wall_s: float) -> dict[str, Any]:
        rows.sort(key=lambda r: (r["system"], r["incident_id"], r["run"]))
        summaries = {s: summarize([r for r in rows if r["system"] == s]) for s in self.systems
                     if any(r["system"] == s for r in rows)}
        result = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "conditions": {"provider": self.provider_name, "model": self.settings.model if self.provider_name == "anthropic" else "stub",
                           "effort": self.settings.effort, "runs_per_incident": self.runs,
                           "incidents": sorted({r["incident_id"] for r in rows}), "concurrency": self.concurrency,
                           "config": self.config.model_dump(), "wall_clock_s": round(wall_s, 1),
                           "global_spend_usd_after": round(self.ledger.total(), 4),
                           "token_note": None if self.provider_name == "anthropic" else
                           "stub provider: real token consumption unavailable"},
            "summary": summaries, "skipped": skipped, "runs": rows,
        }
        self.out_dir.mkdir(parents=True, exist_ok=True)
        (self.out_dir / "evaluation_results.json").write_text(json.dumps(result, indent=2, default=str))
        with open(self.out_dir / "evaluation_runs.csv", "w", newline="") as fh:
            cols = [k for k in rows[0] if k not in ("tokens_by_agent", "judge_rationale")] if rows else []
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        (self.out_dir / "summary_table.md").write_text(summary_table(summaries))
        make_charts(rows, summaries, self.settings.results_dir / "charts")
        return result


TABLE_METRICS = [
    ("accuracy", "Root-cause accuracy (category)"), ("accuracy_run_std", "Accuracy std across runs"),
    ("strict_accuracy", "Strict accuracy (category+service)"), ("behaviour_accuracy", "Expected-behaviour accuracy"),
    ("coverage", "Coverage (diagnosis produced)"), ("accuracy_when_diagnosed", "Accuracy when diagnosed"),
    ("correct", "Correct"), ("incorrect", "Incorrect (wrong diagnosis)"), ("inconclusive", "Inconclusive"),
    ("macro_precision", "Macro precision"), ("macro_recall", "Macro recall"), ("macro_f1", "Macro F1"),
    ("citation_validity", "Evidence citation validity"), ("hallucinated_citations_total", "Hallucinated citations"),
    ("top_citation_accuracy", "Top-hypothesis citation accuracy"), ("unsupported_hypotheses_rate", "Unsupported hypotheses rate"),
    ("key_evidence_recall", "Ground-truth key evidence recall"), ("decoy_handling_rate", "Decoy/misleading evidence handled"),
    ("contradiction_coverage", "Hypotheses with contradicting evidence"), ("completeness_score", "Investigation completeness"),
    ("judge_score_mean", "LLM-judge explanation score (1-5)"),
    ("tool_calls_mean", "Tool calls / investigation"), ("tool_calls_total", "Tool calls total"),
    ("tool_failures_total", "Failed tool calls"), ("tool_retries_total", "Retried tool calls"),
    ("tool_calls_per_successful_investigation", "Tool calls / successful investigation"),
    ("latency_mean_s", "Latency mean (s)"), ("latency_median_s", "Latency median (s)"), ("latency_p95_s", "Latency P95 (s)"),
    ("llm_calls_mean", "LLM calls / investigation"), ("tokens_mean", "Tokens / investigation"),
    ("input_tokens_total", "Input tokens total"), ("output_tokens_total", "Output tokens total"),
    ("cost_usd_total", "Cost total (USD)"),
]


def summary_table(summaries: dict[str, dict]) -> str:
    systems = list(summaries)
    lines = ["| Metric | " + " | ".join(systems) + " |", "|---|" + "---|" * len(systems)]
    for key, label in TABLE_METRICS:
        vals = []
        for s in systems:
            v = summaries[s].get(key)
            vals.append("n/a" if v is None else (f"{v:.3f}" if isinstance(v, float) else str(v)))
        lines.append(f"| {label} | " + " | ".join(vals) + " |")
    return "\n".join(lines) + "\n"
