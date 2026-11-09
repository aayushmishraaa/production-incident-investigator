"""Command-line interface.

  python -m app.cli incidents
  python -m app.cli investigate --incident INC-001 [--system single_agent] [--provider stub]
  python -m app.cli evaluate [--runs 3] [--incidents INC-001 INC-005] [--provider stub]
  python -m app.cli history
  python -m app.cli serve
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys

from app.config import get_settings
from app.evaluation.evaluator import Evaluator
from app.evaluation.single_agent import run_single_agent
from app.llm.provider import CostLedger, build_provider
from app.models.incident import IncidentReport
from app.models.investigation import InvestigationConfig
from app.models.report import InvestigationReport
from app.orchestration.workflow import run_investigation
from app.reporting.report_generator import save_report
from app.storage.repository import InvestigationRepository
from app.tools.data_store import list_incident_reports, load_incident_report


def cmd_investigate(a: argparse.Namespace) -> int:
    incident = IncidentReport(**load_incident_report(a.incident))
    llm = build_provider(a.provider)
    cfg = InvestigationConfig(max_rounds=a.max_rounds, max_tool_calls=a.max_tool_calls)
    runner = run_single_agent if a.system == "single_agent" else run_investigation
    state = asyncio.run(runner(incident, llm, cfg))
    InvestigationRepository().save(state)
    report = InvestigationReport.model_validate(state.report)
    jp, mp = save_report(report)
    print(f"\nInvestigation {state.investigation_id} ({state.system}) -> {state.final_status.value}")
    print(f"Root cause: {report.root_cause_statement}")
    print(f"Rounds: {state.round} | tool calls: {state.stats.tool_calls} (failed {state.stats.tool_failures}, "
          f"retries {state.stats.tool_retries}) | messages: {len(state.messages)} | {state.stats.duration_s:.1f}s")
    if state.stats.tokens_available:
        u = state.stats.usage_total
        print(f"Tokens: {u.total_tokens} ({u.llm_calls} LLM calls, ${u.cost_usd:.4f})")
    else:
        print("Tokens: unavailable (stub provider)")
    print(f"Report: {mp}\n        {jp}")
    return 0


def cmd_evaluate(a: argparse.Namespace) -> int:
    ev = Evaluator(provider=a.provider, runs=a.runs, incidents=a.incidents, concurrency=a.concurrency,
                   systems=a.systems, use_judge=not a.no_judge)
    res = asyncio.run(ev.run())
    out = get_settings().results_dir / "evaluation"
    print((out / "summary_table.md").read_text())
    if res["skipped"]:
        print(f"Skipped {len(res['skipped'])} runs: {res['skipped'][:3]}")
    print(f"Results: {out}/evaluation_results.json, evaluation_runs.csv; charts: {get_settings().results_dir / 'charts'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser(prog="python -m app.cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("incidents")
    sub.add_parser("history")
    sub.add_parser("spend")
    sp = sub.add_parser("serve")
    sp.add_argument("--port", type=int, default=8000)
    i = sub.add_parser("investigate")
    i.add_argument("--incident", required=True)
    i.add_argument("--system", choices=["multi_agent", "single_agent"], default="multi_agent")
    i.add_argument("--provider", choices=["anthropic", "stub"], default=None)
    i.add_argument("--max-rounds", type=int, default=3)
    i.add_argument("--max-tool-calls", type=int, default=60)
    e = sub.add_parser("evaluate")
    e.add_argument("--runs", type=int, default=1)
    e.add_argument("--incidents", nargs="*")
    e.add_argument("--systems", nargs="*", choices=["multi_agent", "single_agent"])
    e.add_argument("--provider", choices=["anthropic", "stub"], default=None)
    e.add_argument("--concurrency", type=int, default=4)
    e.add_argument("--no-judge", action="store_true")
    a = p.parse_args(argv)

    if a.cmd == "incidents":
        for r in list_incident_reports():
            print(f"{r['incident_id']}  {r['severity']}  {r['title']}  [{', '.join(r['affected_services'])}]")
        return 0
    if a.cmd == "history":
        for r in InvestigationRepository().list():
            print(json.dumps(r))
        return 0
    if a.cmd == "spend":
        print(f"Global LLM spend: ${CostLedger().total():.4f} / cap ${CostLedger().cap:.2f}")
        return 0
    if a.cmd == "serve":
        import uvicorn
        uvicorn.run("app.main:app", host="127.0.0.1", port=a.port)
        return 0
    if a.cmd == "investigate":
        return cmd_investigate(a)
    return cmd_evaluate(a)


if __name__ == "__main__":
    sys.exit(main())
