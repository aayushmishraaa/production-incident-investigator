# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-012
- **Title:** Payment connection pool timeouts
- **Severity:** SEV2
- **Affected services:** payment-service
- **Start time:** 2026-10-05T10:10:00+00:00
- **Investigation ID:** inv-36a8b654e4 (single_agent)
- **Final status:** `PROBABLE_ROOT_CAUSE`

## Executive Summary
payment-service's DB connection pool (payment-db-pool) was cut from max_size 50 to 10 by a config change at 10:04Z (cfg-56d39584, config-bot, OPS-2669). Pool utilisation hit 100% from 10:05-10:10, and the pool timeout errors began at 10:06, with error rate rising from ~0.8% to ~17% and timeouts from ~0.1% to ~12%. The pool-exhaustion symptom is therefore consistent with the config change, and it precedes the errors. It does not look like last year's connection leak: Postgres connection utilisation dropped rather than rose. The reported latency increase is not visible in the p99 metric (flat at ~300ms), so the impact is errors/timeouts rather than latency.

## Incident Timeline
| Time (UTC) | Label | Event | Evidence |
|---|---|---|---|
| 2026-10-05T09:45:26Z | OBSERVED EVIDENCE | First log: 7x WARN on payment-service: 'Card network soft decline (code 05) for charge ch_98' (first 2026-10-05T09:45:26Z, last 2026-10-05T10:22:54Z) | logpat-payment-service-7e9bf84f |
| 2026-10-05T10:04:00Z | CONFIRMED FACT | Config change on payment-service: db.pool.max_size 50 -> 10 at 2026-10-05T10:04:00Z (OPS-2669) | cfg-56d39584 |
| 2026-10-05T10:05:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service db_conn_util_pct: baseline 34.95 -> window mean 69.43 (max 100.0, change 98.7%), onset 2026-10-05T10:05:00Z | met-payment-service-db_conn_util_pct-0940-1035 |
| 2026-10-05T10:06:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service error_rate: baseline 0.8 -> window mean 9.17 (max 18.85, change 1040.5%), onset 2026-10-05T10:06:00Z | met-payment-service-error_rate-0940-1035 |
| 2026-10-05T10:06:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service timeout_rate: baseline 0.1 -> window mean 6.3 (max 13.3, change 6147.1%), onset 2026-10-05T10:06:00Z | met-payment-service-timeout_rate-0940-1035 |
| 2026-10-05T10:06:13Z | OBSERVED EVIDENCE | First log: 29x ERROR on payment-service: 'Timeout acquiring connection from pool payment-db-pool after 5000ms (active=10, idle=0, waiting=29)' (first 2026-10-05T10:06:13Z, last 2026-10-05T10:34:18Z) | logpat-payment-service-7d1739af |
| 2026-10-05T10:10:00Z | CONFIRMED FACT | Reported symptom start |  |
| 2026-10-05T10:16:00Z | CONFIRMED FACT | Incident reported |  |

## Observed Symptoms
- **OBSERVED EVIDENCE:** payment-service db_conn_util_pct: baseline 34.95 -> window mean 69.43 (max 100.0, change 98.7%), onset 2026-10-05T10:05:00Z (met-payment-service-db_conn_util_pct-0940-1035)
- **OBSERVED EVIDENCE:** payment-service error_rate: baseline 0.8 -> window mean 9.17 (max 18.85, change 1040.5%), onset 2026-10-05T10:06:00Z (met-payment-service-error_rate-0940-1035)
- **OBSERVED EVIDENCE:** payment-service timeout_rate: baseline 0.1 -> window mean 6.3 (max 13.3, change 6147.1%), onset 2026-10-05T10:06:00Z (met-payment-service-timeout_rate-0940-1035)

## Investigation Performed

## Root-Cause Hypotheses (ranked by evidence strength)
### 1. H1 - `configuration_regression` in `payment-service` (confidence 0.80, critic: n/a)
**INFERENCE:** Config change reduced db.pool.max_size from 50 to 10 at 10:04Z, starving the payment DB pool under normal load. Mechanism: With max_size=10, active connections saturate at 10 with idle=0 and a growing waiting queue (up to 92). Requests then time out after 5000ms waiting for a connection, producing errors and timeouts. Postgres connection use falls at the same time, consistent with fewer client connections being opened. Request rate is unchanged, so the cause is capacity, not traffic.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [CONFIRMED FACT] `cfg-56d39584` (strong): Config change on payment-service: db.pool.max_size 50 -> 10 at 2026-10-05T10:04:00Z (OPS-2669)
- [OBSERVED EVIDENCE] `met-payment-service-db_conn_util_pct-0940-1035` (strong): payment-service db_conn_util_pct: baseline 34.95 -> window mean 69.43 (max 100.0, change 98.7%), onset 2026-10-05T10:05:00Z
- [OBSERVED EVIDENCE] `logpat-payment-service-7d1739af` (strong): 29x ERROR on payment-service: 'Timeout acquiring connection from pool payment-db-pool after 5000ms (active=10, idle=0, waiting=29)' (first 2026-10-05T10:06:13Z, last 2026-10-05T10:34:18Z)
- [OBSERVED EVIDENCE] `met-payment-service-error_rate-0940-1035` (strong): payment-service error_rate: baseline 0.8 -> window mean 9.17 (max 18.85, change 1040.5%), onset 2026-10-05T10:06:00Z
- [OBSERVED EVIDENCE] `met-payment-service-timeout_rate-0940-1035` (strong): payment-service timeout_rate: baseline 0.1 -> window mean 6.3 (max 13.3, change 6147.1%), onset 2026-10-05T10:06:00Z
- [OBSERVED EVIDENCE] `met-postgres-db_conn_util_pct-0940-1035` (moderate): postgres db_conn_util_pct: baseline 39.83 -> window mean 30.56 (max 43.9, change -23.3%), onset 2026-10-05T10:07:00Z
- [OBSERVED EVIDENCE] `met-postgres-cpu_pct-0940-1035` (weak): postgres cpu_pct: baseline 35.02 -> window mean 35.11 (max 37.77, change 0.3%), onset none detected

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-payment-service-p99_latency_ms-0940-1035` (moderate): payment-service p99_latency_ms: baseline 299.15 -> window mean 300.84 (max 325.6, change 0.6%), onset none detected
- [OBSERVED EVIDENCE] `met-payment-service-request_rate-0940-1035` (weak): payment-service request_rate: baseline 300.21 -> window mean 299.16 (max 325.13, change -0.4%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Change-approval and intent for OPS-2669 (was a 10 value deliberate or a unit/typo error?)
- [UNKNOWN] Pool wait-time and acquisition-latency metrics
- [UNKNOWN] Pre-change pool usage data for the same window

### 2. H2 - `db_connection_pool_exhaustion` in `payment-service` (confidence 0.12, critic: n/a)
**INFERENCE:** Connection leak in the payment path (like HIST-2025-014) exhausted the pool independently of the config change. Mechanism: A leak holds pooled connections until the pool is exhausted. Waiting-queue growth and active=10 would look the same.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [INFERENCE] `hist-HIST-2025-014` (weak): Past incident HIST-2025-014 'Payment latency from leaked DB connections' (similarity 0.337): Connection leak in refund path held pooled connections; pool exhausted.
- [OBSERVED EVIDENCE] `logpat-payment-service-7d1739af` (weak): 29x ERROR on payment-service: 'Timeout acquiring connection from pool payment-db-pool after 5000ms (active=10, idle=0, waiting=29)' (first 2026-10-05T10:06:13Z, last 2026-10-05T10:34:18Z)

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-postgres-db_conn_util_pct-0940-1035` (moderate): postgres db_conn_util_pct: baseline 39.83 -> window mean 30.56 (max 43.9, change -23.3%), onset 2026-10-05T10:07:00Z
- [CONFIRMED FACT] `cfg-56d39584` (moderate): Config change on payment-service: db.pool.max_size 50 -> 10 at 2026-10-05T10:04:00Z (OPS-2669)

Remaining uncertainties / missing evidence:
- [UNKNOWN] Pool checkout/return counts or connection age data
- [UNKNOWN] Leak-detection logs or thread dumps

## Critic Review
- **Verdict:** `NOT_RUN` (rounds reviewed: 0)
- **Reasoning:** 

## Probable Root Cause
MOST PROBABLE EXPLANATION (INFERENCE, not confirmed): configuration_regression in payment-service - Config change reduced db.pool.max_size from 50 to 10 at 10:04Z, starving the payment DB pool under normal load.

## Corrective Actions
- Roll back db.pool.max_size from 10 to 50 for payment-service (OPS-2669) and confirm the pool recovers
- Check that the change was intentional with the OPS-2669 owner and config-bot author
- Make sure the rollback restores error and timeout rates to baseline (~0.8% errors, ~0.1% timeouts)

## Preventive Actions
- Add validation/guardrails in CI or the config service to flag large pool-size reductions (e.g. >50%) without approval
- Require peer review for automated config-bot changes to database pool settings

## Monitoring Recommendations
- Alert on db pool utilisation >80% sustained for 2+ minutes and on pool wait-queue length
- Alert on payment-service timeout_rate >1% and error_rate >2%
- Track config change events for db.pool.* keys as annotations on dashboards

## Evidence Gaps
- none recorded

## Limitations
- No pool checkout/return or wait-time metrics were available
- Latency p99 did not show the reported increase, so the report's latency claim is not confirmed by telemetry
- No deployments were found in the window; this was checked only for payment-service, api-gateway and postgres
- The tool-call budget was not exhausted; no evidence gaps arose from failed calls
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: agent submitted

## Final Status
`PROBABLE_ROOT_CAUSE`

The most likely cause is the config change db.pool.max_size 50 -> 10 at 10:04Z (cfg-56d39584). It precedes the pool saturation (10:05), the timeouts (10:06) and the error spike, and no deployment or upstream change explains it. The Postgres side is not saturated and the connection count fell, which argues against last year's leak pattern. Status is PROBABLE rather than CONFIRMED because the intent behind the change is unverified and the latency symptom is not reproduced in p99 metrics. Rolling back the config and checking recovery would confirm it.

## Execution Statistics
```json
{
  "rounds": 1,
  "tool_calls": 8,
  "tool_failures": 0,
  "tool_retries": 0,
  "partial_results": 0,
  "agent_failures": 0,
  "agent_retries": 0,
  "invalid_llm_outputs": 0,
  "messages_exchanged": 0,
  "evidence_records": 37,
  "duration_s": 19.8,
  "tokens": {
    "input_tokens": 8,
    "output_tokens": 4605,
    "cache_read_tokens": 18814,
    "cache_write_tokens": 8242,
    "llm_calls": 3,
    "cost_usd": 0.00352169
  },
  "tokens_by_agent": {
    "single_agent": {
      "input_tokens": 8,
      "output_tokens": 4605,
      "cache_read_tokens": 18814,
      "cache_write_tokens": 8242,
      "llm_calls": 3,
      "cost_usd": 0.00352169
    }
  }
}
```
