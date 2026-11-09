"""Build the narrated walkthrough video (demo/walkthrough.mp4) from REAL artefacts.

Inputs: demo/trace_*.txt (from scripts/demo_live.py), docs/, results/ (charts, reports, evaluation),
a live FastAPI server for the Swagger screenshot. Requires macOS `say`, Google Chrome, ffmpeg.
"""
from __future__ import annotations

import json
import re
import subprocess
import textwrap
from pathlib import Path

import markdown
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "demo" / "build"
OUT.mkdir(parents=True, exist_ok=True)
W, H = 1920, 1080
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
MONO = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 22)
MONO_SM = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 19)
SANS_B = ImageFont.truetype("/System/Library/Fonts/HelveticaNeue.ttc", 76, index=1)
SANS = ImageFont.truetype("/System/Library/Fonts/HelveticaNeue.ttc", 38)
SANS_SM = ImageFont.truetype("/System/Library/Fonts/HelveticaNeue.ttc", 30)
BG, FG, ACC = (15, 23, 42), (226, 232, 240), (96, 165, 250)
VOICE = "Samantha"
REPO = "github.com/aayushmishraaa/production-incident-investigator"


def sh(cmd: list[str]) -> str:
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout


def duration(path: Path) -> float:
    return float(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]).strip())


def narrate(i: int, text: str) -> tuple[Path, float]:
    aiff = OUT / f"s{i:02d}.aiff"
    sh(["say", "-v", VOICE, "-r", "185", "-o", str(aiff), text])
    return aiff, duration(aiff) + 0.6


# ------------------------------------------------------------------ frame renderers
def slide(path: Path, title: str, lines: list[str], footer: str = "") -> Path:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 10], fill=ACC)
    d.text((120, 150), title, font=SANS_B, fill=(255, 255, 255))
    y = 300
    for ln in lines:
        for wrapped in textwrap.wrap(ln, 80) or [""]:
            d.text((130, y), wrapped, font=SANS, fill=FG)
            y += 56
        y += 14
    if footer:
        d.text((120, H - 110), footer, font=SANS_SM, fill=ACC)
    img.save(path)
    return path


def colour(line: str):
    if "FAILED" in line or "REJECT" in line:
        return (248, 113, 113)
    if "PARTIAL" in line or "attempts" in line or "NEEDS_MORE" in line:
        return (251, 191, 36)
    if "CRITIC_VERDICT" in line or "FINAL STATUS" in line or "ROOT CAUSE" in line or "APPROVED" in line:
        return (74, 222, 128)
    if " MSG " in line or line.startswith("[") and "MSG" in line:
        return (147, 197, 253)
    if "scored" in line:
        return (216, 180, 254)
    return FG


def terminal(path: Path, title: str, lines: list[str]) -> Path:
    img = Image.new("RGB", (W, H), (10, 12, 16))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 44], fill=(38, 42, 52))
    for k, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse([20 + k * 30, 13, 38 + k * 30, 31], fill=c)
    d.text((130, 10), title, font=MONO_SM, fill=(200, 200, 200))
    y = 64
    for ln in lines[-37:]:
        d.text((24, y), ln[:150], font=MONO_SM, fill=colour(ln))
        y += 27
    img.save(path)
    return path


def chrome_shot(url: str, path: Path, budget_ms: int = 6000, height: int = H) -> Path:
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--window-size={W},{height}",
                    f"--virtual-time-budget={budget_ms}", f"--screenshot={path}", url],
                   check=True, capture_output=True)
    return path


def html_page(name: str, body_html: str, extra_head: str = "") -> Path:
    p = OUT / f"{name}.html"
    p.write_text(f"""<!doctype html><html><head><meta charset="utf-8">
<style>
body{{background:#0f172a;color:#e2e8f0;font-family:-apple-system,Helvetica,Arial;margin:0;padding:40px 70px;font-size:22px}}
h1{{color:#fff;font-size:44px;margin:0 0 18px}} h2{{color:#93c5fd;font-size:32px;margin:22px 0 10px}} h3{{color:#c4b5fd;font-size:25px}}
table{{border-collapse:collapse;font-size:19px}} td,th{{border:1px solid #334155;padding:6px 12px}} th{{background:#1e293b}}
code{{color:#fbbf24}} pre{{background:#020617;padding:12px}} a{{color:#93c5fd}} .mermaid{{background:#fff;border-radius:12px;padding:10px;text-align:center}} .mermaid svg{{max-height:900px;width:auto!important}}
li{{margin:4px 0}}
</style>{extra_head}</head><body>{body_html}</body></html>""")
    return p


def md_to_html(md: str) -> str:
    return markdown.markdown(md, extensions=["tables", "fenced_code"])


# ------------------------------------------------------------------ scenes
def build() -> None:
    scenes: list[dict] = []
    ev = json.loads((ROOT / "results/evaluation/evaluation_results.json").read_text())["summary"]
    m, s = ev["multi_agent"], ev["single_agent"]

    scenes.append(dict(frames=[slide(OUT / "f_title.png", "Multi-Agent Production Incident Investigator",
        ["Six cooperating Claude agents investigate production incidents from logs, metrics, deployments, "
         "config changes, dependencies and incident history.",
         "Evidence-grounded reports. Inconclusive is an allowed answer.",
         "Evaluated against a single-agent baseline on 12 synthetic incidents."], REPO)],
        say="This is a walkthrough of the multi-agent production incident investigator. Six cooperating Claude agents "
            "investigate a production incident using simulated logs, metrics, deployments, configuration changes, "
            "service dependencies and past incidents, and produce an evidence-grounded report. Everything you will see "
            "comes from real runs on Claude Haiku five point five."))

    arch_md = (ROOT / "docs/architecture.md").read_text()
    blocks = re.findall(r"```mermaid\n(.*?)```", arch_md, re.S)
    head = '<script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"></script>' \
           '<script>mermaid.initialize({startOnLoad:true,theme:"default"});</script>'
    p = html_page("arch", f'<h1>Architecture</h1><div class="mermaid">{blocks[0]}</div>', head)
    scenes.append(dict(frames=[chrome_shot(p.as_uri(), OUT / "f_arch.png", 8000)],
        say="Here is the architecture. A LangGraph state machine coordinates the six agents: the orchestrator, "
            "observability, dependency, reasoning, critic and reporting agents. They share one investigation state and "
            "exchange structured, typed messages over a message bus. Every tool call goes through a shared executor that "
            "validates input, enforces a global budget and timeouts, retries failures, and registers evidence with an ID "
            "that later claims must cite."))
    p = html_page("loop", f'<h1>Investigation loop with Critic feedback</h1><div class="mermaid">{blocks[4]}</div>', head)
    scenes.append(dict(frames=[chrome_shot(p.as_uri(), OUT / "f_loop.png", 8000)],
        say="The workflow is plan, gather, reason, critique, decide. If the critic needs more evidence, the orchestrator "
            "creates follow-up tasks and loops back, bounded by rounds, tool calls, LLM calls, cost, and a timeout. "
            "Otherwise the reporting agent writes the final report."))

    trace = (ROOT / "demo/trace_INC-005.txt").read_text().splitlines()
    n = len(trace)
    cuts = [8, 18, 28, 33, 40, n]
    says = [
        "Now a live playthrough of incident five. Payments got slow right after a payment service release, and the team "
        "suspects the release. The orchestrator checks the dependency graph, then dispatches three independent tasks "
        "to the observability and dependency agents, which run in parallel.",
        "The agents query metrics and logs concurrently. Notice one query failed with invalid query and the agent simply "
        "corrected it. The dependency agent finds the release at eleven thirty two.",
        "Findings flow back to the orchestrator as structured messages. Observability reports that postgres disk wait "
        "and latency degraded at about eleven twenty two, ten minutes before the release.",
        "The reasoning agent proposes competing hypotheses: postgres storage degradation, the deployment, and others. "
        "The critic, which cannot see confidence scores, runs its own verification queries.",
        "The critic approves the storage hypothesis. The transparent scorer gives it zero point nine, and the deployment "
        "drops to zero because its proposed cause comes after the first anomaly. Temporal correlation was not treated as causation.",
        "Final status: root cause identified, postgres storage degradation, in about seventy seconds for under two cents.",
    ]
    prev = 0
    for k, (cut, text) in enumerate(zip(cuts, says)):
        cut = min(cut, n)
        frames = [terminal(OUT / f"f_t5_{k}_{j}.png", "python scripts/demo_live.py INC-005", trace[:j])
                  for j in range(max(prev, 1), cut + 1)] or [terminal(OUT / f"f_t5_{k}.png", "demo", trace[:cut])]
        scenes.append(dict(frames=frames, say=text))
        prev = cut

    rep = (ROOT / "results/reports/samples/INC-005_multi_agent_run1.md").read_text()
    sect = rep.split("## Root-Cause Hypotheses")[1].split("## Probable Root Cause")[0]
    p = html_page("report", md_to_html("# Report excerpt: hypotheses & critic review (INC-005)\n## Root-Cause Hypotheses" + sect[:6500]))
    scenes.append(dict(frames=[chrome_shot(p.as_uri(), OUT / "f_report.png", 2000)],
        say="The report ranks hypotheses with supporting and contradicting evidence. Every citation is an evidence ID "
            "that exists in the shared state, and every statement is labelled as confirmed fact, observed evidence, "
            "inference, assumption, or unknown. The confidence breakdown is fully transparent."))

    t9 = ROOT / "demo/trace_INC-009.txt"
    if t9.exists() and t9.read_text().strip():
        lines9 = t9.read_text().splitlines()
        key = [ln for ln in lines9 if "FAILED" in ln or "PARTIAL" in ln or "attempts" in ln]
        keep = lines9[:5] + [ln for ln in lines9[5:] if ln in key or "CRITIC_VERDICT" in ln or "scored" in ln] + lines9[-3:]
        scenes.append(dict(frames=[terminal(OUT / "f_t9.png", "python scripts/demo_live.py INC-009   (tool failures)", keep)],
            say="Incident nine injects tool failures: metrics queries time out, deployment history is unavailable, and logs "
                "come back partial. The executor retries with backoff, partial evidence is down-weighted, and failures are "
                "recorded as evidence gaps, never as proof that a system is healthy."))

    inc10 = (ROOT / "results/reports/samples/INC-010_multi_agent_run1.md").read_text()
    stmt = inc10.split("## Probable Root Cause")[1].split("##")[0].strip()
    gaps = inc10.split("## Evidence Gaps")[1].split("## Limitations")[0].strip().splitlines()[:6]
    scenes.append(dict(frames=[slide(OUT / "f_inc10.png", "INC-010: insufficient evidence",
        ["Final status: INCONCLUSIVE", stmt[:160]] + [g[:110] for g in gaps])],
        say="When the evidence is not there, the system says so. Incident ten has missing telemetry, and every run "
            "returned inconclusive with the explicit statement that the root cause could not be established, instead of "
            "inventing one."))

    p = chrome_shot("http://127.0.0.1:8765/docs", OUT / "f_swagger.png", 5000)
    scenes.append(dict(frames=[p],
        say="Everything is exposed through a FastAPI service with Swagger documentation: start an investigation, poll its "
            "shared state, and fetch the report, evidence, and timeline. Investigations persist to SQLite. There is also a command line interface."))

    table = (ROOT / "results/evaluation/summary_table.md").read_text().splitlines()
    keep_rows = [r for r in table if any(k in r for k in ("Metric", "---", "Root-cause accuracy (category)", "Accuracy when diagnosed",
                 "Incorrect", "Inconclusive", "Hallucinated", "Unsupported", "Decoy", "LLM-judge", "Tool calls / investigation",
                 "Latency mean", "Tokens / investigation", "Cost total"))]
    p = html_page("eval", md_to_html("# Evaluation: 12 incidents x 3 runs, Claude Haiku 5.5\n" + "\n".join(keep_rows)))
    scenes.append(dict(frames=[chrome_shot(p.as_uri(), OUT / "f_eval.png", 1500)],
        say=f"The evaluation ran both systems on twelve incidents, three runs each. The single agent baseline had slightly "
            f"higher raw accuracy, {s['accuracy']:.2f} versus {m['accuracy']:.2f}. But when the multi agent system gave a "
            f"diagnosis it was always right, with zero wrong answers and zero hallucinated citations, while the baseline "
            f"gave three wrong diagnoses and a twenty one percent unsupported hypothesis rate."))
    acc = Image.open(ROOT / "results/charts/accuracy_comparison.png").convert("RGB")
    canvas = Image.new("RGB", (W, H), (255, 255, 255))
    acc.thumbnail((W - 80, H - 80))
    canvas.paste(acc, ((W - acc.width) // 2, (H - acc.height) // 2))
    canvas.save(OUT / "f_acc.png")
    tok = Image.open(ROOT / "results/charts/token_comparison.png").convert("RGB")
    canvas2 = Image.new("RGB", (W, H), (255, 255, 255))
    tok.thumbnail((W - 80, H - 80))
    canvas2.paste(tok, ((W - tok.width) // 2, (H - tok.height) // 2))
    canvas2.save(OUT / "f_tok.png")
    scenes.append(dict(frames=[OUT / "f_acc.png"],
        say="The trade off is clear: the critic makes the multi agent system more cautious. It abstains more often, which "
            "lowers coverage, but it never commits to a wrong root cause. On the cache degradation incident the baseline "
            "blamed a feature flag change in all three runs, while the multi agent system found the real cause."))
    scenes.append(dict(frames=[OUT / "f_tok.png"],
        say="That caution costs about four times the tokens and latency. The observability, reasoning, and critic agents "
            "dominate the budget. The whole project, development and evaluation included, used about a dollar fifty of a three dollar cap."))

    pytest_out = (OUT / "pytest.txt").read_text().splitlines() if (OUT / "pytest.txt").exists() else []
    scenes.append(dict(frames=[terminal(OUT / "f_tests.png", "pytest --cov=app", pytest_out[-37:])],
        say="Ninety eight automated tests run offline in about ten seconds with ninety four percent coverage. They prove "
            "parallel execution, the critic feedback loop, critic rejection, bounded retries, tool timeouts and partial "
            "data, agent crash recovery, inconclusive outcomes, and that agents can never read the ground truth."))
    scenes.append(dict(frames=[slide(OUT / "f_end.png", "Thanks for watching",
        ["Code, docs, evaluation results, charts, sample reports and the coding transcript:", REPO,
         "README.md  -  docs/architecture.md  -  docs/evaluation.md  -  TECHNICAL_NOTE.md"])],
        say="The code, architecture docs, evaluation results, sample reports and the full coding transcript are all in the "
            "repository. Thanks for watching."))

    # ------------------------------------------------------------------ assemble
    parts = []
    for i, sc in enumerate(scenes):
        audio, dur = narrate(i, sc["say"])
        frames = sc["frames"]
        per = dur / len(frames)
        lst = OUT / f"s{i:02d}.txt"
        lst.write_text("".join(f"file '{f}'\nduration {per:.3f}\n" for f in frames) + f"file '{frames[-1]}'\n")
        seg = OUT / f"s{i:02d}.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-i", str(audio),
                        "-vf", f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=white,fps=30,format=yuv420p",
                        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "aac", "-b:a", "160k",
                        "-t", f"{dur:.3f}", "-shortest", str(seg)], check=True)
        parts.append(seg)
        print(f"scene {i}: {dur:.1f}s, {len(frames)} frames")
    concat = OUT / "parts.txt"
    concat.write_text("".join(f"file '{p}'\n" for p in parts))
    final = ROOT / "demo" / "walkthrough.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy",
                    str(final)], check=True)
    print(f"wrote {final} ({duration(final):.0f}s)")


if __name__ == "__main__":
    build()
