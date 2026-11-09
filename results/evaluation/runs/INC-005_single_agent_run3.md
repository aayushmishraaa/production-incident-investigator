# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-005
- **Title:** Payments slow right after release
- **Severity:** SEV1
- **Affected services:** order-service, payment-service
- **Start time:** 2026-09-14T11:40:00+00:00
- **Investigation ID:** inv-9e5f1827a6 (single_agent)
- **Final status:** `PROBABLE_ROOT_CAUSE`

## Executive Summary
Payment and order errors began about 11:28Z. Postgres showed the earliest anomaly: disk IO wait rose from ~2ms to ~107ms (onset 11:22Z), postgres p99 rose ~53x (onset 11:23Z), and a WAL/checkpoint stall was logged at 11:24Z. Statement timeouts on charges.insert and orders.update followed, and DB connection utilisation on both postgres and payment-service climbed to 80–96%. The payment-service 5.8.0 deployment occurred at 11:32Z, after error onset at 11:28Z, and its change is logging-only. Payment-service p99 latency and timeout rate were flat versus baseline, so the release does not explain the reported latency pattern. Recommended: fail over or migrate away from the degraded volume, and verify the storage volume with the infrastructure team.

## Incident Timeline
| Time (UTC) | Label | Event | Evidence |
|---|---|---|---|
| 2026-09-14T11:11:58Z | OBSERVED EVIDENCE | First log: 7x WARN on api-gateway: 'Slow client upload from 10.4.31.12 (1.9MB)' (first 2026-09-14T11:11:58Z, last 2026-09-14T11:42:43Z) | logpat-api-gateway-88b04940 |
| 2026-09-14T11:12:04Z | OBSERVED EVIDENCE | First log: 5x WARN on payment-service: 'Card network soft decline (code 05) for charge ch_73' (first 2026-09-14T11:12:04Z, last 2026-09-14T12:04:10Z) | logpat-payment-service-7e9bf84f |
| 2026-09-14T11:12:29Z | OBSERVED EVIDENCE | First log: 6x WARN on order-service: 'Inventory reservation retry for sku-66' (first 2026-09-14T11:12:29Z, last 2026-09-14T12:01:12Z) | logpat-order-service-95abd1bb |
| 2026-09-14T11:13:45Z | OBSERVED EVIDENCE | First log: 6x WARN on notification-service: 'SMTP provider throttled 1 message' (first 2026-09-14T11:13:45Z, last 2026-09-14T12:02:54Z) | logpat-notification-service-54b86179 |
| 2026-09-14T11:17:59Z | OBSERVED EVIDENCE | First log: 6x WARN on auth-service: 'Login rate limit hit for user id u-97' (first 2026-09-14T11:17:59Z, last 2026-09-14T11:55:08Z) | logpat-auth-service-cc8d3b87 |
| 2026-09-14T11:21:06Z | OBSERVED EVIDENCE | First log: 7x WARN on postgres: 'storage: volume vol-0a3f write latency degraded (avg 835ms)' (first 2026-09-14T11:21:06Z, last 2026-09-14T11:58:54Z) | logpat-postgres-d629c24d |
| 2026-09-14T11:22:00Z | OBSERVED EVIDENCE | Anomaly onset: postgres disk_io_wait_ms: baseline 2.02 -> window mean 107.34 (max 161.01, change 5219.4%), onset 2026-09-14T11:22:00Z | met-postgres-disk_io_wait_ms-1110-1205 |
| 2026-09-14T11:23:00Z | OBSERVED EVIDENCE | Anomaly onset: postgres p99_latency_ms: baseline 25.12 -> window mean 1338.51 (max 1953.9, change 5229.4%), onset 2026-09-14T11:23:00Z | met-postgres-p99_latency_ms-1110-1205 |
| 2026-09-14T11:24:14Z | OBSERVED EVIDENCE | First log: 5x ERROR on postgres: 'checkpoint took 453.2 s; WAL write slow' (first 2026-09-14T11:24:14Z, last 2026-09-14T11:56:58Z) | logpat-postgres-7ce84fae |
| 2026-09-14T11:25:45Z | OBSERVED EVIDENCE | First log: 5x WARN on user-service: 'Deprecated API /v1/users/legacy called by client web-44' (first 2026-09-14T11:25:45Z, last 2026-09-14T11:59:25Z) | logpat-user-service-742b555e |
| 2026-09-14T11:26:00Z | OBSERVED EVIDENCE | Anomaly onset: postgres db_conn_util_pct: baseline 40.2 -> window mean 73.64 (max 96.22, change 83.2%), onset 2026-09-14T11:26:00Z | met-postgres-db_conn_util_pct-1110-1205 |
| 2026-09-14T11:28:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service error_rate: baseline 0.8 -> window mean 6.02 (max 9.65, change 655.3%), onset 2026-09-14T11:28:00Z | met-payment-service-error_rate-1110-1205 |
| 2026-09-14T11:28:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service db_conn_util_pct: baseline 34.88 -> window mean 63.61 (max 86.52, change 82.4%), onset 2026-09-14T11:28:00Z | met-payment-service-db_conn_util_pct-1110-1205 |
| 2026-09-14T11:28:01Z | OBSERVED EVIDENCE | First log: 4x WARN on postgres: 'duration: 16402 ms statement: SELECT report_rollup()' (first 2026-09-14T11:28:01Z, last 2026-09-14T11:53:40Z) | logpat-postgres-44883ca5 |
| 2026-09-14T11:28:12Z | OBSERVED EVIDENCE | First log: 9x ERROR on order-service: 'SQL query exceeded 2000ms statement timeout (orders.update) req 44' (first 2026-09-14T11:28:12Z, last 2026-09-14T12:01:12Z) | logpat-order-service-22402aae |
| 2026-09-14T11:28:17Z | OBSERVED EVIDENCE | First log: 17x ERROR on payment-service: 'SQL query exceeded 2000ms statement timeout (charges.insert) req 25' (first 2026-09-14T11:28:17Z, last 2026-09-14T12:02:55Z) | logpat-payment-service-c828e437 |
| 2026-09-14T11:32:00Z | CONFIRMED FACT | Deployment of payment-service 5.7.3->5.8.0 at 2026-09-14T11:32:00Z (SUCCEEDED): Add idempotency-key header logging | dep-31448d11 |
| 2026-09-14T11:40:00Z | CONFIRMED FACT | Reported symptom start |  |
| 2026-09-14T11:46:00Z | CONFIRMED FACT | Incident reported |  |

## Observed Symptoms
- **OBSERVED EVIDENCE:** payment-service error_rate: baseline 0.8 -> window mean 6.02 (max 9.65, change 655.3%), onset 2026-09-14T11:28:00Z (met-payment-service-error_rate-1110-1205)
- **OBSERVED EVIDENCE:** payment-service db_conn_util_pct: baseline 34.88 -> window mean 63.61 (max 86.52, change 82.4%), onset 2026-09-14T11:28:00Z (met-payment-service-db_conn_util_pct-1110-1205)
- **OBSERVED EVIDENCE:** postgres disk_io_wait_ms: baseline 2.02 -> window mean 107.34 (max 161.01, change 5219.4%), onset 2026-09-14T11:22:00Z (met-postgres-disk_io_wait_ms-1110-1205)
- **OBSERVED EVIDENCE:** postgres p99_latency_ms: baseline 25.12 -> window mean 1338.51 (max 1953.9, change 5229.4%), onset 2026-09-14T11:23:00Z (met-postgres-p99_latency_ms-1110-1205)
- **OBSERVED EVIDENCE:** postgres db_conn_util_pct: baseline 40.2 -> window mean 73.64 (max 96.22, change 83.2%), onset 2026-09-14T11:26:00Z (met-postgres-db_conn_util_pct-1110-1205)

## Investigation Performed

## Root-Cause Hypotheses (ranked by evidence strength)
### 1. H1 - `infrastructure_degradation` in `postgres` (confidence 0.75, critic: n/a)
**INFERENCE:** Degraded block storage on postgres volume vol-0a3f causing slow WAL writes and checkpoints, which led to statement timeouts in payment-service and order-service and connection-pool saturation. Mechanism: Volume write latency rises (IO wait 2ms to ~107-160ms from 11:22Z). Checkpoints stall (453-497s) and WAL writes slow, so charges.insert and orders.update exceed the 2s statement timeout. Connections are held longer, DB connection utilisation rises to ~80-96%, and the apps see errors. The ordering fits: storage warning 11:21, IO wait 11:22, p99 DB 11:23, checkpoint 11:24, app errors 11:28.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `met-postgres-disk_io_wait_ms-1110-1205` (strong): postgres disk_io_wait_ms: baseline 2.02 -> window mean 107.34 (max 161.01, change 5219.4%), onset 2026-09-14T11:22:00Z
- [OBSERVED EVIDENCE] `met-postgres-p99_latency_ms-1110-1205` (strong): postgres p99_latency_ms: baseline 25.12 -> window mean 1338.51 (max 1953.9, change 5229.4%), onset 2026-09-14T11:23:00Z
- [OBSERVED EVIDENCE] `logpat-postgres-d629c24d` (strong): 7x WARN on postgres: 'storage: volume vol-0a3f write latency degraded (avg 835ms)' (first 2026-09-14T11:21:06Z, last 2026-09-14T11:58:54Z)
- [OBSERVED EVIDENCE] `logpat-postgres-7ce84fae` (strong): 5x ERROR on postgres: 'checkpoint took 453.2 s; WAL write slow' (first 2026-09-14T11:24:14Z, last 2026-09-14T11:56:58Z)
- [OBSERVED EVIDENCE] `logpat-payment-service-c828e437` (moderate): 17x ERROR on payment-service: 'SQL query exceeded 2000ms statement timeout (charges.insert) req 25' (first 2026-09-14T11:28:17Z, last 2026-09-14T12:02:55Z)
- [OBSERVED EVIDENCE] `logpat-order-service-22402aae` (moderate): 9x ERROR on order-service: 'SQL query exceeded 2000ms statement timeout (orders.update) req 44' (first 2026-09-14T11:28:12Z, last 2026-09-14T12:01:12Z)
- [OBSERVED EVIDENCE] `met-postgres-db_conn_util_pct-1110-1205` (moderate): postgres db_conn_util_pct: baseline 40.2 -> window mean 73.64 (max 96.22, change 83.2%), onset 2026-09-14T11:26:00Z
- [INFERENCE] `hist-HIST-2025-047` (weak): Past incident HIST-2025-047 'Database storage latency degradation' (similarity 0.487): Cloud block storage volume degraded.

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-postgres-cpu_pct-1110-1205` (moderate): postgres cpu_pct: baseline 35.25 -> window mean 29.92 (max 37.58, change -15.1%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Cloud provider or host-level block-storage health for vol-0a3f
- [UNKNOWN] Postgres lock or wait-event breakdown
- [UNKNOWN] Replica lag or fail-over status

### 2. H2 - `deployment_regression` in `payment-service` (confidence 0.10, critic: n/a)
**INFERENCE:** payment-service 5.8.0 release caused the degradation (team hypothesis). Mechanism: Release changes could add per-request work or DB calls, increasing charges.insert latency.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [CONFIRMED FACT] `dep-31448d11` (weak): Deployment of payment-service 5.7.3->5.8.0 at 2026-09-14T11:32:00Z (SUCCEEDED): Add idempotency-key header logging

Contradicting evidence:
- [OBSERVED EVIDENCE] `logpat-payment-service-c828e437` (strong): 17x ERROR on payment-service: 'SQL query exceeded 2000ms statement timeout (charges.insert) req 25' (first 2026-09-14T11:28:17Z, last 2026-09-14T12:02:55Z)
- [OBSERVED EVIDENCE] `met-payment-service-error_rate-1110-1205` (strong): payment-service error_rate: baseline 0.8 -> window mean 6.02 (max 9.65, change 655.3%), onset 2026-09-14T11:28:00Z
- [OBSERVED EVIDENCE] `met-postgres-disk_io_wait_ms-1110-1205` (strong): postgres disk_io_wait_ms: baseline 2.02 -> window mean 107.34 (max 161.01, change 5219.4%), onset 2026-09-14T11:22:00Z
- [OBSERVED EVIDENCE] `met-payment-service-p99_latency_ms-1110-1205` (moderate): payment-service p99_latency_ms: baseline 300.2 -> window mean 302.29 (max 325.92, change 0.7%), onset none detected
- [OBSERVED EVIDENCE] `met-payment-service-timeout_rate-1110-1205` (moderate): payment-service timeout_rate: baseline 0.1 -> window mean 0.1 (max 0.11, change -1.4%), onset none detected
- [OBSERVED EVIDENCE] `met-order-service-p99_latency_ms-1110-1205` (moderate): order-service p99_latency_ms: baseline 400.11 -> window mean 400.71 (max 441.32, change 0.2%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Diff of 5.8.0 beyond the logging change
- [UNKNOWN] Pre-release soak metrics

### 3. H3 - `db_connection_pool_exhaustion` in `payment-service` (confidence 0.10, critic: n/a)
**INFERENCE:** Connection-pool exhaustion in payment-service or a connection leak, as in a prior incident. Mechanism: Pooled connections are held by slow or leaking queries and new requests wait for a connection.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `met-payment-service-db_conn_util_pct-1110-1205` (moderate): payment-service db_conn_util_pct: baseline 34.88 -> window mean 63.61 (max 86.52, change 82.4%), onset 2026-09-14T11:28:00Z
- [INFERENCE] `hist-HIST-2025-014` (weak): Past incident HIST-2025-014 'Payment latency from leaked DB connections' (similarity 0.317): Connection leak in refund path held pooled connections; pool exhausted.

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-payment-service-db_conn_util_pct-1110-1205` (moderate): payment-service db_conn_util_pct: baseline 34.88 -> window mean 63.61 (max 86.52, change 82.4%), onset 2026-09-14T11:28:00Z
- [OBSERVED EVIDENCE] `logpat-payment-service-c828e437` (moderate): 17x ERROR on payment-service: 'SQL query exceeded 2000ms statement timeout (charges.insert) req 25' (first 2026-09-14T11:28:17Z, last 2026-09-14T12:02:55Z)

Remaining uncertainties / missing evidence:
- [UNKNOWN] Pool wait-time and active-connection breakdown per service
- [UNKNOWN] Leak-detection logs

## Critic Review
- **Verdict:** `NOT_RUN` (rounds reviewed: 0)
- **Reasoning:** 

## Probable Root Cause
MOST PROBABLE EXPLANATION (INFERENCE, not confirmed): infrastructure_degradation in postgres - Degraded block storage on postgres volume vol-0a3f causing slow WAL writes and checkpoints, which led to statement timeouts in payment-service and order-service and connection-pool saturation.

## Corrective Actions
- Fail over postgres to a replica or migrate away from degraded volume vol-0a3f, after verifying the replica is healthy
- Engage the cloud/infra team to check block-storage health and IOPS throttling for vol-0a3f
- Do not roll back payment-service 5.8.0 on current evidence; roll back only if DB-side causes are ruled out

## Preventive Actions
- Alert on postgres disk IO wait and WAL/checkpoint duration before they reach app-level timeouts
- Review statement timeouts and retry policy for charges.insert and orders.update
- Address report_rollup() long-running queries that compete for storage I/O

## Monitoring Recommendations
- Monitor postgres disk_io_wait_ms and write latency per volume with alerting at about 20ms
- Monitor checkpoint duration and WAL write latency
- Track db_conn_util_pct on postgres and payment-service with alerting at 70%
- Track payment-service error_rate and statement-timeout pattern counts

## Evidence Gaps
- none recorded

## Limitations
- Correlation-based timing analysis; the storage cause is inferred, not directly observed
- Payment p99 latency was flat, so the user-visible 'slowness' may reflect errors and retries rather than latency
- Historical match (similarity 0.49) is only an analogy
- [agent-reported gap] No cloud/host-level storage health data for vol-0a3f
- [agent-reported gap] No pg wait-event or lock data
- [agent-reported gap] No diff of the 5.8.0 code change beyond the summary
- [agent-reported gap] No per-service connection pool breakdown
- [agent-reported gap] Telemetry for the 60 minutes before T0 is only partially used; the baseline is clean
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: agent submitted

## Final Status
`PROBABLE_ROOT_CAUSE`

The 5.8.0 release of payment-service is unlikely to be the cause. The onset of degradation precedes the deployment by several minutes and the release only added logging. The evidence points to degraded storage I/O on the postgres volume vol-0a3f (write latency and WAL/checkpoint stalls starting about 11:21–11:24Z), which caused statement timeouts and connection-pool pressure in payment-service and order-service. Final status is PROBABLE, not confirmed: the storage-level root cause is inferred from database-side telemetry and logs, and no infrastructure-level (cloud volume) evidence was collected.

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
  "evidence_records": 59,
  "duration_s": 23.56,
  "tokens": {
    "input_tokens": 8,
    "output_tokens": 5464,
    "cache_read_tokens": 20136,
    "cache_write_tokens": 9414,
    "llm_calls": 3,
    "cost_usd": 0.00411091
  },
  "tokens_by_agent": {
    "single_agent": {
      "input_tokens": 8,
      "output_tokens": 5464,
      "cache_read_tokens": 20136,
      "cache_write_tokens": 9414,
      "llm_calls": 3,
      "cost_usd": 0.00411091
    }
  }
}
```
