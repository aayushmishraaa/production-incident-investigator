"""Export a Claude Code session transcript (JSONL) to Markdown, redacting secrets.

Usage: python scripts/export_transcript.py <session.jsonl> transcript/coding_assistant_transcript.md
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SECRET = re.compile(r"sk-ant-[A-Za-z0-9_\-]{10,}")
MAX_TOOL_OUTPUT = 4000


def redact(text: str) -> str:
    return SECRET.sub("sk-ant-[REDACTED]", text)


def render_block(block: dict) -> str:
    t = block.get("type")
    if t == "text":
        return block.get("text", "")
    if t == "tool_use":
        inp = json.dumps(block.get("input", {}), indent=2)
        if len(inp) > MAX_TOOL_OUTPUT:
            inp = inp[:MAX_TOOL_OUTPUT] + "\n... [truncated]"
        return f"**Tool call: `{block.get('name')}`**\n```json\n{inp}\n```"
    if t == "tool_result":
        content = block.get("content")
        if isinstance(content, list):
            content = "\n".join(c.get("text", "") for c in content if isinstance(c, dict))
        content = str(content or "")
        if len(content) > MAX_TOOL_OUTPUT:
            content = content[:MAX_TOOL_OUTPUT] + "\n... [truncated]"
        return f"<details><summary>Tool result</summary>\n\n```\n{content}\n```\n</details>"
    return ""


def main(src: str, dst: str) -> None:
    out = ["# Coding assistant transcript (Claude Code)", "",
           "Exported from the Claude Code session log. API keys are redacted; very long tool outputs are truncated.", ""]
    for line in Path(src).read_text().splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") not in ("user", "assistant"):
            continue
        msg = ev.get("message", {})
        content = msg.get("content")
        blocks = [{"type": "text", "text": content}] if isinstance(content, str) else (content or [])
        rendered = [r for r in (render_block(b) for b in blocks if isinstance(b, dict)) if r.strip()]
        if not rendered:
            continue
        role = "User" if ev["type"] == "user" else "Assistant"
        if role == "User" and all(b.get("type") == "tool_result" for b in blocks if isinstance(b, dict)):
            role = "Tool"
        out.append(f"## {role}\n")
        out.extend(rendered)
        out.append("")
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    Path(dst).write_text(redact("\n".join(out)))
    print(f"wrote {dst}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
