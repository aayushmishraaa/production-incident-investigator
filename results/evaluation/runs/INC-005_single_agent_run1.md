# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-005
- **Title:** Payments slow right after release
- **Severity:** SEV1
- **Affected services:** order-service, payment-service
- **Start time:** 2026-09-14T11:40:00+00:00
- **Investigation ID:** inv-6a5bca0722 (single_agent)
- **Final status:** `PROBABLE_ROOT_CAUSE`

## Executive Summary
The payment-service 5.8.0 release (11:32Z) did not start the incident. Degradation begins at ~11:21-11:23Z on the postgres host: storage volume vol-0a3f write latency rises (log 11:21:06Z), disk IO wait jumps from ~2ms to ~130ms (onset 11:22Z), and postgres p95 latency jumps from ~12ms to ~690ms (onset 11:23Z). Payment p95 latency rises at 11:27Z and errors/statement timeouts start 11:28Z, all before the 11:32Z deployment. The most likely cause is degraded database storage (infrastructure), with payment and order symptoms being downstream effects. Confidence is moderate because the storage root cause is inferred from correlated telemetry and logs, not confirmed by a storage-provider signal.

## Incident Timeline
| Time (UTC) | Label | Event | Evidence |
|---|---|---|---|
| 2026-09-14T11:21:06Z | OBSERVED EVIDENCE | First log: 3x WARN on postgres: 'storage: volume vol-0a3f write latency degraded (avg 835ms)' (first 2026-09-14T11:21:06Z, last 2026-09-14T11:33:51Z) | logpat-postgres-d629c24d |
| 2026-09-14T11:22:00Z | OBSERVED EVIDENCE | Anomaly onset: postgres disk_io_wait_ms: baseline 2.02 -> window mean 107.34 (max 161.01, change 5219.4%), onset 2026-09-14T11:22:00Z | met-postgres-disk_io_wait_ms-1110-1205 |
| 2026-09-14T11:23:00Z | OBSERVED EVIDENCE | Anomaly onset: postgres p95_latency_ms: baseline 12.01 -> window mean 667.73 (max 960.48, change 5461.9%), onset 2026-09-14T11:23:00Z | met-postgres-p95_latency_ms-1110-1205 |
| 2026-09-14T11:26:00Z | OBSERVED EVIDENCE | Anomaly onset: postgres db_conn_util_pct: baseline 40.2 -> window mean 73.64 (max 96.22, change 83.2%), onset 2026-09-14T11:26:00Z | met-postgres-db_conn_util_pct-1110-1205 |
| 2026-09-14T11:27:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service p95_latency_ms: baseline 150.16 -> window mean 1585.88 (max 2489.32, change 956.1%), onset 2026-09-14T11:27:00Z | met-payment-service-p95_latency_ms-1110-1205 |
| 2026-09-14T11:28:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service error_rate: baseline 0.8 -> window mean 6.02 (max 9.65, change 655.3%), onset 2026-09-14T11:28:00Z | met-payment-service-error_rate-1110-1205 |
| 2026-09-14T11:28:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service db_conn_util_pct: baseline 34.88 -> window mean 63.61 (max 86.52, change 82.4%), onset 2026-09-14T11:28:00Z | met-payment-service-db_conn_util_pct-1110-1205 |
| 2026-09-14T11:28:17Z | OBSERVED EVIDENCE | First log: 6x ERROR on payment-service: 'SQL query exceeded 2000ms statement timeout (charges.insert) req 25' (first 2026-09-14T11:28:17Z, last 2026-09-14T11:39:03Z) | logpat-payment-service-c828e437 |
| 2026-09-14T11:32:00Z | CONFIRMED FACT | Deployment of payment-service 5.7.3->5.8.0 at 2026-09-14T11:32:00Z (SUCCEEDED): Add idempotency-key header logging | dep-31448d11 |
| 2026-09-14T11:40:00Z | CONFIRMED FACT | Reported symptom start |  |
| 2026-09-14T11:46:00Z | CONFIRMED FACT | Incident reported |  |

## Observed Symptoms
- **OBSERVED EVIDENCE:** payment-service error_rate: baseline 0.8 -> window mean 6.02 (max 9.65, change 655.3%), onset 2026-09-14T11:28:00Z (met-payment-service-error_rate-1110-1205)
- **OBSERVED EVIDENCE:** payment-service db_conn_util_pct: baseline 34.88 -> window mean 63.61 (max 86.52, change 82.4%), onset 2026-09-14T11:28:00Z (met-payment-service-db_conn_util_pct-1110-1205)
- **OBSERVED EVIDENCE:** postgres db_conn_util_pct: baseline 40.2 -> window mean 73.64 (max 96.22, change 83.2%), onset 2026-09-14T11:26:00Z (met-postgres-db_conn_util_pct-1110-1205)
- **OBSERVED EVIDENCE:** postgres p95_latency_ms: baseline 12.01 -> window mean 667.73 (max 960.48, change 5461.9%), onset 2026-09-14T11:23:00Z (met-postgres-p95_latency_ms-1110-1205)
- **OBSERVED EVIDENCE:** postgres disk_io_wait_ms: baseline 2.02 -> window mean 107.34 (max 161.01, change 5219.4%), onset 2026-09-14T11:22:00Z (met-postgres-disk_io_wait_ms-1110-1205)
- **OBSERVED EVIDENCE:** payment-service p95_latency_ms: baseline 150.16 -> window mean 1585.88 (max 2489.32, change 956.1%), onset 2026-09-14T11:27:00Z (met-payment-service-p95_latency_ms-1110-1205)

## Investigation Performed

## Root-Cause Hypotheses (ranked by evidence strength)
### 1. H1 - `infrastructure_degradation` in `postgres` (confidence 0.70, critic: n/a)
**INFERENCE:** Degraded block storage volume vol-0a3f on the postgres host slowed writes/WAL, causing charges.insert statement timeouts and payment latency/error spikes. Mechanism: Volume write latency degrades (11:21Z) -> disk IO wait up ~65x (11:22Z) and checkpoint/WAL stalls (checkpoint took 453s, 11:24Z) -> postgres p95 latency up ~55x (11:23Z) and DB connection utilisation climbs to ~80-96% (11:26Z) as connections are held longer -> payment-service p95 rises (11:27Z), charges.insert exceeds 2000ms statement timeout and errors rise (11:28Z).

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `log-77fdc9ea` (strong): WARN postgres: storage: volume vol-0a3f write latency degraded (avg 835ms)
- [OBSERVED EVIDENCE] `met-postgres-disk_io_wait_ms-1110-1205` (strong): postgres disk_io_wait_ms: baseline 2.02 -> window mean 107.34 (max 161.01, change 5219.4%), onset 2026-09-14T11:22:00Z
- [OBSERVED EVIDENCE] `met-postgres-p95_latency_ms-1110-1205` (strong): postgres p95_latency_ms: baseline 12.01 -> window mean 667.73 (max 960.48, change 5461.9%), onset 2026-09-14T11:23:00Z
- [OBSERVED EVIDENCE] `logpat-postgres-7ce84fae` (strong): 2x ERROR on postgres: 'checkpoint took 453.2 s; WAL write slow' (first 2026-09-14T11:24:14Z, last 2026-09-14T11:32:14Z)
- [OBSERVED EVIDENCE] `met-postgres-db_conn_util_pct-1110-1205` (moderate): postgres db_conn_util_pct: baseline 40.2 -> window mean 73.64 (max 96.22, change 83.2%), onset 2026-09-14T11:26:00Z
- [OBSERVED EVIDENCE] `logpat-payment-service-c828e437` (strong): 6x ERROR on payment-service: 'SQL query exceeded 2000ms statement timeout (charges.insert) req 25' (first 2026-09-14T11:28:17Z, last 2026-09-14T11:39:03Z)
- [OBSERVED EVIDENCE] `met-payment-service-p95_latency_ms-1110-1205` (strong): payment-service p95_latency_ms: baseline 150.16 -> window mean 1585.88 (max 2489.32, change 956.1%), onset 2026-09-14T11:27:00Z
- [OBSERVED EVIDENCE] `met-payment-service-error_rate-1110-1205` (strong): payment-service error_rate: baseline 0.8 -> window mean 6.02 (max 9.65, change 655.3%), onset 2026-09-14T11:28:00Z
- [INFERENCE] `hist-HIST-2025-047` (weak): Past incident HIST-2025-047 'Database storage latency degradation' (similarity 0.384): Cloud block storage volume degraded.

Contradicting evidence:
- [OBSERVED EVIDENCE] `logpat-postgres-44883ca5` (weak): 1x WARN on postgres: 'duration: 16402 ms statement: SELECT report_rollup()' (first 2026-09-14T11:28:01Z, last 2026-09-14T11:28:01Z)
- [OBSERVED EVIDENCE] `met-postgres-cpu_pct-1110-1205` (weak): postgres cpu_pct: baseline 35.25 -> window mean 29.92 (max 37.58, change -15.1%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Cloud provider/volume-level health or event data for vol-0a3f
- [UNKNOWN] Postgres lock/wait-event data and pg_stat_activity during 11:20-11:30Z

### 2. H2 - `deployment_regression` in `payment-service` (confidence 0.10, critic: n/a)
**INFERENCE:** payment-service 5.8.0 (idempotency-key header logging) caused the latency/error regression. Mechanism: New logging in the release adds overhead or DB writes on the charges.insert path, slowing requests.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [CONFIRMED FACT] `dep-31448d11` (weak): Deployment of payment-service 5.7.3->5.8.0 at 2026-09-14T11:32:00Z (SUCCEEDED): Add idempotency-key header logging

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-payment-service-error_rate-1110-1205` (strong): payment-service error_rate: baseline 0.8 -> window mean 6.02 (max 9.65, change 655.3%), onset 2026-09-14T11:28:00Z
- [OBSERVED EVIDENCE] `met-payment-service-p95_latency_ms-1110-1205` (strong): payment-service p95_latency_ms: baseline 150.16 -> window mean 1585.88 (max 2489.32, change 956.1%), onset 2026-09-14T11:27:00Z
- [OBSERVED EVIDENCE] `logpat-postgres-d629c24d` (strong): 3x WARN on postgres: 'storage: volume vol-0a3f write latency degraded (avg 835ms)' (first 2026-09-14T11:21:06Z, last 2026-09-14T11:33:51Z)
- [OBSERVED EVIDENCE] `met-payment-service-cpu_pct-1110-1205` (moderate): payment-service cpu_pct: baseline 39.75 -> window mean 40.08 (max 45.14, change 0.8%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Diff of 5.8.0 code beyond the change summary

### 3. H3 - `db_connection_pool_exhaustion` in `payment-service` (confidence 0.05, critic: n/a)
**INFERENCE:** Connection leak or pool exhaustion in payment-service. Mechanism: Leaked connections would saturate the pool and cause timeouts, but the data shows postgres-side saturation starting after storage latency.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `met-payment-service-db_conn_util_pct-1110-1205` (weak): payment-service db_conn_util_pct: baseline 34.88 -> window mean 63.61 (max 86.52, change 82.4%), onset 2026-09-14T11:28:00Z
- [INFERENCE] `hist-HIST-2025-014` (weak): Past incident HIST-2025-014 'Payment latency from leaked DB connections' (similarity 0.427): Connection leak in refund path held pooled connections; pool exhausted.

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-payment-service-timeout_rate-1110-1205` (moderate): payment-service timeout_rate: baseline 0.1 -> window mean 0.1 (max 0.11, change -1.4%), onset none detected
- [OBSERVED EVIDENCE] `met-payment-service-request_rate-1110-1205` (weak): payment-service request_rate: baseline 303.91 -> window mean 299.38 (max 319.5, change -1.5%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Pool-level metrics (active/idle/waiting per pool) from payment-service

## Critic Review
- **Verdict:** `NOT_RUN` (rounds reviewed: 0)
- **Reasoning:** 

## Probable Root Cause
MOST PROBABLE EXPLANATION (INFERENCE, not confirmed): infrastructure_degradation in postgres - Degraded block storage volume vol-0a3f on the postgres host slowed writes/WAL, causing charges.insert statement timeouts and payment latency/error spikes.

## Corrective Actions
- Check volume vol-0a3f health with the cloud/storage provider; if degraded, fail over postgres to a replica or migrate the volume
- Reduce DB load while storage is degraded: pause or reschedule report_rollup() and heavy autovacuum
- Reassess the 5.8.0 rollback only if errors persist after storage recovers

## Preventive Actions
- Alert on postgres disk IO wait and volume write latency so storage degradation is caught before payment timeouts
- Set guardrails on long-running reporting queries against the primary

## Monitoring Recommendations
- postgres disk_io_wait_ms and write latency for vol-0a3f
- postgres checkpoint duration and WAL write time
- payment-service charges.insert statement timeout count and p95 latency
- payment db_conn_util_pct

## Evidence Gaps
- none recorded

## Limitations
- Order-service metrics show no change, despite the reported order latency; the reported symptom may not be reflected in the telemetry
- No storage provider or infrastructure events were available
- Telemetry in the 11:10-11:20Z range is only a baseline; pool-level metrics were unavailable
- [agent-reported gap] Cloud/storage health data for vol-0a3f
- [agent-reported gap] payment-service connection pool wait metrics
- [agent-reported gap] postgres wait-event and lock data
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: agent submitted

## Final Status
`PROBABLE_ROOT_CAUSE`

The release is not the trigger. The evidence points to degraded postgres storage (vol-0a3f) starting about 11:21Z, which produced DB latency, statement timeouts and payment errors from 11:27-11:28Z, before the 11:32Z release. Confidence is moderate: the storage cause is inferred from correlated logs and metrics, and provider-side confirmation is still missing. Order-service showed no metric change, so its impact is not established from this data.

## Execution Statistics
```json
{
  "rounds": 1,
  "tool_calls": 11,
  "tool_failures": 0,
  "tool_retries": 0,
  "partial_results": 0,
  "agent_failures": 0,
  "agent_retries": 0,
  "invalid_llm_outputs": 0,
  "messages_exchanged": 0,
  "evidence_records": 46,
  "duration_s": 23.18,
  "tokens": {
    "input_tokens": 12,
    "output_tokens": 5334,
    "cache_read_tokens": 43322,
    "cache_write_tokens": 10744,
    "llm_calls": 5,
    "cost_usd": 0.00444442
  },
  "tokens_by_agent": {
    "single_agent": {
      "input_tokens": 12,
      "output_tokens": 5334,
      "cache_read_tokens": 43322,
      "cache_write_tokens": 10744,
      "llm_calls": 5,
      "cost_usd": 0.00444442
    }
  }
}
```
