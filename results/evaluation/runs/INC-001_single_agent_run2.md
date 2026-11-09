# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-001
- **Title:** Payment API latency spike
- **Severity:** SEV2
- **Affected services:** api-gateway, payment-service
- **Start time:** 2026-09-02T14:00:00+00:00
- **Investigation ID:** inv-3cbe3107d6 (single_agent)
- **Final status:** `PROBABLE_ROOT_CAUSE`

## Executive Summary
Checkout latency (3-5s) and 5xx payment failures began at 14:00Z. payment-service's DB connection pool saturated (100% utilisation) because connections were leaked on the partial-refund path. Log pattern logpat-payment-service-9d1f3d29 shows 9 leak-detection warnings from RefundService.processPartialRefund (held >30s) starting 13:45Z, and pool timeouts (logpat-payment-service-7d1739af, 29 events) from 14:00Z. api-gateway latency and errors follow payment-service, consistent with downstream impact. Postgres and auth-service are healthy. No config change was found; the only deployment in the window (notification-service 3.4.1 at 13:54Z) has no link to the payment pool. Recommended immediate action: restart payment-service pods to release leaked connections, and roll back or fix the refund code path.

## Incident Timeline
| Time (UTC) | Label | Event | Evidence |
|---|---|---|---|
| 2026-09-02T13:45:08Z | OBSERVED EVIDENCE | First log: 9x WARN on payment-service: 'HikariPool-payment - Connection leak detection triggered for connection conn-98, held > 30000 ms by RefundService.processPartialRefund' (first 2026-09-02T13:45:08Z, last 2026-09-02T14:00:16Z) | logpat-payment-service-9d1f3d29 |
| 2026-09-02T13:49:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service db_conn_util_pct: baseline 34.95 -> window mean 72.1 (max 100.0, change 106.3%), onset 2026-09-02T13:49:00Z | met-payment-service-db_conn_util_pct-1330-1425 |
| 2026-09-02T13:49:52Z | OBSERVED EVIDENCE | First log: 3x WARN on payment-service: 'Card network soft decline (code 05) for charge ch_33' (first 2026-09-02T13:49:52Z, last 2026-09-02T14:20:23Z) | logpat-payment-service-7e9bf84f |
| 2026-09-02T13:54:00Z | CONFIRMED FACT | Deployment of notification-service 3.4.0->3.4.1 at 2026-09-02T13:54:00Z (SUCCEEDED): Update email templates for receipts | dep-d757f128 |
| 2026-09-02T14:00:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service p95_latency_ms: baseline 150.24 -> window mean 1315.14 (max 3018.96, change 775.3%), onset 2026-09-02T14:00:00Z | met-payment-service-p95_latency_ms-1330-1425 |
| 2026-09-02T14:00:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service error_rate: baseline 0.8 -> window mean 9.93 (max 23.67, change 1139.4%), onset 2026-09-02T14:00:00Z | met-payment-service-error_rate-1330-1425 |
| 2026-09-02T14:00:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service timeout_rate: baseline 0.1 -> window mean 8.04 (max 19.09, change 7957.0%), onset 2026-09-02T14:00:00Z | met-payment-service-timeout_rate-1330-1425 |
| 2026-09-02T14:00:00Z | CONFIRMED FACT | Reported symptom start |  |
| 2026-09-02T14:00:16Z | OBSERVED EVIDENCE | First log: 29x ERROR on payment-service: 'Timeout acquiring connection from pool payment-db-pool after 5000ms (active=50, idle=0, waiting=46)' (first 2026-09-02T14:00:16Z, last 2026-09-02T14:24:16Z) | logpat-payment-service-7d1739af |
| 2026-09-02T14:01:00Z | OBSERVED EVIDENCE | Anomaly onset: api-gateway p95_latency_ms: baseline 119.71 -> window mean 868.12 (max 2004.12, change 625.2%), onset 2026-09-02T14:01:00Z | met-api-gateway-p95_latency_ms-1330-1425 |
| 2026-09-02T14:01:00Z | OBSERVED EVIDENCE | Anomaly onset: api-gateway error_rate: baseline 0.5 -> window mean 4.05 (max 9.88, change 710.4%), onset 2026-09-02T14:01:00Z | met-api-gateway-error_rate-1330-1425 |
| 2026-09-02T14:06:00Z | CONFIRMED FACT | Incident reported |  |

## Observed Symptoms
- **OBSERVED EVIDENCE:** payment-service p95_latency_ms: baseline 150.24 -> window mean 1315.14 (max 3018.96, change 775.3%), onset 2026-09-02T14:00:00Z (met-payment-service-p95_latency_ms-1330-1425)
- **OBSERVED EVIDENCE:** payment-service error_rate: baseline 0.8 -> window mean 9.93 (max 23.67, change 1139.4%), onset 2026-09-02T14:00:00Z (met-payment-service-error_rate-1330-1425)
- **OBSERVED EVIDENCE:** payment-service db_conn_util_pct: baseline 34.95 -> window mean 72.1 (max 100.0, change 106.3%), onset 2026-09-02T13:49:00Z (met-payment-service-db_conn_util_pct-1330-1425)
- **OBSERVED EVIDENCE:** payment-service timeout_rate: baseline 0.1 -> window mean 8.04 (max 19.09, change 7957.0%), onset 2026-09-02T14:00:00Z (met-payment-service-timeout_rate-1330-1425)
- **OBSERVED EVIDENCE:** api-gateway p95_latency_ms: baseline 119.71 -> window mean 868.12 (max 2004.12, change 625.2%), onset 2026-09-02T14:01:00Z (met-api-gateway-p95_latency_ms-1330-1425)
- **OBSERVED EVIDENCE:** api-gateway error_rate: baseline 0.5 -> window mean 4.05 (max 9.88, change 710.4%), onset 2026-09-02T14:01:00Z (met-api-gateway-error_rate-1330-1425)

## Investigation Performed

## Root-Cause Hypotheses (ranked by evidence strength)
### 1. H1 - `db_connection_pool_exhaustion` in `payment-service` (confidence 0.80, critic: n/a)
**INFERENCE:** Connection leak in RefundService.processPartialRefund exhausts payment-db-pool in payment-service, causing acquisition timeouts, latency and 5xx that propagate to api-gateway. Mechanism: Refund path acquires pooled DB connections and does not release them (likely missing try-with-resources or a long-held transaction). Leaked connections accumulate from ~13:45Z, active reaches the 50-connection cap, and new checkout requests wait the full 5s acquisition timeout and fail. The retry and timeout path raises p95 and error rate.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-payment-service-9d1f3d29` (strong): 9x WARN on payment-service: 'HikariPool-payment - Connection leak detection triggered for connection conn-98, held > 30000 ms by RefundService.processPartialRefund' (first 2026-09-02T13:45:08Z, last 2026-09-02T14:00:16Z)
- [OBSERVED EVIDENCE] `logpat-payment-service-7d1739af` (strong): 29x ERROR on payment-service: 'Timeout acquiring connection from pool payment-db-pool after 5000ms (active=50, idle=0, waiting=46)' (first 2026-09-02T14:00:16Z, last 2026-09-02T14:24:16Z)
- [OBSERVED EVIDENCE] `met-payment-service-db_conn_util_pct-1330-1425` (strong): payment-service db_conn_util_pct: baseline 34.95 -> window mean 72.1 (max 100.0, change 106.3%), onset 2026-09-02T13:49:00Z
- [OBSERVED EVIDENCE] `met-payment-service-p95_latency_ms-1330-1425` (strong): payment-service p95_latency_ms: baseline 150.24 -> window mean 1315.14 (max 3018.96, change 775.3%), onset 2026-09-02T14:00:00Z
- [OBSERVED EVIDENCE] `met-payment-service-timeout_rate-1330-1425` (strong): payment-service timeout_rate: baseline 0.1 -> window mean 8.04 (max 19.09, change 7957.0%), onset 2026-09-02T14:00:00Z
- [OBSERVED EVIDENCE] `met-payment-service-error_rate-1330-1425` (strong): payment-service error_rate: baseline 0.8 -> window mean 9.93 (max 23.67, change 1139.4%), onset 2026-09-02T14:00:00Z
- [OBSERVED EVIDENCE] `met-api-gateway-p95_latency_ms-1330-1425` (moderate): api-gateway p95_latency_ms: baseline 119.71 -> window mean 868.12 (max 2004.12, change 625.2%), onset 2026-09-02T14:01:00Z
- [INFERENCE] `hist-HIST-2025-014` (weak): Past incident HIST-2025-014 'Payment latency from leaked DB connections' (similarity 0.347): Connection leak in refund path held pooled connections; pool exhausted.

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-postgres-p95_latency_ms-1330-1425` (moderate): postgres p95_latency_ms: baseline 11.98 -> window mean 12.06 (max 12.83, change 0.7%), onset none detected
- [OBSERVED EVIDENCE] `met-payment-service-cpu_pct-1330-1425` (weak): payment-service cpu_pct: baseline 39.9 -> window mean 40.03 (max 44.07, change 0.3%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] No deployment of payment-service or RefundService code in the window (get_deployments returned only notification-service); the trigger for the leak is unknown
- [UNKNOWN] No refund request volume metrics to check for a refund traffic surge
- [UNKNOWN] No thread dump or connection holder stack trace beyond the leak-detection message

### 2. H2 - `upstream_dependency_degradation` in `postgres` (confidence 0.10, critic: n/a)
**INFERENCE:** Database-side slowness or contention causes connections to be held longer, exhausting the pool. Mechanism: If postgres were slow, queries would hold connections longer and fill the pool.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `met-postgres-db_conn_util_pct-1330-1425` (weak): postgres db_conn_util_pct: baseline 40.59 -> window mean 53.15 (max 67.91, change 31.0%), onset 2026-09-02T13:55:00Z

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-postgres-p95_latency_ms-1330-1425` (strong): postgres p95_latency_ms: baseline 11.98 -> window mean 12.06 (max 12.83, change 0.7%), onset none detected
- [OBSERVED EVIDENCE] `met-postgres-disk_io_wait_ms-1330-1425` (moderate): postgres disk_io_wait_ms: baseline 2.0 -> window mean 1.99 (max 2.14, change -0.8%), onset none detected
- [OBSERVED EVIDENCE] `met-postgres-cpu_pct-1330-1425` (moderate): postgres cpu_pct: baseline 34.63 -> window mean 34.97 (max 38.3, change 1.0%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] No postgres lock or long-query telemetry

### 3. H3 - `upstream_dependency_degradation` in `auth-service` (confidence 0.05, critic: n/a)
**INFERENCE:** auth-service degradation slows checkout calls and holds payment threads. Mechanism: Slow auth calls would hold request threads, increasing payment latency.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- none

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-auth-service-p95_latency_ms-1330-1425` (strong): auth-service p95_latency_ms: baseline 44.97 -> window mean 44.96 (max 49.46, change -0.0%), onset none detected
- [OBSERVED EVIDENCE] `met-auth-service-error_rate-1330-1425` (moderate): auth-service error_rate: baseline 0.3 -> window mean 0.3 (max 0.33, change 1.2%), onset none detected

## Critic Review
- **Verdict:** `NOT_RUN` (rounds reviewed: 0)
- **Reasoning:** 

## Probable Root Cause
MOST PROBABLE EXPLANATION (INFERENCE, not confirmed): db_connection_pool_exhaustion in payment-service - Connection leak in RefundService.processPartialRefund exhausts payment-db-pool in payment-service, causing acquisition timeouts, latency and 5xx that propagate to api-gateway.

## Corrective Actions
- Restart payment-service pods to release leaked connections and restore checkout (immediate mitigation)
- Fix the connection leak in RefundService.processPartialRefund: release connections in a finally block or try-with-resources, and bound transaction duration
- Roll back any recent RefundService change if the leak is traced to a specific release

## Preventive Actions
- Add a code review and integration test for connection release on exception paths in refund flows
- Set a pool max-lifetime and a statement or transaction timeout for payment-db-pool

## Monitoring Recommendations
- Alert on HikariPool connection-leak warnings (any occurrence) and on pool utilisation above 80% for 5 minutes
- Track active connections held per call site (RefundService vs checkout) in payment-service
- Dashboard payment-service timeout_rate and error_rate with pool wait time

## Evidence Gaps
- none recorded

## Limitations
- Evidence is temporal and log-based; the leak was not reproduced
- Trigger for the leak is not identified
- Historical match similarity is only 0.35 and serves as an analogy only
- [agent-reported gap] No commit or deploy record explaining why the refund path began leaking at about 13:45Z
- [agent-reported gap] No refund traffic volume metrics for the 13:30-13:50 window
- [agent-reported gap] No thread dumps or pg_stat_activity snapshots to confirm connection holders
- [agent-reported gap] Deployment query covered only the 12:30-14:25 window and returned only notification-service
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: agent submitted

## Final Status
`PROBABLE_ROOT_CAUSE`

The payment-service latency spike and 5xx errors are caused by exhaustion of the payment-db-pool connection pool. Connections checked out by RefundService.processPartialRefund were leaked and held for more than 30s, so the pool filled (active=50, idle=0, large waiting queue) and new requests timed out acquiring connections. The database itself is not the bottleneck (postgres p95 latency flat at ~12ms, CPU and disk flat). The leak started at about 13:45Z, pool utilisation rose from 13:49Z, and saturation coincided with the 14:00Z onset of latency and errors. The mechanism matches a known historical pattern, but the trigger for the leak (code change or refund traffic change) is not yet confirmed.

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
  "evidence_records": 48,
  "duration_s": 24.05,
  "tokens": {
    "input_tokens": 10,
    "output_tokens": 5580,
    "cache_read_tokens": 30910,
    "cache_write_tokens": 11628,
    "llm_calls": 4,
    "cost_usd": 0.0045536
  },
  "tokens_by_agent": {
    "single_agent": {
      "input_tokens": 10,
      "output_tokens": 5580,
      "cache_read_tokens": 30910,
      "cache_write_tokens": 11628,
      "llm_calls": 4,
      "cost_usd": 0.0045536
    }
  }
}
```
