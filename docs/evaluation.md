# Evaluation: multi-agent vs single-agent

All numbers below come from one real evaluation run on 2026-11-09:

```bash
python -m app.cli evaluate --runs 3 --concurrency 6
```

Machine-readable outputs:
- `results/evaluation/evaluation_results.json`, which holds the run conditions, summaries and every run
- `results/evaluation/evaluation_runs.csv`
- `results/evaluation/summary_table.md`
- every per-run report, in `results/evaluation/runs/`

Charts are in `results/charts/`.

## 1. Experimental conditions

| | |
|---|---|
| Model | `claude-haiku-5-5` for every agent, the baseline and the judge |
| Effort | `low`; thinking adaptive (model default); no sampling parameters (not supported by the model) |
| Incidents | 12 (INC-001 … INC-012), 3 runs each per system, so 36 investigations per system |
| Limits (both systems) | `max_tool_calls=60`, `max_tool_retries=2`, `tool_timeout_s=2`, `investigation_timeout_s=300`, `max_llm_calls=80`, `max_cost_usd=0.25`, `max_rounds=3` (multi only), `max_agent_steps=6` (baseline gets 18 steps in one loop) |
| Tools | the same `ToolExecutor`, the same 6 tools and the same fault-injection profiles for both systems |
| Seeds | `config.seed + run` for the fault simulator; LLM sampling is not seedable |
| Scheduling | jobs shuffled (seed 42), concurrency 6, so both systems saw the same API load |
| Total wall clock | 905 s for the 72 investigations |
| Cost | $1.11 multi-agent and $0.17 single-agent for the evaluation itself, plus the judge. All LLM spend in the project, development included: $1.53 of the $3.00 cap |

**Scoring.** Each system has to commit to a root-cause category from a fixed, generic
taxonomy, plus a culprit service, or return INCONCLUSIVE.
- **Accuracy:** the predicted category matches ground truth. For INC-010, where ground truth expects an inconclusive result, the correct answer is INCONCLUSIVE.
- **Not correct:** an INCONCLUSIVE result is never counted as a correct diagnosis.
- **Strict accuracy:** the category *and* the culprit service both match.
- **Behaviour accuracy:** the same as accuracy, except that INCONCLUSIVE also counts on INC-006, where ground truth says it's an acceptable outcome.
- **Precision, recall and F1:** macro-averaged over root-cause classes, treating INCONCLUSIVE as an abstention.

An LLM judge, also Haiku, grades explanation quality from 1 to 5 against the
ground-truth description.

## 2. Results

| Metric | Multi-agent | Single-agent |
|---|---|---|
| **Root-cause accuracy (category)** | 0.861 (31/36) | **0.917** (33/36) |
| Accuracy std across the 3 runs | 0.039 | 0.000 |
| Strict accuracy (category + service) | 0.861 | **0.889** |
| Expected-behaviour accuracy | **0.944** | 0.917 |
| Coverage (diagnosis produced) | 0.778 | **0.917** |
| **Accuracy when a diagnosis was produced** | **1.000** | 0.909 |
| Wrong diagnoses | **0** | 3 |
| Inconclusive | 8 | 3 |
| Macro precision / recall / F1 | **1.000** / 0.875 / 0.922 | 0.952 / 0.875 / **0.971** |
| Evidence citation validity | **1.000** | 0.995 |
| Hallucinated (non-existent) citations | **0** | 3 |
| Unsupported hypotheses (no valid support) | **0.8 %** | 21.1 % |
| Top-hypothesis citation accuracy (cites the culprit's own data) | 0.688 | **0.751** |
| Ground-truth key-evidence recall | **0.735** | 0.694 |
| Decoy (misleading change) handled | 1.000 | 1.000 |
| Hypotheses listing contradicting evidence | 0.992 | 1.000 |
| Investigation completeness (5-check score) | 0.956 | 0.967 |
| LLM-judge explanation score (1–5) | 4.53 | **4.69** |
| Tool calls / investigation (incl. retries) | 32.3 | **9.8** |
| Failed / retried tool calls (total) | 15 / 9 | 15 / 9 |
| LLM calls / investigation | 22.8 | **4.0** |
| Latency mean / median / P95 (s) | 107 / 79 / 183 | **24 / 23 / 36** |
| Tokens / investigation | 192 k | **49 k** |
| Input / output tokens (total) | 5.65 M / 1.26 M | 1.56 M / 0.21 M |
| Cost (36 investigations) | $1.11 | **$0.17** |

Multi-agent token use per investigation, by agent (mean):

| Agent | Tokens |
|---|---|
| observability | 73 k |
| reasoning | 41 k |
| critic | 41 k |
| dependency | 25 k |
| reporting | 7 k |
| orchestrator | 4 k |

The multi-agent system averaged 1.83 rounds and 33.6 structured messages per investigation.

Charts:

| Chart | File |
|---|---|
| Accuracy comparison | `results/charts/accuracy_comparison.png` |
| Grounding comparison | `results/charts/grounding_comparison.png` |
| Latency comparison | `results/charts/latency_comparison.png` |
| Tool-call comparison | `results/charts/tool_calls_comparison.png` |
| Token comparison | `results/charts/token_comparison.png` |
| Confusion matrices | `results/charts/confusion_multi_agent.png`, `results/charts/confusion_single_agent.png` |

### Per-incident outcomes (correct runs out of 3)

| Incident | Multi | Single | Notes |
|---|---|---|---|
| INC-001 pool exhaustion | 3 | 3 | |
| INC-002 deployment regression | 3 | 3 | |
| INC-003 upstream auth degradation | 3 | 3 | |
| INC-004 CPU saturation | 3 | 3 | |
| INC-005 misleading deployment | 3 | 3 | both rejected the decoy deploy on timing |
| INC-006 conflicting telemetry | 0 (3 × INCONCLUSIVE) | 3 | inconclusive is *acceptable* here (behaviour accuracy counts it) |
| INC-007 config regression | 2 (1 × INCONCLUSIVE) | 3 | |
| INC-008 cache degradation | 2 (1 × INCONCLUSIVE) | **0** (3 × config regression) | |
| INC-009 tool failures | 3 | 3 | both retried timeouts and kept partial findings |
| INC-010 insufficient evidence | 3 (INCONCLUSIVE) | 3 (INCONCLUSIVE) | |
| INC-011 traffic surge | 3 | 3 | |
| INC-012 config change disguised as pool exhaustion | 3 | 3 | |

## 3. Discussion

**Where multi-agent collaboration helped**

- **No wrong answers.** When the multi-agent system committed to a diagnosis it was always right (36 runs, 28 diagnoses, 0 errors). Its failures were all abstentions. The baseline committed to a wrong cause three times. In incident response a confident wrong answer usually costs more than "inconclusive, here is what we know", so the multi-agent system's error profile is the safer one.
- **INC-008, cache degradation.** The baseline blamed the `profile_v2_cache` feature-flag change in all three runs. That isn't absurd: the flag enlarged cached payloads. But the proximate fault was Redis reaching `maxmemory` and evicting keys, and the multi-agent system got this right in 2 of 3 runs. The separation of duties helped: Observability reported the eviction and hit-rate onsets, Dependency reported the 40-minute-old flag change, and the Critic weighed that 40-minute gap against the onset times.
- **Grounding.** The pre-checks plus specialist-level validation of citation IDs produced zero hallucinated citations and only 0.8% unsupported hypotheses, against 21% for the baseline. The baseline often padded its hypothesis lists with entries that had no valid supporting evidence.
- **Calibrated caution on INC-006.** The Critic recognised that DB error logs contradicted healthy (and partly missing) DB metrics. It returned INCONCLUSIVE every time while still naming the right leading candidate (judge score 3–4). The baseline committed to the right answer with confidence 0.5–0.7. That's correct here, but it is the same behaviour that produced its INC-008 errors.

**Where it hurt**

- **Over-caution costs coverage.** Coverage was 78% against 92%. On INC-007 (one run) and INC-008 (one run), the Critic did not approve the correct leading hypothesis within three rounds. On INC-007 it asked for more evidence each round until the round limit was reached; on INC-008 it ruled INCONCLUSIVE. Stricter gating trades recall for precision. The `approve_confidence` threshold and the Critic's prompt are the levers.
- **Cost and latency.** The multi-agent system needs about 4× the tokens, 6× the LLM calls, 3.3× the tool calls and 4.4× the latency. Observability is the most expensive agent, because it repeats similar queries in follow-up rounds. Each critic round adds a reasoning plus critic pass of roughly 80k tokens.
- **Raw accuracy is not better on this dataset.** With a capable model and a clean, well-scoped toolset, one agent already solves most of these synthetic incidents. The multi-agent architecture pays off on the hard, ambiguous cases (INC-006 and INC-008) and in grounding discipline, not on the easy ones.

**Threats to validity**

- **Small sample.** There are 12 synthetic incidents with 3 runs each. A one-run difference is 2.8 percentage points.
- **Self-designed benchmark.** I designed both the dataset and the systems. The scenarios are realistic but still cleaner than production telemetry.
- **Same-family judge.** The LLM judge is the same model family as the agents. Its scores are secondary to the exact-match accuracy.
- **Shared load.** Latency was measured under shared concurrency (6), which affected both systems equally because the jobs were interleaved.

## 4. Tool failures (INC-009, INC-010)

INC-009 injects:
- two metrics timeouts, each a real `asyncio` timeout
- a deployment-history SERVICE_UNAVAILABLE
- 50% partial logs

Both systems retried and recovered. The retry counts were the same (9 retries out of 15
failures across all runs). Both kept the partial findings, and the reports list the gaps
as UNKNOWN rather than treating them as healthy. Neither system turned a failed query into
negative evidence.

## 5. Token accounting

Token counts come from the API's `usage` fields:
- `input_tokens`
- `output_tokens`
- `cache_read_input_tokens`
- `cache_creation_input_tokens`

Cost uses Haiku 5.5 list prices: $0.10 input, $0.50 output, $0.125 cache write and $0.01
cache read, all per million tokens. Offline stub runs report tokens as *unavailable*
rather than zero.

## 6. Calibration history (disclosed)

The first real multi-agent run, INC-005 (kept in `results/reports/pre_calibration/`),
ended INCONCLUSIVE even though its leading hypothesis was correct. Two problems caused
this:
- **The Critic requested evidence no tool can provide**, such as cloud volume events.
- **Uncapped contradiction penalties pushed a well-supported hypothesis down to 0.34.**

Before the evaluation, and before any other incident had been run on the real model, I
made four generic changes:
- capped the contradiction penalty
- reduced the gap penalty
- told the Critic to request only evidence the tools can obtain and to judge the proximate cause
- raised the output-token limit for Reasoning and the Critic, which had been truncating

None of these changes mention specific incidents. A 3-incident smoke check (INC-002,
INC-005, INC-012) confirmed the fix, and the evaluation was then run once with no further
tuning.
