"""Record a narrated browser playthrough of the web UI (demo/walkthrough.mp4).

Requires: a running server (uvicorn app.main:app --port 8765) with the real provider,
Google Chrome, Playwright (python), macOS `say`, ffmpeg, and demo/build/f_*.png from
scripts/make_demo_video.py (title/architecture/tests/end slides).
"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
B = ROOT / "demo" / "build"
URL = "http://127.0.0.1:8765/"
VOICE, RATE = "Samantha", "185"
W, H = 1920, 1080

LINES = {
    "intro": "This is the web dashboard for the multi agent incident investigator. On the left are the twelve synthetic "
             "production incidents. Each one has its own logs, metrics, deployments and configuration history.",
    "select5": "Let's open incident five. Payments got slow right after a payment service release, and the team suspects "
               "the release. That is the trap.",
    "run5": "I start a real investigation with six Claude agents. The orchestrator plans the work and dispatches independent "
            "tasks, so the observability and dependency agents run in parallel.",
    "feed5": "The live feed shows every structured message between agents and every tool call. Each tool result is "
             "registered as evidence with an ID that later claims must cite.",
    "hyps5": "The reasoning agent proposes competing hypotheses: postgres storage degradation, the deployment, and others. "
             "Their confidence comes from a transparent, rule based score, not from the model.",
    "verdict5": "The critic reviews them without seeing the scores, runs its own queries, and applies automatic checks. "
                "The deployment is rejected because the database degraded ten minutes before it shipped.",
    "report5": "The final report: root cause identified, postgres storage degradation. Every statement is labelled as fact, "
               "observation, inference or unknown, with corrective, preventive and monitoring actions.",
    "select9": "Now incident nine, where the tools themselves fail. Metrics time out, deployment history is unavailable, "
               "and logs come back partial.",
    "feed9": "Watch the amber lines. Failed calls are retried with backoff, partial results are flagged and down weighted, "
             "and failures are recorded as evidence gaps, never as proof that a system is healthy.",
    "done9": "Despite the failures, the agents still find the faulty user service release, and the report lists the "
             "missing data as limitations.",
    "eval": "The evaluation tab compares the six agent system with a single agent baseline that has the same tools and "
            "limits, over twelve incidents and three runs each. The baseline is slightly more accurate overall, but the "
            "multi agent system was never wrong when it committed to a diagnosis, and it produced zero hallucinated citations.",
    "charts": "The charts show the trade off. More grounding and caution, at roughly four times the tokens and latency.",
    "history": "Every investigation is persisted to SQLite, and any past run can be reopened from the history tab.",
}


def sh(cmd):
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout


def dur(p: Path) -> float:
    return float(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]).strip())


def main() -> None:
    B.mkdir(parents=True, exist_ok=True)
    clips = {}
    for k, text in LINES.items():
        p = B / f"ui_{k}.aiff"
        sh(["say", "-v", VOICE, "-r", RATE, "-o", str(p), text])
        clips[k] = (p, dur(p))
    cues: list[tuple[str, float]] = []
    vid_dir = B / "ui_video"
    vid_dir.mkdir(exist_ok=True)
    for f in vid_dir.glob("*.webm"):
        f.unlink()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome")
        ctx = browser.new_context(viewport={"width": W, "height": H}, record_video_dir=str(vid_dir),
                                  record_video_size={"width": W, "height": H})
        page = ctx.new_page()
        t0 = time.monotonic()
        busy_until = [0.0]

        def say(key: str, min_gap: float = 0.4) -> None:
            now = time.monotonic() - t0
            if now < busy_until[0]:
                time.sleep(busy_until[0] - now)
                now = busy_until[0]
            cues.append((key, now))
            busy_until[0] = now + clips[key][1] + min_gap

        def wait_speech() -> None:
            now = time.monotonic() - t0
            if now < busy_until[0]:
                time.sleep(busy_until[0] - now)

        page.goto(URL)
        page.wait_for_selector(".inc")
        page.wait_for_timeout(800)
        say("intro")
        page.hover('.inc[data-id="INC-001"]'); page.wait_for_timeout(2500)
        page.hover('.inc[data-id="INC-008"]'); page.wait_for_timeout(2500)
        wait_speech()

        page.click('.inc[data-id="INC-005"]')
        say("select5")
        wait_speech()
        page.click("#runMulti")
        page.wait_for_timeout(600)
        say("run5")
        page.wait_for_function("document.querySelectorAll('#feed div').length > 12", timeout=120000)
        say("feed5")
        page.wait_for_selector("#hyps .hyp", timeout=240000)
        say("hyps5")
        page.wait_for_selector("#verdict .pill", timeout=240000)
        say("verdict5")
        page.wait_for_selector(".status-big", timeout=300000)
        wait_speech()
        page.evaluate("document.querySelector('#v-investigate').scrollTo({top: 99999, behavior: 'smooth'})")
        page.wait_for_timeout(1200)
        say("report5")
        wait_speech()
        page.wait_for_timeout(800)
        page.evaluate("document.querySelector('#v-investigate').scrollTo({top: 0, behavior: 'smooth'})")
        page.wait_for_timeout(1000)

        page.click('.inc[data-id="INC-009"]')
        say("select9")
        wait_speech()
        page.click("#runMulti")
        page.wait_for_function("document.querySelectorAll('#feed .warn, #feed .bad').length >= 2", timeout=180000)
        say("feed9")
        page.wait_for_selector(".status-big", timeout=300000)
        wait_speech()
        page.evaluate("document.querySelector('#v-investigate').scrollTo({top: 520, behavior: 'smooth'})")
        page.wait_for_timeout(800)
        say("done9")
        page.wait_for_timeout(2500)
        page.evaluate("document.querySelector('#v-investigate').scrollTo({top: 99999, behavior: 'smooth'})")
        wait_speech()

        page.click('nav button[data-v="evaluation"]')
        page.wait_for_timeout(1000)
        say("eval")
        wait_speech()
        page.evaluate("document.querySelector('#v-evaluation').scrollTo({top: 99999, behavior: 'smooth'})")
        page.wait_for_timeout(800)
        say("charts")
        wait_speech()
        page.click('nav button[data-v="history"]')
        page.wait_for_timeout(800)
        say("history")
        wait_speech()
        page.wait_for_timeout(1500)
        total = time.monotonic() - t0
        video_path = Path(page.video.path())
        ctx.close()
        browser.close()

    # mix narration onto the recorded UI video
    inputs, filters = ["-i", str(video_path)], []
    for i, (k, t) in enumerate(cues, start=1):
        inputs += ["-i", str(clips[k][0])]
        ms = int(t * 1000)
        filters.append(f"[{i}:a]adelay={ms}|{ms},aresample=44100[a{i}]")
    mix = "".join(f"[a{i}]" for i in range(1, len(cues) + 1))
    filters.append(f"{mix}amix=inputs={len(cues)}:normalize=0[aout]")
    ui_mp4 = B / "ui_part.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(filters),
                    "-map", "0:v", "-map", "[aout]", "-t", f"{total:.2f}", "-vf", "fps=30,format=yuv420p",
                    "-c:v", "libx264", "-crf", "20", "-preset", "medium", "-c:a", "aac", "-ar", "44100", "-b:a", "160k",
                    str(ui_mp4)], check=True)

    # bookends from the slide build: title + architecture + loop  ...  tests + end
    def slide_seg(img: str, audio: str, name: str) -> Path:
        out = B / f"{name}.mp4"
        d = dur(B / audio) + 0.6
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", str(B / img), "-i", str(B / audio),
                        "-vf", f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p",
                        "-c:v", "libx264", "-crf", "20", "-c:a", "aac", "-ar", "44100", "-b:a", "160k", "-t", f"{d:.2f}",
                        str(out)], check=True)
        return out

    parts = [slide_seg("f_title.png", "s00.aiff", "b_title"), slide_seg("f_arch.png", "s01.aiff", "b_arch"),
             slide_seg("f_loop.png", "s02.aiff", "b_loop"), ui_mp4,
             slide_seg("f_tests.png", "s16.aiff", "b_tests"), slide_seg("f_end.png", "s17.aiff", "b_end")]
    lst = B / "final_parts.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    final = ROOT / "demo" / "walkthrough.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c:v", "libx264", "-crf", "20", "-preset", "medium", "-c:a", "aac", "-ar", "44100", "-b:a", "160k",
                    "-movflags", "+faststart", str(final)], check=True)
    print(f"cues: {[(k, round(t, 1)) for k, t in cues]}")
    print(f"wrote {final} ({dur(final):.0f}s)")


if __name__ == "__main__":
    main()
