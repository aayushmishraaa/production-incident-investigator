# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-009
- **Title:** User API errors during morning peak
- **Severity:** SEV2
- **Affected services:** api-gateway, user-service
- **Start time:** 2026-09-26T08:00:00+00:00
- **Investigation ID:** inv-5247f94cf2 (single_agent)
- **Final status:** `PROBABLE_ROOT_CAUSE`

## Executive Summary
User API errors during the morning peak (INC-009) began at 07:57-08:00Z, coinciding with the user-service 7.1.3 -> 7.2.0 deployment at 07:56Z (switch ORM to batch loader). user-service error rate rose from ~0.4% to ~23% and api-gateway 5xx rose from ~0.5% to ~7.8%. Logs show a NullPointerException in ProfileBatchLoader.load on v7.2.0 starting 07:57:17Z, consistent with the deployment as the cause. Latency, DB connection utilization, timeouts and request rate were flat, so this is not a capacity or traffic problem.

## Incident Timeline
| Time (UTC) | Label | Event | Evidence |
|---|---|---|---|
| 2026-09-26T07:32:16Z | OBSERVED EVIDENCE | First log: 3x WARN on postgres: 'duration: 19702 ms statement: SELECT report_rollup()' (first 2026-09-26T07:32:16Z, last 2026-09-26T08:21:19Z) | logpat-postgres-44883ca5 |
| 2026-09-26T07:33:45Z | OBSERVED EVIDENCE | First log: 3x WARN on order-service: 'Inventory reservation retry for sku-69' (first 2026-09-26T07:33:45Z, last 2026-09-26T08:16:55Z) | logpat-order-service-95abd1bb |
| 2026-09-26T07:35:33Z | OBSERVED EVIDENCE | First log: 4x WARN on user-service: 'Deprecated API /v1/users/legacy called by client web-74' (first 2026-09-26T07:35:33Z, last 2026-09-26T08:16:20Z) | logpat-user-service-742b555e |
| 2026-09-26T07:56:00Z | CONFIRMED FACT | Deployment of user-service 7.1.3->7.2.0 at 2026-09-26T07:56:00Z (SUCCEEDED): Switch ORM to batch loader | dep-c02e51b7 |
| 2026-09-26T07:57:00Z | OBSERVED EVIDENCE | Anomaly onset: user-service error_rate: baseline 0.41 -> window mean 12.5 (max 26.11, change 2984.9%), onset 2026-09-26T07:57:00Z | met-user-service-error_rate-0730-0825 |
| 2026-09-26T07:57:00Z | OBSERVED EVIDENCE | Anomaly onset: api-gateway error_rate: baseline 0.5 -> window mean 4.25 (max 8.65, change 747.7%), onset 2026-09-26T07:57:00Z | met-api-gateway-error_rate-0730-0825 |
| 2026-09-26T07:57:17Z | OBSERVED EVIDENCE | First log: 10x ERROR on user-service: 'NullPointerException in ProfileBatchLoader.load (user-service v7.2.0) req 18' (first 2026-09-26T07:57:17Z, last 2026-09-26T08:20:12Z) | logpat-user-service-2347725d |
| 2026-09-26T08:00:00Z | CONFIRMED FACT | Reported symptom start |  |
| 2026-09-26T08:00:08Z | OBSERVED EVIDENCE | First log: 6x WARN on api-gateway: 'user-service returned 500 for GET /v1/users/23' (first 2026-09-26T08:00:08Z, last 2026-09-26T08:18:48Z) | logpat-api-gateway-c1d874f7 |
| 2026-09-26T08:06:00Z | CONFIRMED FACT | Incident reported |  |

## Observed Symptoms
- **OBSERVED EVIDENCE:** user-service error_rate: baseline 0.41 -> window mean 12.5 (max 26.11, change 2984.9%), onset 2026-09-26T07:57:00Z (met-user-service-error_rate-0730-0825)
- **OBSERVED EVIDENCE:** api-gateway error_rate: baseline 0.5 -> window mean 4.25 (max 8.65, change 747.7%), onset 2026-09-26T07:57:00Z (met-api-gateway-error_rate-0730-0825)

## Investigation Performed

## Root-Cause Hypotheses (ranked by evidence strength)
### 1. H1 - `deployment_regression` in `user-service` (confidence 0.80, critic: n/a)
**INFERENCE:** Regression in user-service v7.2.0 (ORM batch loader change) causes NullPointerException in ProfileBatchLoader.load, producing HTTP 500s that api-gateway surfaces to users. Mechanism: Deployment at 07:56Z introduces batch loader; some requests hit a null in ProfileBatchLoader.load, throwing NPE and returning 500. user-service error rate jumps at 07:57-08:00; api-gateway error rate follows at 08:00 as it proxies the 500s.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [CONFIRMED FACT] `dep-c02e51b7` (strong): Deployment of user-service 7.1.3->7.2.0 at 2026-09-26T07:56:00Z (SUCCEEDED): Switch ORM to batch loader
- [OBSERVED EVIDENCE] `met-user-service-error_rate-0730-0825` (strong): user-service error_rate: baseline 0.41 -> window mean 12.5 (max 26.11, change 2984.9%), onset 2026-09-26T07:57:00Z
- [OBSERVED EVIDENCE] `logpat-user-service-2347725d` (strong): 10x ERROR on user-service: 'NullPointerException in ProfileBatchLoader.load (user-service v7.2.0) req 18' (first 2026-09-26T07:57:17Z, last 2026-09-26T08:20:12Z)
- [OBSERVED EVIDENCE] `met-api-gateway-error_rate-0730-0825` (moderate): api-gateway error_rate: baseline 0.5 -> window mean 4.25 (max 8.65, change 747.7%), onset 2026-09-26T07:57:00Z
- [OBSERVED EVIDENCE] `logpat-api-gateway-c1d874f7` (moderate): 6x WARN on api-gateway: 'user-service returned 500 for GET /v1/users/23' (first 2026-09-26T08:00:08Z, last 2026-09-26T08:18:48Z)

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-user-service-p99_latency_ms-0730-0825` (weak): user-service p99_latency_ms: baseline 158.68 -> window mean 159.8 (max 170.4, change 0.7%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Per-endpoint error breakdown and fraction of requests hitting the batch loader
- [UNKNOWN] Log query was partial; the 13 omitted records could change counts
- [UNKNOWN] No code diff of 7.2.0 reviewed
- [UNKNOWN] No rollback test performed

### 2. H2 - `resource_saturation` in `postgres` (confidence 0.10, critic: n/a)
**INFERENCE:** Slow report_rollup() queries in postgres create DB contention affecting user-service. Mechanism: Long-running SELECT report_rollup() (16-20s) could hold locks or consume I/O, slowing user queries.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-postgres-44883ca5` (weak): 3x WARN on postgres: 'duration: 19702 ms statement: SELECT report_rollup()' (first 2026-09-26T07:32:16Z, last 2026-09-26T08:21:19Z)

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-user-service-db_conn_util_pct-0730-0825` (strong): user-service db_conn_util_pct: baseline 29.75 -> window mean 30.18 (max 33.82, change 1.4%), onset none detected
- [OBSERVED EVIDENCE] `met-user-service-p99_latency_ms-0730-0825` (moderate): user-service p99_latency_ms: baseline 158.68 -> window mean 159.8 (max 170.4, change 0.7%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] postgres metrics not queried
- [UNKNOWN] lock/wait data not available

## Critic Review
- **Verdict:** `NOT_RUN` (rounds reviewed: 0)
- **Reasoning:** 

## Probable Root Cause
MOST PROBABLE EXPLANATION (INFERENCE, not confirmed): deployment_regression in user-service - Regression in user-service v7.2.0 (ORM batch loader change) causes NullPointerException in ProfileBatchLoader.load, producing HTTP 500s that api-gateway surfaces to users.

## Corrective Actions
- Roll back user-service from 7.2.0 to 7.1.3 (verify error rate recovers in gateway and user-service)
- Hotfix the null handling in ProfileBatchLoader.load before redeploying

## Preventive Actions
- Add pre-prod/canary tests covering null inputs for batch loader paths
- Gate deployments on error-rate canary comparison

## Monitoring Recommendations
- Alert on user-service error rate > 2% within 5 minutes of any deployment
- Track NullPointerException count per version

## Evidence Gaps
- [UNKNOWN] query_logs returned incomplete data for all (PARTIAL_DATA)

## Limitations
- Historical analogy (hist-HIST-2025-022) has low similarity (0.319) and is not evidence
- Logs were partial
- [agent-reported gap] Log query was partial (13 records omitted); counts may be understated
- [agent-reported gap] Postgres service metrics were not queried
- [agent-reported gap] No per-endpoint breakdown of failing requests
- 0 tool calls failed and 1 returned partial data; affected areas are treated as unknown, not healthy.
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: agent submitted

## Final Status
`PROBABLE_ROOT_CAUSE`

Most likely root cause is the user-service 7.2.0 deployment (ProfileBatchLoader NPE) causing 500s that propagate through api-gateway. Rollback is the recommended immediate action. Status is probable rather than confirmed because the log query was incomplete and the code change was not reviewed.

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
  "invalid_llm_outputs": 0,
  "messages_exchanged": 0,
  "evidence_records": 50,
  "duration_s": 17.28,
  "tokens": {
    "input_tokens": 8,
    "output_tokens": 3287,
    "cache_read_tokens": 20015,
    "cache_write_tokens": 7489,
    "llm_calls": 3,
    "cost_usd": 0.0027805750000000004
  },
  "tokens_by_agent": {
    "single_agent": {
      "input_tokens": 8,
      "output_tokens": 3287,
      "cache_read_tokens": 20015,
      "cache_write_tokens": 7489,
      "llm_calls": 3,
      "cost_usd": 0.0027805750000000004
    }
  }
}
```
