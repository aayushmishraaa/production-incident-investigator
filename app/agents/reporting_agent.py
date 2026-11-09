"""AGENT 6: Reporting -- writes the narrative parts of the final report.

It receives VALIDATED state (final status, ranked hypotheses, critic verdict, gaps)
and cannot change the conclusion: status/root cause are fixed by the Orchestrator and
the structured sections are assembled deterministically by app.reporting.
"""
from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from app.agents.base_agent import BaseAgent
from app.models.agent import AgentName, InvestigationTask

SYSTEM = """You are the Reporting Agent. You write the narrative sections of a production incident investigation report from VALIDATED findings that are given to you.
Rules:
- Do not change or contradict the final status or the leading hypothesis you are given. Do not introduce new root causes or new facts.
- If the status is INCONCLUSIVE, say clearly that the root cause could not be established and focus actions on mitigation and closing evidence gaps.
- If the status is PROBABLE_ROOT_CAUSE, describe it as the most probable explanation, not a confirmed fact.
- Corrective actions = immediate mitigation; preventive actions = long-term fixes; monitoring = concrete alerts/metrics/logging.
- Reference evidence ids in parentheses where useful. Be concise and specific.
Call submit_report_narrative."""


class NarrativeSubmission(BaseModel):
    executive_summary: str
    corrective_actions: list[str] = Field(min_length=1, max_length=8)
    preventive_actions: list[str] = Field(min_length=1, max_length=8)
    monitoring_recommendations: list[str] = Field(min_length=1, max_length=8)
    limitations: list[str] = Field(default_factory=list, max_length=8)
    conclusion: str


class ReportingAgent(BaseAgent):
    name = AgentName.REPORTING
    system_prompt = SYSTEM
    tool_names: list[str] = []
    submit_name = "submit_report_narrative"
    submit_description = "Submit the narrative sections of the report."
    submit_model = NarrativeSubmission
    max_tokens = 3000

    async def run(self, task: InvestigationTask, validated: dict[str, Any]) -> NarrativeSubmission:
        briefing = "VALIDATED INVESTIGATION RESULT:\n" + json.dumps(validated, default=str)[:12000]
        return await self.run_loop(briefing, task, max_steps=2)


def fallback_narrative(validated: dict[str, Any]) -> NarrativeSubmission:
    """Deterministic narrative used if the Reporting Agent fails (recorded as a failure)."""
    top = validated.get("leading_hypothesis")
    status = validated["final_status"]
    if top and status in ("ROOT_CAUSE_IDENTIFIED", "PROBABLE_ROOT_CAUSE"):
        summary = (f"{validated['incident']['title']}: the {'most probable ' if status == 'PROBABLE_ROOT_CAUSE' else ''}"
                   f"root cause is {top['category']} in {top.get('culprit_service')}: {top['description']}")
        corrective = [f"Mitigate {top['category'].replace('_', ' ')} on {top.get('culprit_service')}"]
    else:
        summary = f"{validated['incident']['title']}: root cause could not be conclusively established."
        corrective = ["Mitigate customer impact (scale out / fail over / roll back recent changes if risk is low)"]
    return NarrativeSubmission(
        executive_summary=summary, corrective_actions=corrective,
        preventive_actions=["Address the evidence gaps listed below", "Add regression tests for the identified failure mode"],
        monitoring_recommendations=["Alert on error rate and p95 latency per service", "Monitor telemetry completeness"],
        limitations=["Narrative generated deterministically because the Reporting Agent failed"],
        conclusion=summary)
