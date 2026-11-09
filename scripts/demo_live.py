"""Live trace of a multi-agent investigation (used for the demo video).

python scripts/demo_live.py INC-005 [--provider anthropic|stub] > trace.txt
Prints agent messages, tool calls and verdicts as they happen, with elapsed seconds.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.llm.provider import build_provider  # noqa: E402
from app.models.incident import IncidentReport  # noqa: E402
from app.models.investigation import InvestigationConfig  # noqa: E402
from app.orchestration.state import create_runtime  # noqa: E402
from app.orchestration.workflow import run_investigation  # noqa: E402
from app.tools.data_store import load_incident_report  # noqa: E402


async def main(iid: str, provider: str | None) -> None:
    inc = IncidentReport(**load_incident_report(iid))
    rt = create_runtime(inc, build_provider(provider), InvestigationConfig())
    st = rt.state
    t0 = time.perf_counter()
    print(f"INCIDENT {inc.incident_id} [{inc.severity}] {inc.title}")
    print(f"  {inc.description}")
    print(f"  affected: {', '.join(inc.affected_services)}   symptom start: {inc.symptom_start:%H:%M}Z\n", flush=True)
    seen_msgs = seen_calls = seen_verdicts = 0

    def emit(line: str) -> None:
        print(f"[{time.perf_counter() - t0:6.1f}s] {line}", flush=True)

    async def watch() -> None:
        nonlocal seen_msgs, seen_calls, seen_verdicts
        while True:
            for m in st.messages[seen_msgs:]:
                extra = ""
                p = m.payload
                if m.message_type.value == "task_assignment":
                    extra = f"round {p.get('round')}: {p.get('objective', '')[:70]}"
                elif m.message_type.value == "findings" and m.recipient.value == "orchestrator":
                    extra = f"{len(p.get('findings', []))} findings - {p.get('summary', '')[:70]}"
                elif m.message_type.value == "hypotheses":
                    extra = ", ".join(f"{h['hypothesis_id']}={h['category']}@{h.get('culprit_service')}" for h in p.get("hypotheses", []))
                elif m.message_type.value == "evidence_request":
                    extra = f"-> {p.get('target_agent')}: {p.get('request', '')[:70]}"
                if m.message_type.value in ("task_assignment", "findings", "hypotheses", "evidence_request", "critic_verdict", "report"):
                    if m.message_type.value == "findings" and m.recipient.value == "reasoning":
                        continue
                    if m.message_type.value == "critic_verdict" and m.recipient.value != "orchestrator":
                        continue
                    if m.message_type.value == "critic_verdict":
                        extra = f"{p.get('verdict')}: {p.get('summary', '')[:80]}"
                    emit(f"MSG  {m.sender.value:>13} -> {m.recipient.value:<13} {m.message_type.value.upper():<17} {extra}")
            seen_msgs = len(st.messages)
            for c in st.tool_calls[seen_calls:]:
                svc = c.arguments.get("service") or ""
                status = "ok" if c.success and not c.is_partial else ("PARTIAL" if c.success else f"FAILED {c.error_code}")
                retry = f" (attempts {c.attempts})" if c.attempts > 1 else ""
                emit(f"TOOL {c.agent:>13}    {c.tool_name}({svc}) {status}{retry} +{len(c.evidence_ids)} evidence")
            seen_calls = len(st.tool_calls)
            for h_round, hyps in []:
                pass
            if st.critic_verdicts[seen_verdicts:]:
                for h in sorted(st.hypotheses, key=lambda h: -h.confidence):
                    emit(f"     scored  {h.hypothesis_id} {h.category.value}@{h.culprit_service}: confidence {h.confidence:.2f} [{h.status}]")
                seen_verdicts = len(st.critic_verdicts)
            await asyncio.sleep(0.2)

    w = asyncio.create_task(watch())
    await run_investigation(inc, rt.llm, rt.state.config, runtime=rt)
    await asyncio.sleep(0.5)
    w.cancel()
    r = st.report
    print()
    print(f"FINAL STATUS: {r['final_status']}")
    print(f"ROOT CAUSE:   {r['root_cause_statement'][:220]}")
    u = st.stats.usage_total
    print(f"rounds {st.round} | tool calls {st.stats.tool_calls} | messages {len(st.messages)} | "
          f"evidence {len(st.evidence)} | {u.llm_calls} LLM calls | {u.total_tokens} tokens | ${u.cost_usd:.3f} | "
          f"{st.stats.duration_s:.0f}s")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("incident")
    ap.add_argument("--provider", default=None)
    a = ap.parse_args()
    asyncio.run(main(a.incident, a.provider))
