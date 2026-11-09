# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-012
- **Title:** Payment connection pool timeouts
- **Severity:** SEV2
- **Affected services:** payment-service
- **Start time:** 2026-10-05T10:10:00+00:00
- **Investigation ID:** inv-4ae825a336 (single_agent)
- **Final status:** `ROOT_CAUSE_IDENTIFIED`

## Executive Summary
INC-012: payment-service connection pool timeouts began at ~10:06Z, after config-bot reduced db.pool.max_size from 50 to 10 at 10:04Z (ticket OPS-2669). Pool saturation (active=10, idle=0, waiting up to 92) followed within about one minute, and error rate rose from ~0.8% to ~17% and timeouts from ~0.1% to ~11-13%. The pool-size cut is the most likely cause. A connection leak (prior-year pattern) is not supported because the saturation step coincides with the config change, not a gradual build-up.

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
- **OBSERVED EVIDENCE:** payment-service error_rate: baseline 0.8 -> window mean 9.17 (max 18.85, change 1040.5%), onset 2026-10-05T10:06:00Z (met-payment-service-error_rate-0940-1035)
- **OBSERVED EVIDENCE:** payment-service db_conn_util_pct: baseline 34.95 -> window mean 69.43 (max 100.0, change 98.7%), onset 2026-10-05T10:05:00Z (met-payment-service-db_conn_util_pct-0940-1035)
- **OBSERVED EVIDENCE:** payment-service timeout_rate: baseline 0.1 -> window mean 6.3 (max 13.3, change 6147.1%), onset 2026-10-05T10:06:00Z (met-payment-service-timeout_rate-0940-1035)

## Investigation Performed

## Root-Cause Hypotheses (ranked by evidence strength)
### 1. H1 - `configuration_regression` in `payment-service` (confidence 0.85, critic: n/a)
**INFERENCE:** Config change db.pool.max_size 50->10 on payment-service at 10:04Z caused the DB connection pool to saturate under normal load (~300 rps), producing acquisition timeouts and errors. Mechanism: Pool capped at 10 connections; with steady load, all connections are active (active=10, idle=0) and waiting requests queue until the 5000ms acquisition timeout, which then fails the request. DB connection utilisation goes 35% -> 100% (onset 10:05) and errors/timeouts step up at 10:06.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [CONFIRMED FACT] `cfg-56d39584` (strong): Config change on payment-service: db.pool.max_size 50 -> 10 at 2026-10-05T10:04:00Z (OPS-2669)
- [OBSERVED EVIDENCE] `met-payment-service-db_conn_util_pct-0940-1035` (strong): payment-service db_conn_util_pct: baseline 34.95 -> window mean 69.43 (max 100.0, change 98.7%), onset 2026-10-05T10:05:00Z
- [OBSERVED EVIDENCE] `met-payment-service-error_rate-0940-1035` (strong): payment-service error_rate: baseline 0.8 -> window mean 9.17 (max 18.85, change 1040.5%), onset 2026-10-05T10:06:00Z
- [OBSERVED EVIDENCE] `met-payment-service-timeout_rate-0940-1035` (strong): payment-service timeout_rate: baseline 0.1 -> window mean 6.3 (max 13.3, change 6147.1%), onset 2026-10-05T10:06:00Z
- [OBSERVED EVIDENCE] `logpat-payment-service-7d1739af` (strong): 29x ERROR on payment-service: 'Timeout acquiring connection from pool payment-db-pool after 5000ms (active=10, idle=0, waiting=29)' (first 2026-10-05T10:06:13Z, last 2026-10-05T10:34:18Z)
- [OBSERVED EVIDENCE] `met-payment-service-request_rate-0940-1035` (moderate): payment-service request_rate: baseline 300.21 -> window mean 299.16 (max 325.13, change -0.4%), onset none detected
- [OBSERVED EVIDENCE] `met-payment-service-cpu_pct-0940-1035` (moderate): payment-service cpu_pct: baseline 40.26 -> window mean 39.7 (max 43.26, change -1.4%), onset none detected

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-payment-service-p99_latency_ms-0940-1035` (moderate): payment-service p99_latency_ms: baseline 299.15 -> window mean 300.84 (max 325.6, change 0.6%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Direct confirmation of who/why the change was made (OPS-2669 content not retrieved)
- [UNKNOWN] Confirmation that the config is live on all payment-service pods
- [UNKNOWN] DB-side view (postgres connection counts, lock waits) not checked

### 2. H2 - `db_connection_pool_exhaustion` in `None` (confidence 0.10, critic: n/a)
**INFERENCE:** Connection leak in payment-service (same pattern as HIST-2025-014) exhausted the pool. Mechanism: Leaked pooled connections accumulate until the pool is exhausted and waiting requests time out.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [INFERENCE] `hist-HIST-2025-014` (weak): Past incident HIST-2025-014 'Payment latency from leaked DB connections' (similarity 0.419): Connection leak in refund path held pooled connections; pool exhausted.
- [OBSERVED EVIDENCE] `logpat-payment-service-7d1739af` (weak): 29x ERROR on payment-service: 'Timeout acquiring connection from pool payment-db-pool after 5000ms (active=10, idle=0, waiting=29)' (first 2026-10-05T10:06:13Z, last 2026-10-05T10:34:18Z)

Contradicting evidence:
- [CONFIRMED FACT] `cfg-56d39584` (strong): Config change on payment-service: db.pool.max_size 50 -> 10 at 2026-10-05T10:04:00Z (OPS-2669)
- [OBSERVED EVIDENCE] `met-payment-service-db_conn_util_pct-0940-1035` (moderate): payment-service db_conn_util_pct: baseline 34.95 -> window mean 69.43 (max 100.0, change 98.7%), onset 2026-10-05T10:05:00Z

Remaining uncertainties / missing evidence:
- [UNKNOWN] Pool metrics before 09:40 showing a leak trend (only 60m of telemetry is available)
- [UNKNOWN] Connection-age or refund-path traces

### 3. H3 - `upstream_dependency_degradation` in `None` (confidence 0.05, critic: n/a)
**INFERENCE:** Postgres or upstream slowness held connections longer, causing pool exhaustion. Mechanism: Slow DB queries hold connections longer, so the pool drains and waits build up.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- none

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-payment-service-p99_latency_ms-0940-1035` (moderate): payment-service p99_latency_ms: baseline 299.15 -> window mean 300.84 (max 325.6, change 0.6%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] No postgres metrics or logs were collected

## Critic Review
- **Verdict:** `NOT_RUN` (rounds reviewed: 0)
- **Reasoning:** 

## Probable Root Cause
ROOT CAUSE IDENTIFIED (critic-approved; still an INFERENCE from evidence): configuration_regression in payment-service - Config change db.pool.max_size 50->10 on payment-service at 10:04Z caused the DB connection pool to saturate under normal load (~300 rps), producing acquisition timeouts and errors.

## Corrective Actions
- Revert db.pool.max_size on payment-service from 10 to the prior value of 50 (or the validated value per OPS-2669) and verify conn util, error rate and timeouts return to baseline
- Restart or roll pods only if connections remain stuck after the revert

## Preventive Actions
- Add config validation in CI/CD or config-bot that blocks large pool-size reductions (for example >50%) without approval
- Require review for db pool changes on payment-service
- Add a pre-change load test for pool sizing

## Monitoring Recommendations
- Alert on db_conn_util_pct > 80% sustained for 2 minutes on payment-service
- Alert on pool acquisition timeout log rate and error_rate > 2%
- Track config changes to db.pool.* keys as annotated events on dashboards

## Evidence Gaps
- none recorded

## Limitations
- Telemetry only covers T0-60m to T0+30m, so long-term leak trends cannot be checked
- No postgres or auth-service metrics were gathered
- The p99 latency symptom is not reflected in metrics; the stated symptom may be a client-side view
- Config-change ticket OPS-2669 content was not retrieved
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: agent submitted

## Final Status
`ROOT_CAUSE_IDENTIFIED`

The incident is most likely caused by the config change db.pool.max_size 50 -> 10 at 10:04Z on payment-service (cfg-56d39584). The change precedes the utilisation rise (10:05), the error and timeout rise (10:06), and the pool-timeout logs, which show active=10 idle=0 consistent with the new cap. Request rate and CPU were flat, which rules out traffic surge and compute saturation. The connection-leak analogy from last year is not supported by the step-change timing. Revert the setting to restore service. Remaining gaps: intent of OPS-2669, whether the value is live on all pods, and DB-side data.

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
  "evidence_records": 33,
  "duration_s": 20.22,
  "tokens": {
    "input_tokens": 8,
    "output_tokens": 4403,
    "cache_read_tokens": 14599,
    "cache_write_tokens": 11400,
    "llm_calls": 3,
    "cost_usd": 0.0037732900000000003
  },
  "tokens_by_agent": {
    "single_agent": {
      "input_tokens": 8,
      "output_tokens": 4403,
      "cache_read_tokens": 14599,
      "cache_write_tokens": 11400,
      "llm_calls": 3,
      "cost_usd": 0.0037732900000000003
    }
  }
}
```
