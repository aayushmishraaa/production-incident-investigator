# Technical Note

**Architecture.** A LangGraph state machine (plan → gather → reason → critique → decide → report) coordinates six agents. Each agent is a separate Claude tool-calling loop with its own prompt, tool subset and a Pydantic-validated `submit_*` contract. The Orchestrator uses the LLM only to plan. Dispatch, the task DAG, follow-up rounds, limits and the final status are deterministic code, so coordination is auditable and bounded. Independent tasks and parallel tool calls run concurrently (`asyncio.gather` with a semaphore).

**Shared state and communication.** One `InvestigationState` holds tasks with dependencies, typed `AgentMessage`s, the evidence registry, gaps, findings, hypotheses, verdicts, tool-call records and statistics. Agents exchange structured payloads through a message bus stored in that state. Reasoning builds its input only from its inbox, so removing the specialists' findings changes its output; a test checks this. Only tools can mint evidence IDs, and every citation is checked against the registry.

**The Critic.** The Critic is made independent in four ways:
- deterministic pre-checks run first: hallucinated citations, cause after onset, correlation-only change hypotheses, historical-only support
- the Critic never sees confidence scores
- it can query the data itself
- code refuses an approval while a blocking pre-check stands

Confidence comes from a transparent rule-based score, not from the LLM, and is not a calibrated probability.

**Tool failures.** A shared `ToolExecutor` enforces input validation, a global call budget, real timeouts, bounded retries for retryable errors, and seeded fault injection (timeouts, unavailability, partial data). Failures become `EvidenceGap`s, labelled "not evidence of health". Partial results lower evidence reliability. Agent crashes and malformed output get bounded retries. A failed parallel task does not stop the investigation, and a failed Critic never auto-approves.

**Results (Claude Haiku 5.5, 12 incidents × 3 runs).**

| | Multi-agent | Single-agent |
|---|---|---|
| Accuracy | 0.86 | 0.92 |
| Accuracy when a diagnosis was given | 1.00 (0 wrong) | 0.91 (3 wrong) |
| Hallucinated citations | 0 | 3 |
| Unsupported hypotheses | 0.8% | 21% |
| Tokens and latency | ~4× and ~4.4× the baseline | baseline |

The multi-agent system abstains more often instead of being wrong.

**Trade-offs.** On clean synthetic data one capable agent solves most cases. Collaboration pays off on ambiguous cases (cache degradation vs a config change, conflicting telemetry) and in grounding discipline. The strict Critic lowers coverage, and each review round costs about 80k tokens.

**Limitations.**
- The benchmark is small and self-designed.
- The judge is from the same model family as the agents.
- Thresholds were adjusted once after a single pilot run (disclosed).
- The Critic sometimes withholds approval of a correct leader until the round limit.
- Follow-up specialists repeat queries.
- LLM sampling cannot be seeded.
- The offline stub only exercises the plumbing.

**Improvements.**
- Give follow-up specialists a digest of earlier query results.
- Calibrate the approval thresholds on held-out incidents.
- Use a cheaper model for evidence gathering and a stronger one for reasoning and critique.
- Make wider use of prompt caching.
- Add trace-based tools.
- Test against noisier telemetry.
