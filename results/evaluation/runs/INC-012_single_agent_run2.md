# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-012
- **Title:** Payment connection pool timeouts
- **Severity:** SEV2
- **Affected services:** payment-service
- **Start time:** 2026-10-05T10:10:00+00:00
- **Investigation ID:** inv-2a71a51160 (single_agent)
- **Final status:** `PROBABLE_ROOT_CAUSE`

## Executive Summary
payment-service's DB connection pool (payment-db-pool) was cut from max_size 50 to 10 by a config change at 10:04Z (cfg-56d39584, author config-bot, ticket OPS-2669). Pool utilisation rose to 100% and requests began timing out acquiring connections from 10:06Z, producing a ~17% error rate and ~12% timeout rate. Postgres connection use fell at the same time, consistent with fewer pooled connections rather than database distress. This is a self-inflicted configuration regression, not a connection leak like last year's incident.

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
### 1. H1 - `configuration_regression` in `payment-service` (confidence 0.85, critic: n/a)
**INFERENCE:** Config change reducing db.pool.max_size from 50 to 10 at 10:04Z exhausted the payment-db-pool, causing connection acquisition timeouts. Mechanism: Pool capacity dropped 80%. Under steady ~300 rps, demand exceeds 10 connections, so waiters queue (waiting=15-92) and hit the 5000ms acquisition timeout, yielding errors and timeouts. Onset of pool saturation (10:05-10:06) follows the config change (10:04) and precedes the error onset (10:06).

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [CONFIRMED FACT] `cfg-56d39584` (strong): Config change on payment-service: db.pool.max_size 50 -> 10 at 2026-10-05T10:04:00Z (OPS-2669)
- [OBSERVED EVIDENCE] `met-payment-service-db_conn_util_pct-0940-1035` (strong): payment-service db_conn_util_pct: baseline 34.95 -> window mean 69.43 (max 100.0, change 98.7%), onset 2026-10-05T10:05:00Z
- [OBSERVED EVIDENCE] `met-payment-service-error_rate-0940-1035` (strong): payment-service error_rate: baseline 0.8 -> window mean 9.17 (max 18.85, change 1040.5%), onset 2026-10-05T10:06:00Z
- [OBSERVED EVIDENCE] `met-payment-service-timeout_rate-0940-1035` (strong): payment-service timeout_rate: baseline 0.1 -> window mean 6.3 (max 13.3, change 6147.1%), onset 2026-10-05T10:06:00Z
- [OBSERVED EVIDENCE] `logpat-payment-service-7d1739af` (strong): 29x ERROR on payment-service: 'Timeout acquiring connection from pool payment-db-pool after 5000ms (active=10, idle=0, waiting=29)' (first 2026-10-05T10:06:13Z, last 2026-10-05T10:34:18Z)
- [OBSERVED EVIDENCE] `met-postgres-db_conn_util_pct-0940-1035` (moderate): postgres db_conn_util_pct: baseline 39.83 -> window mean 30.56 (max 43.9, change -23.3%), onset 2026-10-05T10:07:00Z
- [OBSERVED EVIDENCE] `met-postgres-cpu_pct-0940-1035` (moderate): postgres cpu_pct: baseline 35.02 -> window mean 35.11 (max 37.77, change 0.3%), onset none detected

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-payment-service-p99_latency_ms-0940-1035` (moderate): payment-service p99_latency_ms: baseline 299.15 -> window mean 300.84 (max 325.6, change 0.6%), onset none detected
- [OBSERVED EVIDENCE] `met-payment-service-request_rate-0940-1035` (weak): payment-service request_rate: baseline 300.21 -> window mean 299.16 (max 325.13, change -0.4%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Per-request latency for failed calls, and the p50 series, were not checked.
- [UNKNOWN] No direct evidence of the pool-config reload on running pods (was the new value applied?).

### 2. H2 - `db_connection_pool_exhaustion` in `payment-service` (confidence 0.10, critic: n/a)
**INFERENCE:** Connection leak in payment-service (as in HIST-2025-014) holding pooled connections until exhaustion. Mechanism: A leaked connection path would steadily reduce idle connections and show a gradual ramp rather than a step change aligned with a config edit.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [INFERENCE] `hist-HIST-2025-014` (weak): Past incident HIST-2025-014 'Payment latency from leaked DB connections' (similarity 0.4): Connection leak in refund path held pooled connections; pool exhausted.
- [OBSERVED EVIDENCE] `logpat-payment-service-7d1739af` (moderate): 29x ERROR on payment-service: 'Timeout acquiring connection from pool payment-db-pool after 5000ms (active=10, idle=0, waiting=29)' (first 2026-10-05T10:06:13Z, last 2026-10-05T10:34:18Z)

Contradicting evidence:
- [CONFIRMED FACT] `cfg-56d39584` (strong): Config change on payment-service: db.pool.max_size 50 -> 10 at 2026-10-05T10:04:00Z (OPS-2669)
- [OBSERVED EVIDENCE] `met-postgres-db_conn_util_pct-0940-1035` (moderate): postgres db_conn_util_pct: baseline 39.83 -> window mean 30.56 (max 43.9, change -23.3%), onset 2026-10-05T10:07:00Z

Remaining uncertainties / missing evidence:
- [UNKNOWN] Pool active-count trend before 10:04 at the 50-connection cap.

### 3. H3 - `upstream_dependency_degradation` in `postgres` (confidence 0.05, critic: n/a)
**INFERENCE:** Postgres or an upstream (auth-service) degradation slowed connection checkouts. Mechanism: Slow DB responses would hold connections longer and exhaust the pool.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- none

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-postgres-p95_latency_ms-0940-1035` (strong): postgres p95_latency_ms: baseline 12.07 -> window mean 11.96 (max 12.88, change -0.9%), onset none detected
- [OBSERVED EVIDENCE] `met-postgres-cpu_pct-0940-1035` (moderate): postgres cpu_pct: baseline 35.02 -> window mean 35.11 (max 37.77, change 0.3%), onset none detected
- [CONFIRMED FACT] `topo-payment-service-both-d2` (weak): payment-service depends on ['auth-service', 'postgres', 'redis']; called by ['api-gateway', 'order-service'] (graph topology-v2)

Remaining uncertainties / missing evidence:
- [UNKNOWN] auth-service metrics were not queried.

## Critic Review
- **Verdict:** `NOT_RUN` (rounds reviewed: 0)
- **Reasoning:** 

## Probable Root Cause
MOST PROBABLE EXPLANATION (INFERENCE, not confirmed): configuration_regression in payment-service - Config change reducing db.pool.max_size from 50 to 10 at 10:04Z exhausted the payment-db-pool, causing connection acquisition timeouts.

## Corrective Actions
- Revert db.pool.max_size from 10 to 50 on payment-service (OPS-2669) and confirm pods reload the value.
- Confirm pool waiters drain and error/timeout rates return to baseline (~0.8% / ~0.1%).

## Preventive Actions
- Add validation in CI/config pipeline rejecting pool sizes that drop more than a set fraction without approval.
- Require review for config-bot changes to database pool settings.

## Monitoring Recommendations
- Alert on payment-db-pool utilisation above 80% and on any pool-acquisition timeout log.
- Track db.pool.max_size as a config-drift metric.

## Evidence Gaps
- none recorded

## Limitations
- Live pod configuration was not verified against the config-change record.
- Latency symptom is not reflected in p99 metrics; per-request failure latency was not examined.
- auth-service and redis metrics were not queried.
- [agent-reported gap] No pod-level pool size confirmation.
- [agent-reported gap] No auth-service or redis telemetry.
- [agent-reported gap] No p50 or failed-request latency data.
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: agent submitted

## Final Status
`PROBABLE_ROOT_CAUSE`

The incident is most likely a configuration regression: db.pool.max_size was cut from 50 to 10 at 10:04Z, which saturated the payment DB pool and caused acquisition timeouts from 10:06Z. The timing, the pool-exhaustion log signature, and the healthy Postgres side all support this. It is not confirmed because I did not verify the live pod config, and the flat p99 latency does not match the reported latency symptom. Last year's leak pattern is only an analogy and is not supported by the data.

## Execution Statistics
```json
{
  "rounds": 1,
  "tool_calls": 7,
  "tool_failures": 0,
  "tool_retries": 0,
  "partial_results": 0,
  "agent_failures": 0,
  "agent_retries": 0,
  "invalid_llm_outputs": 0,
  "messages_exchanged": 0,
  "evidence_records": 35,
  "duration_s": 17.51,
  "tokens": {
    "input_tokens": 8,
    "output_tokens": 4105,
    "cache_read_tokens": 18812,
    "cache_write_tokens": 7440,
    "llm_calls": 3,
    "cost_usd": 0.00317142
  },
  "tokens_by_agent": {
    "single_agent": {
      "input_tokens": 8,
      "output_tokens": 4105,
      "cache_read_tokens": 18812,
      "cache_write_tokens": 7440,
      "llm_calls": 3,
      "cost_usd": 0.00317142
    }
  }
}
```
