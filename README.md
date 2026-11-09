# Multi-Agent Production Incident Investigator

Six cooperating LLM agents investigate a production incident, starting from the incident
report and working against simulated operational data: logs, metrics, deployments,
configuration changes, the service dependency graph and historical incidents. The output
is an evidence-grounded report with ranked hypotheses. When the evidence doesn't support
a conclusion, the report says so: **INCONCLUSIVE** is an allowed outcome.

A single-agent baseline uses the same tools and limits, and an evaluation harness
compares the two systems across 12 synthetic incidents.

| | |
|---|---|
| Language / runtime | Python 3.12, asyncio |
| Orchestration | LangGraph `StateGraph` (plan → gather → reason → critique → decide → report) |
| LLM | Anthropic Claude (`claude-haiku-5-5` by default) via the official SDK; scripted stub for offline tests |
| Schemas | Pydantic v2 for every tool input/output, agent message, finding, hypothesis, verdict and report |
| Storage | SQLite investigation history, JSON/JSONL dataset |
| Interfaces | FastAPI (Swagger at `/docs`) and a CLI |

## Documentation

- [docs/architecture.md](docs/architecture.md): architecture, with 7 Mermaid diagrams (also in `docs/diagrams/*.mmd`)
- [docs/agent_coordination.md](docs/agent_coordination.md): a worked example of the agents coordinating
- [docs/evaluation.md](docs/evaluation.md): evaluation methodology, results and discussion
- [docs/api_examples.md](docs/api_examples.md): sample API requests and responses
- [TECHNICAL_NOTE.md](TECHNICAL_NOTE.md): design decisions and trade-offs (≤ 500 words)
- `results/reports/`: sample investigation reports (Markdown and JSON)
- `results/evaluation/`: `evaluation_results.json`, `evaluation_runs.csv`, `summary_table.md`, and every run's report under `runs/`
- `results/charts/`: accuracy, grounding, latency, tool-call and token charts, plus confusion matrices
- `results/coverage_html/`: the test coverage report
- `transcript/`: the coding-assistant transcript (required by the assignment)
- `demo/walkthrough.mp4`: a 4.5-minute narrated walkthrough built from real runs (`scripts/demo_live.py`, `scripts/make_demo_video.py`)

## Setup

Requires Python 3.11 or newer. With [uv](https://github.com/astral-sh/uv):

```bash
uv venv --python 3.12 && source .venv/bin/activate
uv pip install -r requirements.txt
cp .env.example .env          # then set ANTHROPIC_API_KEY
python scripts/generate_dataset.py   # optional: dataset is committed; regenerates deterministically
```

With plain pip, use `python -m venv .venv && pip install -r requirements.txt` instead.

Without an API key, every command takes `--provider stub`. That runs the scripted stub,
which exercises the whole pipeline offline. Its outputs are **not** meaningful
diagnoses, and it reports token usage as unavailable.

## Usage

### CLI

```bash
python -m app.cli incidents                                   # list the 12 synthetic incidents
python -m app.cli investigate --incident INC-001              # multi-agent investigation
python -m app.cli investigate --incident INC-005 --system single_agent
python -m app.cli investigate --incident INC-010 --provider stub   # offline
python -m app.cli evaluate --runs 3                           # full comparison (both systems)
python -m app.cli evaluate --incidents INC-001 INC-005 --runs 1
python -m app.cli history                                     # persisted investigations
python -m app.cli spend                                       # cumulative LLM spend vs cap
python -m app.cli serve                                       # FastAPI on :8000
```

### API

Start the server with `uvicorn app.main:app` (or `python -m app.cli serve`), then open
`http://127.0.0.1:8000/docs`.

| Method | Path | Purpose |
|---|---|---|
| POST | `/investigate` | Start an investigation (`incident_id` or a full `incident`, optional `config`, `system`, `wait`) |
| GET | `/investigations/{id}` | Status and full shared state (tasks, messages, evidence, hypotheses, verdicts, stats) |
| GET | `/investigations/{id}/report` | Final report (JSON) |
| GET | `/investigations/{id}/evidence` | Collected evidence records and evidence gaps |
| GET | `/investigations/{id}/timeline` | Investigation timeline and incident timeline |
| GET | `/investigations` | Investigation history (SQLite) |
| GET | `/incidents` | Available synthetic incidents |
| GET | `/health` | Health check |
| POST | `/evaluate` | Run the evaluation in the background |
| GET | `/evaluate/results` | Latest evaluation results |

```bash
curl -s -X POST localhost:8000/investigate -H 'content-type: application/json' \
  -d '{"incident_id":"INC-007","config":{"max_rounds":3,"max_tool_calls":60}}'
```

## Configuration

Settings are read from the environment or `.env`.

| Variable | Default | Meaning |
|---|---|---|
| `LLM_PROVIDER` | `anthropic` | `anthropic` or `stub` |
| `LLM_MODEL` | `claude-haiku-5-5` | Model used by every agent and the baseline |
| `LLM_EFFORT` | `low` | Effort level for the model |
| `TOTAL_COST_CAP_USD` | `3.0` | Hard cap on cumulative spend, tracked in `results/cost_ledger.json` |

Per-investigation limits are set on `InvestigationConfig`, either in the API body or in
code:

| Field | Default |
|---|---|
| `max_rounds` | 3 |
| `max_tool_calls` | 60 |
| `max_tool_retries` | 2 |
| `max_agent_retries` | 1 |
| `max_agent_steps` | 6 |
| `tool_timeout_s` | 2.0 |
| `investigation_timeout_s` | 300 |
| `max_llm_calls` | 80 |
| `max_cost_usd` | 0.25 |
| `parallelism` | 4 |
| `random_failure_rate` | 0 |

## Tests

```bash
pytest                                     # 98 tests, offline (stub LLM), ~10 s
pytest --cov=app --cov-report=html:results/coverage_html
```

The tests cover:
- every agent and every tool
- structured messaging and shared state
- parallel execution (timing-based)
- DAG dependencies
- the critic feedback loop, critic rejection and approval blocking
- round, tool, LLM-call and timeout limits
- tool timeouts, partial data and retries
- agent crashes and retries, failed parallel tasks, invalid or malformed LLM output
- evidence-reference validation
- inconclusive outcomes
- the baseline
- metric calculations, report generation, persistence and the API
- ground-truth isolation, checked both statically (import and AST scan) and at runtime (file-read spy)

## Dataset

`scripts/generate_dataset.py` deterministically generates 12 incidents across 9
services: api-gateway, auth, payment, user, order, notification, postgres, redis and
message-queue. For each incident it produces:
- about 280 logs, including noise and unrelated WARNs
- 1-minute metric series covering T0−60m to T0+30m
- deployments and configuration changes, including decoys
- a fault-injection profile

Ground truth is written separately to `data/ground_truth/`. Only
`app/evaluation/ground_truth.py` reads it, and the tool data store refuses to.

| ID | Scenario | Trap |
|---|---|---|
| INC-001 | DB connection pool exhaustion (leak) | unrelated notification deploy 6 min before |
| INC-002 | Faulty auth-service deployment | unrelated feature-flag change |
| INC-003 | Upstream auth-service degradation | payment-service "slow" but internally healthy; log-level config change |
| INC-004 | CPU saturation (batch job) | flat request rate rules out traffic |
| INC-005 | Postgres storage degradation | payment deploy 8 min before, *after* the degradation began |
| INC-006 | Conflicting observability (node network) | DB error logs while DB metrics are healthy or missing |
| INC-007 | Config regression (client timeout 3000→300 ms) | old payment deploy; payment metrics healthy |
| INC-008 | Redis cache degradation | Postgres CPU alarm is a symptom |
| INC-009 | Deployment regression under tool failures | metrics timeouts, partial logs, deployments unavailable |
| INC-010 | Insufficient evidence | missing telemetry; expected outcome INCONCLUSIVE |
| INC-011 | Traffic surge (client retry storm) | user-service deploy decoy |
| INC-012 | Config regression masquerading as pool exhaustion | matches a historical pool-exhaustion incident |

## External dependencies and limitations

- **Anthropic API.** Real runs need an Anthropic API key. Everything else runs locally.
- **Simulated environment.** The operational data is synthetic, and the tools query it rather than real observability back-ends.
- **Confidence scores.** These are rule-based evidence-strength scores, not calibrated probabilities.

See `TECHNICAL_NOTE.md` and `docs/evaluation.md` for the known limitations.
