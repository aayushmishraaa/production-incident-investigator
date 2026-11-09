# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-009
- **Title:** User API errors during morning peak
- **Severity:** SEV2
- **Affected services:** api-gateway, user-service
- **Start time:** 2026-09-26T08:00:00+00:00
- **Investigation ID:** inv-4d7f7ac436 (single_agent)
- **Final status:** `PROBABLE_ROOT_CAUSE`

## Executive Summary
User-service release 7.2.0 (deployed 07:56Z, switching the ORM to a batch loader) is the most likely cause of the INC-009 user API errors. user-service 5xx-level error rate rose from ~0.4% to ~12.5% (peak 26%) starting 07:57Z, and api-gateway error rate rose from ~0.5% to ~4.3% (peak 8.7%) with the same onset. Every ERROR log in the window is a NullPointerException in ProfileBatchLoader.load on v7.2.0. Latency, DB connection utilisation, CPU and timeouts were flat, so this is an application-level failure, not saturation.

## Incident Timeline
| Time (UTC) | Label | Event | Evidence |
|---|---|---|---|
| 2026-09-26T07:33:45Z | OBSERVED EVIDENCE | First log: 4x WARN on order-service: 'Inventory reservation retry for sku-69' (first 2026-09-26T07:33:45Z, last 2026-09-26T08:13:33Z) | logpat-order-service-95abd1bb |
| 2026-09-26T07:35:33Z | OBSERVED EVIDENCE | First log: 3x WARN on user-service: 'Deprecated API /v1/users/legacy called by client web-74' (first 2026-09-26T07:35:33Z, last 2026-09-26T08:23:14Z) | logpat-user-service-742b555e |
| 2026-09-26T07:46:02Z | OBSERVED EVIDENCE | First log: 4x WARN on postgres: 'duration: 16102 ms statement: SELECT report_rollup()' (first 2026-09-26T07:46:02Z, last 2026-09-26T08:14:06Z) | logpat-postgres-44883ca5 |
| 2026-09-26T07:56:00Z | CONFIRMED FACT | Deployment of user-service 7.1.3->7.2.0 at 2026-09-26T07:56:00Z (SUCCEEDED): Switch ORM to batch loader | dep-c02e51b7 |
| 2026-09-26T07:57:00Z | OBSERVED EVIDENCE | Anomaly onset: user-service error_rate: baseline 0.41 -> window mean 12.5 (max 26.11, change 2984.9%), onset 2026-09-26T07:57:00Z | met-user-service-error_rate-0730-0825 |
| 2026-09-26T07:57:00Z | OBSERVED EVIDENCE | Anomaly onset: api-gateway error_rate: baseline 0.5 -> window mean 4.25 (max 8.65, change 747.7%), onset 2026-09-26T07:57:00Z | met-api-gateway-error_rate-0730-0825 |
| 2026-09-26T07:57:09Z | OBSERVED EVIDENCE | First log: 4x WARN on api-gateway: 'user-service returned 500 for GET /v1/users/81' (first 2026-09-26T07:57:09Z, last 2026-09-26T08:12:37Z) | logpat-api-gateway-c1d874f7 |
| 2026-09-26T07:57:17Z | OBSERVED EVIDENCE | First log: 10x ERROR on user-service: 'NullPointerException in ProfileBatchLoader.load (user-service v7.2.0) req 18' (first 2026-09-26T07:57:17Z, last 2026-09-26T08:22:46Z) | logpat-user-service-2347725d |
| 2026-09-26T08:00:00Z | CONFIRMED FACT | Reported symptom start |  |
| 2026-09-26T08:06:00Z | CONFIRMED FACT | Incident reported |  |

## Observed Symptoms
- **OBSERVED EVIDENCE:** user-service error_rate: baseline 0.41 -> window mean 12.5 (max 26.11, change 2984.9%), onset 2026-09-26T07:57:00Z (met-user-service-error_rate-0730-0825)
- **OBSERVED EVIDENCE:** api-gateway error_rate: baseline 0.5 -> window mean 4.25 (max 8.65, change 747.7%), onset 2026-09-26T07:57:00Z (met-api-gateway-error_rate-0730-0825)

## Investigation Performed

## Root-Cause Hypotheses (ranked by evidence strength)
### 1. H1 - `deployment_regression` in `user-service` (confidence 0.80, critic: n/a)
**INFERENCE:** Regression in user-service v7.2.0 ProfileBatchLoader (batch ORM loader switch) throws NullPointerException on a subset of requests, producing 500s that propagate to api-gateway. Mechanism: After deploy dep-c02e51b7 at 07:56Z, requests hitting ProfileBatchLoader.load hit a null-dereference; user-service returns 500, api-gateway logs upstream 500s for GET /v1/users/* from 07:57Z.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [CONFIRMED FACT] `dep-c02e51b7` (strong): Deployment of user-service 7.1.3->7.2.0 at 2026-09-26T07:56:00Z (SUCCEEDED): Switch ORM to batch loader
- [OBSERVED EVIDENCE] `met-user-service-error_rate-0730-0825` (strong): user-service error_rate: baseline 0.41 -> window mean 12.5 (max 26.11, change 2984.9%), onset 2026-09-26T07:57:00Z
- [OBSERVED EVIDENCE] `met-api-gateway-error_rate-0730-0825` (strong): api-gateway error_rate: baseline 0.5 -> window mean 4.25 (max 8.65, change 747.7%), onset 2026-09-26T07:57:00Z
- [OBSERVED EVIDENCE] `logpat-user-service-2347725d` (strong): 10x ERROR on user-service: 'NullPointerException in ProfileBatchLoader.load (user-service v7.2.0) req 18' (first 2026-09-26T07:57:17Z, last 2026-09-26T08:22:46Z)
- [OBSERVED EVIDENCE] `logpat-api-gateway-c1d874f7` (moderate): 4x WARN on api-gateway: 'user-service returned 500 for GET /v1/users/81' (first 2026-09-26T07:57:09Z, last 2026-09-26T08:12:37Z)

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-user-service-p99_latency_ms-0730-0825` (weak): user-service p99_latency_ms: baseline 158.68 -> window mean 159.8 (max 170.4, change 0.7%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Pre-deploy 7.1.3 error logs for comparison (no NPE pattern found before 07:57 but log query was partial)
- [UNKNOWN] Per-endpoint error breakdown
- [UNKNOWN] Confirmation of the exact error code returned (500 per gateway logs)

### 2. H2 - `resource_saturation` in `postgres` (confidence 0.10, critic: n/a)
**INFERENCE:** Slow report_rollup() statements on postgres (up to 16s) degrade the shared database and contribute to user-service errors. Mechanism: Long-running report queries could hold locks or resources, causing user-service DB calls to fail.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-postgres-44883ca5` (weak): 4x WARN on postgres: 'duration: 16102 ms statement: SELECT report_rollup()' (first 2026-09-26T07:46:02Z, last 2026-09-26T08:14:06Z)

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-user-service-db_conn_util_pct-0730-0825` (strong): user-service db_conn_util_pct: baseline 29.75 -> window mean 30.18 (max 33.82, change 1.4%), onset none detected
- [OBSERVED EVIDENCE] `logpat-user-service-2347725d` (moderate): 10x ERROR on user-service: 'NullPointerException in ProfileBatchLoader.load (user-service v7.2.0) req 18' (first 2026-09-26T07:57:17Z, last 2026-09-26T08:22:46Z)
- [OBSERVED EVIDENCE] `met-user-service-timeout_rate-0730-0825` (moderate): user-service timeout_rate: baseline 0.05 -> window mean 0.05 (max 0.05, change -0.0%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Postgres error logs or lock/wait metrics
- [UNKNOWN] Whether user-service queries touch the same tables

### 3. H3 - `traffic_surge` in `api-gateway` (confidence 0.05, critic: n/a)
**INFERENCE:** Client-driven load change (e.g. deprecated /v1/users/legacy traffic) triggers errors. Mechanism: Increased legacy-endpoint traffic might overload user-service.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-user-service-742b555e` (weak): 3x WARN on user-service: 'Deprecated API /v1/users/legacy called by client web-74' (first 2026-09-26T07:35:33Z, last 2026-09-26T08:23:14Z)

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-api-gateway-request_rate-0730-0825` (strong): api-gateway request_rate: baseline 1212.46 -> window mean 1200.93 (max 1338.87, change -1.0%), onset none detected
- [OBSERVED EVIDENCE] `met-user-service-cpu_pct-0730-0825` (strong): user-service cpu_pct: baseline 30.1 -> window mean 29.91 (max 32.45, change -0.6%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Per-endpoint traffic breakdown

## Critic Review
- **Verdict:** `NOT_RUN` (rounds reviewed: 0)
- **Reasoning:** 

## Probable Root Cause
MOST PROBABLE EXPLANATION (INFERENCE, not confirmed): deployment_regression in user-service - Regression in user-service v7.2.0 ProfileBatchLoader (batch ORM loader switch) throws NullPointerException on a subset of requests, producing 500s that propagate to api-gateway.

## Corrective Actions
- Roll back user-service from 7.2.0 to 7.1.3 (dep-c02e51b7), then confirm error rates return to baseline
- Fix the null handling in ProfileBatchLoader.load and re-release after staging validation

## Preventive Actions
- Add contract/integration tests covering batch loader null and missing-profile cases before release
- Use canary or progressive rollout with automatic rollback on error-rate increase

## Monitoring Recommendations
- Alert on user-service error_rate > 2% for 3 minutes, and on any new exception pattern after deploy
- Track ProfileBatchLoader NPE count per version

## Evidence Gaps
- [UNKNOWN] query_logs returned incomplete data for all (PARTIAL_DATA)
- [UNKNOWN] query_logs returned incomplete data for service=user-service, keyword=ProfileBatchLoader (PARTIAL_DATA)

## Limitations
- Temporal correlation with the deploy is strong but not proven by a rollback
- Historical incident matches were low similarity (0.22-0.35) and used only as analogy
- [agent-reported gap] Log query for 07:00-07:57 returned no records and is flagged as incomplete, so pre-deploy absence of NPEs is not fully confirmed
- [agent-reported gap] Log results were truncated (13 records omitted)
- [agent-reported gap] No per-endpoint error breakdown available
- [agent-reported gap] Postgres lock/wait data not available
- 0 tool calls failed and 2 returned partial data; affected areas are treated as unknown, not healthy.
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: agent submitted

## Final Status
`PROBABLE_ROOT_CAUSE`

The evidence points most strongly to the user-service 7.2.0 deployment (ProfileBatchLoader NPEs starting 07:57Z, one minute after the deploy) as the cause of the user API 5xx errors propagating through api-gateway. Status is PROBABLE rather than confirmed because the log query was partial and no rollback test has been run. Postgres slow reports and traffic changes are not supported by the metrics.

## Execution Statistics
```json
{
  "rounds": 1,
  "tool_calls": 11,
  "tool_failures": 3,
  "tool_retries": 3,
  "partial_results": 2,
  "agent_failures": 0,
  "agent_retries": 0,
  "invalid_llm_outputs": 0,
  "messages_exchanged": 0,
  "evidence_records": 51,
  "duration_s": 19.71,
  "tokens": {
    "input_tokens": 8,
    "output_tokens": 4197,
    "cache_read_tokens": 15554,
    "cache_write_tokens": 12647,
    "llm_calls": 3,
    "cost_usd": 0.003835715
  },
  "tokens_by_agent": {
    "single_agent": {
      "input_tokens": 8,
      "output_tokens": 4197,
      "cache_read_tokens": 15554,
      "cache_write_tokens": 12647,
      "llm_calls": 3,
      "cost_usd": 0.003835715
    }
  }
}
```
