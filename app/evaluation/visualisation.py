"""Evaluation charts (matplotlib, headless)."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

COLORS = {"multi_agent": "#2a6fdb", "single_agent": "#e07b39"}
LABELS = {"multi_agent": "Multi-agent", "single_agent": "Single-agent"}


def _bar_compare(ax, metrics: list[str], summaries: dict[str, dict], title: str, ylim=None):
    systems = list(summaries)
    w = 0.8 / len(systems)
    for i, s in enumerate(systems):
        vals = [summaries[s].get(m) or 0 for m in metrics]
        bars = ax.bar([x + i * w for x in range(len(metrics))], vals, w, label=LABELS.get(s, s), color=COLORS.get(s))
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, b.get_height(), f"{v:.2f}", ha="center", va="bottom", fontsize=7)
    ax.set_xticks([x + w * (len(systems) - 1) / 2 for x in range(len(metrics))])
    ax.set_xticklabels([m.replace("_", "\n") for m in metrics], fontsize=8)
    ax.set_title(title)
    if ylim:
        ax.set_ylim(*ylim)
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.3)


def make_charts(rows: list[dict[str, Any]], summaries: dict[str, dict], out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []

    fig, ax = plt.subplots(figsize=(10, 4.5))
    _bar_compare(ax, ["accuracy", "strict_accuracy", "behaviour_accuracy", "coverage", "accuracy_when_diagnosed", "macro_f1"],
                 summaries, "Root-cause accuracy", (0, 1.1))
    paths.append(_save(fig, out_dir / "accuracy_comparison.png"))

    fig, ax = plt.subplots(figsize=(10, 4.5))
    _bar_compare(ax, ["citation_validity", "top_citation_accuracy", "key_evidence_recall", "decoy_handling_rate",
                      "contradiction_coverage", "completeness_score"], summaries, "Evidence grounding & completeness", (0, 1.1))
    paths.append(_save(fig, out_dir / "grounding_comparison.png"))

    by_sys = defaultdict(list)
    for r in rows:
        by_sys[r["system"]].append(r)
    fig, ax = plt.subplots(figsize=(7, 4.5))
    systems = list(by_sys)
    ax.boxplot([[r["duration_s"] for r in by_sys[s]] for s in systems], tick_labels=[LABELS.get(s, s) for s in systems])
    ax.set_ylabel("seconds per investigation")
    ax.set_title("Investigation latency")
    ax.grid(axis="y", alpha=0.3)
    paths.append(_save(fig, out_dir / "latency_comparison.png"))

    incidents = sorted({r["incident_id"] for r in rows})
    fig, ax = plt.subplots(figsize=(11, 4.5))
    w = 0.4
    for i, s in enumerate(systems):
        means = []
        for inc in incidents:
            v = [r["tool_calls"] for r in by_sys[s] if r["incident_id"] == inc]
            means.append(sum(v) / len(v) if v else 0)
        ax.bar([x + i * w for x in range(len(incidents))], means, w, label=LABELS.get(s, s), color=COLORS.get(s))
    ax.set_xticks([x + w / 2 for x in range(len(incidents))])
    ax.set_xticklabels(incidents, rotation=45, fontsize=8)
    ax.set_ylabel("mean tool calls (incl. retries)")
    ax.set_title("Tool calls per incident")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    paths.append(_save(fig, out_dir / "tool_calls_comparison.png"))

    if all(summaries[s].get("tokens_available") for s in summaries):
        fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
        ax = axes[0]
        for i, s in enumerate(systems):
            sm = summaries[s]
            ax.bar(i, sm["tokens_mean"], color=COLORS.get(s))
            ax.text(i, sm["tokens_mean"], f"{sm['tokens_mean']:.0f}", ha="center", va="bottom", fontsize=8)
        ax.set_xticks(range(len(systems)))
        ax.set_xticklabels([LABELS.get(s, s) for s in systems])
        ax.set_title("Mean tokens per investigation")
        ax2 = axes[1]
        per_agent = summaries.get("multi_agent", {}).get("tokens_by_agent_mean") or {}
        if per_agent:
            ax2.barh(list(per_agent), list(per_agent.values()), color=COLORS["multi_agent"])
            ax2.set_title("Multi-agent: mean tokens by agent")
        fig.tight_layout()
        paths.append(_save(fig, out_dir / "token_comparison.png"))

    for s in systems:
        conf = summaries[s]["confusion"]
        labels, mat = conf["labels"], conf["matrix"]
        fig, ax = plt.subplots(figsize=(8, 7))
        ax.imshow(mat, cmap="Blues")
        ax.set_xticks(range(len(labels)))
        ax.set_yticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=60, ha="right", fontsize=8)
        ax.set_yticklabels(labels, fontsize=8)
        for i in range(len(labels)):
            for j in range(len(labels)):
                if mat[i][j]:
                    ax.text(j, i, mat[i][j], ha="center", va="center", fontsize=9)
        ax.set_xlabel("predicted")
        ax.set_ylabel("ground truth")
        ax.set_title(f"Confusion matrix - {LABELS.get(s, s)}")
        fig.tight_layout()
        paths.append(_save(fig, out_dir / f"confusion_{s}.png"))
    return paths


def _save(fig, path: Path) -> Path:
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path
