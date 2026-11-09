# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-005
- **Title:** Payments slow right after release
- **Severity:** SEV1
- **Affected services:** order-service, payment-service
- **Start time:** 2026-09-14T11:40:00+00:00
- **Investigation ID:** inv-4c6cd9a2c3 (single_agent)
- **Final status:** `PROBABLE_ROOT_CAUSE`

## Executive Summary
The payment-service 5.8.0 release (11:32Z) is unlikely to be the cause. Errors and DB connection pressure in payment-service began at 11:28Z, and the earliest anomaly is in postgres (p99 latency onset 11:23Z, after storage write-latency warnings on volume vol-0a3f from 11:21Z). The most likely cause is degraded storage on the Postgres volume vol-0a3f, slowing writes and checkpoints, which pushed charges.insert past its 2000ms statement timeout and held payment DB connections. Long-running report_rollup() queries are a likely contributor. Order-service latency and error rate were flat, so the reported order-service degradation is not supported by telemetry.

## Incident Timeline
| Time (UTC) | Label | Event | Evidence |
|---|---|---|---|
| 2026-09-14T11:21:06Z | OBSERVED EVIDENCE | First log: 4x WARN on postgres: 'storage: volume vol-0a3f write latency degraded (avg 835ms)' (first 2026-09-14T11:21:06Z, last 2026-09-14T11:39:56Z) | logpat-postgres-d629c24d |
| 2026-09-14T11:23:00Z | OBSERVED EVIDENCE | Anomaly onset: postgres p99_latency_ms: baseline 25.12 -> window mean 1338.51 (max 1953.9, change 5229.4%), onset 2026-09-14T11:23:00Z | met-postgres-p99_latency_ms-1110-1205 |
| 2026-09-14T11:26:00Z | OBSERVED EVIDENCE | Anomaly onset: postgres db_conn_util_pct: baseline 40.2 -> window mean 73.64 (max 96.22, change 83.2%), onset 2026-09-14T11:26:00Z | met-postgres-db_conn_util_pct-1110-1205 |
| 2026-09-14T11:28:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service error_rate: baseline 0.8 -> window mean 6.02 (max 9.65, change 655.3%), onset 2026-09-14T11:28:00Z | met-payment-service-error_rate-1110-1205 |
| 2026-09-14T11:28:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service db_conn_util_pct: baseline 34.88 -> window mean 63.61 (max 86.52, change 82.4%), onset 2026-09-14T11:28:00Z | met-payment-service-db_conn_util_pct-1110-1205 |
| 2026-09-14T11:28:01Z | OBSERVED EVIDENCE | First log: 3x WARN on postgres: 'duration: 16402 ms statement: SELECT report_rollup()' (first 2026-09-14T11:28:01Z, last 2026-09-14T11:39:27Z) | logpat-postgres-44883ca5 |
| 2026-09-14T11:28:17Z | OBSERVED EVIDENCE | First log: 6x ERROR on payment-service: 'SQL query exceeded 2000ms statement timeout (charges.insert) req 25' (first 2026-09-14T11:28:17Z, last 2026-09-14T11:39:03Z) | logpat-payment-service-c828e437 |
| 2026-09-14T11:32:00Z | CONFIRMED FACT | Deployment of payment-service 5.7.3->5.8.0 at 2026-09-14T11:32:00Z (SUCCEEDED): Add idempotency-key header logging | dep-31448d11 |
| 2026-09-14T11:40:00Z | CONFIRMED FACT | Reported symptom start |  |
| 2026-09-14T11:46:00Z | CONFIRMED FACT | Incident reported |  |

## Observed Symptoms
- **OBSERVED EVIDENCE:** payment-service error_rate: baseline 0.8 -> window mean 6.02 (max 9.65, change 655.3%), onset 2026-09-14T11:28:00Z (met-payment-service-error_rate-1110-1205)
- **OBSERVED EVIDENCE:** payment-service db_conn_util_pct: baseline 34.88 -> window mean 63.61 (max 86.52, change 82.4%), onset 2026-09-14T11:28:00Z (met-payment-service-db_conn_util_pct-1110-1205)
- **OBSERVED EVIDENCE:** postgres db_conn_util_pct: baseline 40.2 -> window mean 73.64 (max 96.22, change 83.2%), onset 2026-09-14T11:26:00Z (met-postgres-db_conn_util_pct-1110-1205)
- **OBSERVED EVIDENCE:** postgres p99_latency_ms: baseline 25.12 -> window mean 1338.51 (max 1953.9, change 5229.4%), onset 2026-09-14T11:23:00Z (met-postgres-p99_latency_ms-1110-1205)

## Investigation Performed

## Root-Cause Hypotheses (ranked by evidence strength)
### 1. H1 - `infrastructure_degradation` in `postgres` (confidence 0.70, critic: n/a)
**INFERENCE:** Degraded block storage volume vol-0a3f on the Postgres host slowed WAL/checkpoint writes, causing charges.insert statement timeouts in payment-service and DB connection saturation. Mechanism: Storage write latency rose (835ms avg at 11:21Z) -> WAL writes and checkpoints slow (checkpoint took 453s) -> Postgres p99 latency rises from 11:23Z -> payment charges.insert exceeds 2000ms statement_timeout (from 11:28Z) -> payment DB connection utilisation climbs to ~80% -> payment errors rise to ~9%.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-postgres-d629c24d` (strong): 4x WARN on postgres: 'storage: volume vol-0a3f write latency degraded (avg 835ms)' (first 2026-09-14T11:21:06Z, last 2026-09-14T11:39:56Z)
- [OBSERVED EVIDENCE] `logpat-postgres-7ce84fae` (strong): 2x ERROR on postgres: 'checkpoint took 453.2 s; WAL write slow' (first 2026-09-14T11:24:14Z, last 2026-09-14T11:32:14Z)
- [OBSERVED EVIDENCE] `met-postgres-p99_latency_ms-1110-1205` (strong): postgres p99_latency_ms: baseline 25.12 -> window mean 1338.51 (max 1953.9, change 5229.4%), onset 2026-09-14T11:23:00Z
- [OBSERVED EVIDENCE] `met-postgres-db_conn_util_pct-1110-1205` (moderate): postgres db_conn_util_pct: baseline 40.2 -> window mean 73.64 (max 96.22, change 83.2%), onset 2026-09-14T11:26:00Z
- [OBSERVED EVIDENCE] `logpat-payment-service-c828e437` (strong): 6x ERROR on payment-service: 'SQL query exceeded 2000ms statement timeout (charges.insert) req 25' (first 2026-09-14T11:28:17Z, last 2026-09-14T11:39:03Z)
- [OBSERVED EVIDENCE] `met-payment-service-error_rate-1110-1205` (strong): payment-service error_rate: baseline 0.8 -> window mean 6.02 (max 9.65, change 655.3%), onset 2026-09-14T11:28:00Z
- [OBSERVED EVIDENCE] `met-payment-service-db_conn_util_pct-1110-1205` (moderate): payment-service db_conn_util_pct: baseline 34.88 -> window mean 63.61 (max 86.52, change 82.4%), onset 2026-09-14T11:28:00Z
- [INFERENCE] `hist-HIST-2025-047` (weak): Past incident HIST-2025-047 'Database storage latency degradation' (similarity 0.433): Cloud block storage volume degraded.

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-payment-service-p99_latency_ms-1110-1205` (moderate): payment-service p99_latency_ms: baseline 300.2 -> window mean 302.29 (max 325.92, change 0.7%), onset none detected
- [OBSERVED EVIDENCE] `met-order-service-p99_latency_ms-1110-1205` (moderate): order-service p99_latency_ms: baseline 400.11 -> window mean 400.71 (max 441.32, change 0.2%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Host-level disk/IO metrics for the Postgres volume
- [UNKNOWN] Cloud provider health events for vol-0a3f
- [UNKNOWN] pg_stat_activity / lock data showing the blocking query

### 2. H3 - `resource_saturation` in `postgres` (confidence 0.25, critic: n/a)
**INFERENCE:** Long-running report_rollup() queries saturated the database, contending with charges.insert and driving connection use up. Mechanism: report_rollup() runs 15-16s per execution from 11:28Z, holding resources and I/O, which slows writes and fills the connection pool.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-postgres-44883ca5` (moderate): 3x WARN on postgres: 'duration: 16402 ms statement: SELECT report_rollup()' (first 2026-09-14T11:28:01Z, last 2026-09-14T11:39:27Z)
- [OBSERVED EVIDENCE] `met-postgres-db_conn_util_pct-1110-1205` (weak): postgres db_conn_util_pct: baseline 40.2 -> window mean 73.64 (max 96.22, change 83.2%), onset 2026-09-14T11:26:00Z

Contradicting evidence:
- [OBSERVED EVIDENCE] `logpat-postgres-d629c24d` (moderate): 4x WARN on postgres: 'storage: volume vol-0a3f write latency degraded (avg 835ms)' (first 2026-09-14T11:21:06Z, last 2026-09-14T11:39:56Z)

Remaining uncertainties / missing evidence:
- [UNKNOWN] Scheduler or job record showing who triggered report_rollup and when

### 3. H2 - `deployment_regression` in `payment-service` (confidence 0.10, critic: n/a)
**INFERENCE:** The payment-service 5.8.0 release (idempotency-key header logging) caused the degradation. Mechanism: New logging on the request path adds DB writes or latency, slowing charges.insert.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [CONFIRMED FACT] `dep-31448d11` (weak): Deployment of payment-service 5.7.3->5.8.0 at 2026-09-14T11:32:00Z (SUCCEEDED): Add idempotency-key header logging

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-payment-service-error_rate-1110-1205` (strong): payment-service error_rate: baseline 0.8 -> window mean 6.02 (max 9.65, change 655.3%), onset 2026-09-14T11:28:00Z
- [OBSERVED EVIDENCE] `met-postgres-p99_latency_ms-1110-1205` (strong): postgres p99_latency_ms: baseline 25.12 -> window mean 1338.51 (max 1953.9, change 5229.4%), onset 2026-09-14T11:23:00Z
- [OBSERVED EVIDENCE] `logpat-postgres-d629c24d` (strong): 4x WARN on postgres: 'storage: volume vol-0a3f write latency degraded (avg 835ms)' (first 2026-09-14T11:21:06Z, last 2026-09-14T11:39:56Z)
- [OBSERVED EVIDENCE] `met-payment-service-p99_latency_ms-1110-1205` (moderate): payment-service p99_latency_ms: baseline 300.2 -> window mean 302.29 (max 325.92, change 0.7%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Diff of 5.8.0 beyond the logging change
- [UNKNOWN] Logs from 5.8.0 pods showing added DB calls

## Critic Review
- **Verdict:** `NOT_RUN` (rounds reviewed: 0)
- **Reasoning:** 

## Probable Root Cause
MOST PROBABLE EXPLANATION (INFERENCE, not confirmed): infrastructure_degradation in postgres - Degraded block storage volume vol-0a3f on the Postgres host slowed WAL/checkpoint writes, causing charges.insert statement timeouts in payment-service and DB connection saturation.

## Corrective Actions
- Mitigate the storage issue: fail over Postgres to a replica or migrate off vol-0a3f, and confirm with the cloud provider.
- Pause or reschedule report_rollup() during incident recovery.
- Do not roll back 5.8.0 on current evidence; revisit only if per-version error data shows it contributes.

## Preventive Actions
- Alert on Postgres storage write latency and checkpoint duration.
- Isolate reporting queries onto a replica or a separate resource pool.
- Add per-version error breakdowns to release monitoring so deploy attribution is unambiguous.

## Monitoring Recommendations
- Track vol-0a3f write latency and disk IO wait with a threshold alert.
- Monitor Postgres checkpoint duration and WAL write time.
- Alert on charges.insert statement timeout counts in payment-service.
- Collect disk_io_wait_ms for postgres and payment-service.

## Evidence Gaps
- none recorded

## Limitations
- Timing-based correlation analysis; no direct causal test.
- Telemetry limited to the window provided.
- [agent-reported gap] No disk_io_wait_ms for postgres; no IOPS or cloud health data for vol-0a3f.
- [agent-reported gap] No pg_stat_activity or lock data.
- [agent-reported gap] Payment p99 latency flat despite DB timeouts; not explained.
- [agent-reported gap] Order-service degradation reported by the team is not visible in its metrics.
- [agent-reported gap] No scheduler record for report_rollup().
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: agent submitted

## Final Status
`PROBABLE_ROOT_CAUSE`

The release 5.8.0 is not supported as the cause. The earliest anomaly is Postgres storage and write degradation (volume vol-0a3f, from 11:21Z), which precedes the payment errors (11:28Z) and the deploy (11:32Z). That degradation most likely caused charges.insert statement timeouts and connection saturation in payment-service. The report_rollup() workload is a plausible contributor. Confidence is moderate because host-level IO data for Postgres was not collected and the flat payment p99 is unexplained.

## Execution Statistics
```json
{
  "rounds": 1,
  "tool_calls": 12,
  "tool_failures": 0,
  "tool_retries": 0,
  "partial_results": 0,
  "agent_failures": 0,
  "agent_retries": 0,
  "invalid_llm_outputs": 1,
  "messages_exchanged": 0,
  "evidence_records": 50,
  "duration_s": 36.75,
  "tokens": {
    "input_tokens": 14,
    "output_tokens": 9459,
    "cache_read_tokens": 59672,
    "cache_write_tokens": 15202,
    "llm_calls": 6,
    "cost_usd": 0.00722787
  },
  "tokens_by_agent": {
    "single_agent": {
      "input_tokens": 14,
      "output_tokens": 9459,
      "cache_read_tokens": 59672,
      "cache_write_tokens": 15202,
      "llm_calls": 6,
      "cost_usd": 0.00722787
    }
  }
}
```
