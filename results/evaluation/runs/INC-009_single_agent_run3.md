# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-009
- **Title:** User API errors during morning peak
- **Severity:** SEV2
- **Affected services:** api-gateway, user-service
- **Start time:** 2026-09-26T08:00:00+00:00
- **Investigation ID:** inv-9911d2ee9c (single_agent)
- **Final status:** `PROBABLE_ROOT_CAUSE`

## Executive Summary
INC-009: user endpoint errors began ~07:57-08:00Z. user-service error rate rose from ~0.4% to ~23%, and api-gateway error rate from ~0.5% to ~8%. The onset coincides with the user-service 7.2.0 deployment at 07:56Z, whose logged errors are NPEs in ProfileBatchLoader. Latency and resource metrics stayed flat. Likely cause: a regression in the 7.2.0 batch-loader change. Recommended action: roll back to 7.1.3.

## Incident Timeline
| Time (UTC) | Label | Event | Evidence |
|---|---|---|---|
| 2026-09-26T07:31:48Z | OBSERVED EVIDENCE | First log: 4x WARN on api-gateway: 'Slow client upload from 10.4.16.12 (1.9MB)' (first 2026-09-26T07:31:48Z, last 2026-09-26T08:03:47Z) | logpat-api-gateway-88b04940 |
| 2026-09-26T07:35:17Z | OBSERVED EVIDENCE | First log: 5x WARN on auth-service: 'Login rate limit hit for user id u-78' (first 2026-09-26T07:35:17Z, last 2026-09-26T08:17:38Z) | logpat-auth-service-cc8d3b87 |
| 2026-09-26T07:35:33Z | OBSERVED EVIDENCE | First log: 3x WARN on user-service: 'Deprecated API /v1/users/legacy called by client web-74' (first 2026-09-26T07:35:33Z, last 2026-09-26T08:16:20Z) | logpat-user-service-742b555e |
| 2026-09-26T07:46:02Z | OBSERVED EVIDENCE | First log: 3x WARN on postgres: 'duration: 16102 ms statement: SELECT report_rollup()' (first 2026-09-26T07:46:02Z, last 2026-09-26T08:14:06Z) | logpat-postgres-44883ca5 |
| 2026-09-26T07:56:00Z | CONFIRMED FACT | Deployment of user-service 7.1.3->7.2.0 at 2026-09-26T07:56:00Z (SUCCEEDED): Switch ORM to batch loader | dep-c02e51b7 |
| 2026-09-26T07:57:00Z | OBSERVED EVIDENCE | Anomaly onset: user-service error_rate: baseline 0.41 -> window mean 12.5 (max 26.11, change 2984.9%), onset 2026-09-26T07:57:00Z | met-user-service-error_rate-0730-0825 |
| 2026-09-26T07:57:00Z | OBSERVED EVIDENCE | Anomaly onset: api-gateway error_rate: baseline 0.5 -> window mean 4.25 (max 8.65, change 747.7%), onset 2026-09-26T07:57:00Z | met-api-gateway-error_rate-0730-0825 |
| 2026-09-26T07:57:09Z | OBSERVED EVIDENCE | First log: 4x WARN on api-gateway: 'user-service returned 500 for GET /v1/users/81' (first 2026-09-26T07:57:09Z, last 2026-09-26T08:18:48Z) | logpat-api-gateway-c1d874f7 |
| 2026-09-26T07:58:29Z | OBSERVED EVIDENCE | First log: 9x ERROR on user-service: 'NullPointerException in ProfileBatchLoader.load (user-service v7.2.0) req 81' (first 2026-09-26T07:58:29Z, last 2026-09-26T08:23:59Z) | logpat-user-service-2347725d |
| 2026-09-26T08:00:00Z | CONFIRMED FACT | Reported symptom start |  |
| 2026-09-26T08:06:00Z | CONFIRMED FACT | Incident reported |  |

## Observed Symptoms
- **OBSERVED EVIDENCE:** user-service error_rate: baseline 0.41 -> window mean 12.5 (max 26.11, change 2984.9%), onset 2026-09-26T07:57:00Z (met-user-service-error_rate-0730-0825)
- **OBSERVED EVIDENCE:** api-gateway error_rate: baseline 0.5 -> window mean 4.25 (max 8.65, change 747.7%), onset 2026-09-26T07:57:00Z (met-api-gateway-error_rate-0730-0825)

## Investigation Performed

## Root-Cause Hypotheses (ranked by evidence strength)
### 1. H1 - `deployment_regression` in `user-service` (confidence 0.85, critic: n/a)
**INFERENCE:** The user-service 7.2.0 ORM-to-batch-loader change introduced a null-handling defect in ProfileBatchLoader.load, causing request failures that propagate as 500s through api-gateway. Mechanism: After the deployment at 07:56Z, ProfileBatchLoader throws NullPointerException on some requests and returns 500s. api-gateway records 5xx for GET /v1/users/*. Error rate jumps from ~0.4% to ~23% with flat latency and DB utilisation, consistent with fast-failing exceptions rather than saturation.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [CONFIRMED FACT] `dep-c02e51b7` (strong): Deployment of user-service 7.1.3->7.2.0 at 2026-09-26T07:56:00Z (SUCCEEDED): Switch ORM to batch loader
- [OBSERVED EVIDENCE] `met-user-service-error_rate-0730-0825` (strong): user-service error_rate: baseline 0.41 -> window mean 12.5 (max 26.11, change 2984.9%), onset 2026-09-26T07:57:00Z
- [OBSERVED EVIDENCE] `logpat-user-service-2347725d` (strong): 9x ERROR on user-service: 'NullPointerException in ProfileBatchLoader.load (user-service v7.2.0) req 81' (first 2026-09-26T07:58:29Z, last 2026-09-26T08:23:59Z)
- [OBSERVED EVIDENCE] `met-api-gateway-error_rate-0730-0825` (moderate): api-gateway error_rate: baseline 0.5 -> window mean 4.25 (max 8.65, change 747.7%), onset 2026-09-26T07:57:00Z
- [OBSERVED EVIDENCE] `logpat-api-gateway-c1d874f7` (moderate): 4x WARN on api-gateway: 'user-service returned 500 for GET /v1/users/81' (first 2026-09-26T07:57:09Z, last 2026-09-26T08:18:48Z)

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-user-service-p99_latency_ms-0730-0825` (weak): user-service p99_latency_ms: baseline 158.68 -> window mean 159.8 (max 170.4, change 0.7%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Per-endpoint or per-pod error breakdown
- [UNKNOWN] Post-rollback recovery metrics
- [UNKNOWN] Code diff for 7.2.0 to confirm the null path

### 2. H2 - `db_connection_pool_exhaustion` in `postgres` (confidence 0.10, critic: n/a)
**INFERENCE:** Database contention from slow postgres report_rollup() statements caused user-service failures. Mechanism: Slow report_rollup queries (up to 16s) could hold locks or connections and cause user-service errors.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-postgres-44883ca5` (weak): 3x WARN on postgres: 'duration: 16102 ms statement: SELECT report_rollup()' (first 2026-09-26T07:46:02Z, last 2026-09-26T08:14:06Z)

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-user-service-db_conn_util_pct-0730-0825` (strong): user-service db_conn_util_pct: baseline 29.75 -> window mean 30.18 (max 33.82, change 1.4%), onset none detected
- [OBSERVED EVIDENCE] `met-user-service-timeout_rate-0730-0825` (moderate): user-service timeout_rate: baseline 0.05 -> window mean 0.05 (max 0.05, change -0.0%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Postgres lock or wait metrics

### 3. H3 - `traffic_surge` in `api-gateway` (confidence 0.03, critic: n/a)
**INFERENCE:** A client-side traffic or retry surge caused the errors. Mechanism: A retry storm would raise request rate and latency.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- none

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-api-gateway-request_rate-0730-0825` (strong): api-gateway request_rate: baseline 1212.46 -> window mean 1200.93 (max 1338.87, change -1.0%), onset none detected

## Critic Review
- **Verdict:** `NOT_RUN` (rounds reviewed: 0)
- **Reasoning:** 

## Probable Root Cause
MOST PROBABLE EXPLANATION (INFERENCE, not confirmed): deployment_regression in user-service - The user-service 7.2.0 ORM-to-batch-loader change introduced a null-handling defect in ProfileBatchLoader.load, causing request failures that propagate as 500s through api-gateway.

## Corrective Actions
- Roll back user-service from 7.2.0 to 7.1.3 immediately.
- Verify api-gateway and user-service error rates return to ~0.4% and ~0.5%.
- Fix the null handling in ProfileBatchLoader.load and re-release behind a canary.

## Preventive Actions
- Add unit and contract tests for null or missing keys in the batch loader.
- Gate deployments with a canary and automatic rollback on error-rate increase.

## Monitoring Recommendations
- Alert on user-service error rate above 2% within 10 minutes of any deployment.
- Alert on NullPointerException count in ProfileBatchLoader.
- Track postgres report_rollup() duration to rule out contention.

## Evidence Gaps
- [UNKNOWN] query_logs returned incomplete data for all (PARTIAL_DATA)

## Limitations
- Historical incident matching was low similarity (max 0.32) and was used only as an analogy.
- The error log sample is small (9 NPE events, sampled).
- [agent-reported gap] Partial log result: the record listing was truncated (15 more omitted), so absence of other errors cannot be concluded.
- [agent-reported gap] No per-endpoint or per-pod breakdown of user-service errors.
- [agent-reported gap] No code diff or stack trace for the 7.2.0 change.
- [agent-reported gap] No telemetry after 08:25Z to confirm whether the error rate is ongoing or recovered.
- 0 tool calls failed and 1 returned partial data; affected areas are treated as unknown, not healthy.
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: agent submitted

## Final Status
`PROBABLE_ROOT_CAUSE`

The user API error spike began at 07:57-08:00Z, within about a minute of the user-service v7.2.0 deployment (dep-c02e51b7 at 07:56Z, "Switch ORM to batch loader"). The errors are NullPointerExceptions in ProfileBatchLoader.load, and api-gateway 5xx responses from user-service follow. Latency, DB connection utilisation, CPU, timeouts and request rate stayed at baseline, so this looks like a code-level failure rather than capacity exhaustion. Rolling back user-service to 7.1.3 is the recommended mitigation; confirmation is pending a post-rollback recovery check.

## Execution Statistics
```json
{
  "rounds": 1,
  "tool_calls": 10,
  "tool_failures": 3,
  "tool_retries": 3,
  "partial_results": 1,
  "agent_failures": 0,
  "agent_retries": 0,
  "invalid_llm_outputs": 2,
  "messages_exchanged": 0,
  "evidence_records": 53,
  "duration_s": 34.69,
  "tokens": {
    "input_tokens": 12,
    "output_tokens": 8773,
    "cache_read_tokens": 47364,
    "cache_write_tokens": 12888,
    "llm_calls": 5,
    "cost_usd": 0.00647234
  },
  "tokens_by_agent": {
    "single_agent": {
      "input_tokens": 12,
      "output_tokens": 8773,
      "cache_read_tokens": 47364,
      "cache_write_tokens": 12888,
      "llm_calls": 5,
      "cost_usd": 0.00647234
    }
  }
}
```
