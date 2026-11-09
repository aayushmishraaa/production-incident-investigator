# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-001
- **Title:** Payment API latency spike
- **Severity:** SEV2
- **Affected services:** api-gateway, payment-service
- **Start time:** 2026-09-02T14:00:00+00:00
- **Investigation ID:** inv-40d7137ba9 (single_agent)
- **Final status:** `PROBABLE_ROOT_CAUSE`

## Executive Summary
Payment API latency and 5xx errors are caused by exhaustion of payment-service's DB connection pool (payment-db-pool). Connections were leaked by RefundService.processPartialRefund starting about 13:45Z, pool utilization climbed from 13:49Z, and from 14:00Z requests timed out acquiring connections. The resulting timeouts propagated to api-gateway. Auth-service, the CPU of payment-service, and the notification-service deploy are not implicated. The leak trigger is not yet confirmed.

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
**INFERENCE:** Connection leak in the partial-refund code path (RefundService.processPartialRefund) holds pooled DB connections until the payment-db-pool is saturated, causing acquisition timeouts, latency and 5xx. Mechanism: Refund calls leak connections (held >30s, flagged by Hikari leak detection from 13:45Z). Active connections climb to the pool max of 50 with 0 idle; new checkout requests wait up to 5000ms and then fail, which raises payment-service P95 and error rate, and api-gateway P95 follows.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-payment-service-9d1f3d29` (strong): 9x WARN on payment-service: 'HikariPool-payment - Connection leak detection triggered for connection conn-98, held > 30000 ms by RefundService.processPartialRefund' (first 2026-09-02T13:45:08Z, last 2026-09-02T14:00:16Z)
- [OBSERVED EVIDENCE] `met-payment-service-db_conn_util_pct-1330-1425` (strong): payment-service db_conn_util_pct: baseline 34.95 -> window mean 72.1 (max 100.0, change 106.3%), onset 2026-09-02T13:49:00Z
- [OBSERVED EVIDENCE] `logpat-payment-service-7d1739af` (strong): 29x ERROR on payment-service: 'Timeout acquiring connection from pool payment-db-pool after 5000ms (active=50, idle=0, waiting=46)' (first 2026-09-02T14:00:16Z, last 2026-09-02T14:24:16Z)
- [OBSERVED EVIDENCE] `met-payment-service-p95_latency_ms-1330-1425` (strong): payment-service p95_latency_ms: baseline 150.24 -> window mean 1315.14 (max 3018.96, change 775.3%), onset 2026-09-02T14:00:00Z
- [OBSERVED EVIDENCE] `met-payment-service-timeout_rate-1330-1425` (strong): payment-service timeout_rate: baseline 0.1 -> window mean 8.04 (max 19.09, change 7957.0%), onset 2026-09-02T14:00:00Z
- [OBSERVED EVIDENCE] `met-payment-service-error_rate-1330-1425` (strong): payment-service error_rate: baseline 0.8 -> window mean 9.93 (max 23.67, change 1139.4%), onset 2026-09-02T14:00:00Z
- [OBSERVED EVIDENCE] `met-api-gateway-p95_latency_ms-1330-1425` (moderate): api-gateway p95_latency_ms: baseline 119.71 -> window mean 868.12 (max 2004.12, change 625.2%), onset 2026-09-02T14:01:00Z
- [OBSERVED EVIDENCE] `met-api-gateway-error_rate-1330-1425` (moderate): api-gateway error_rate: baseline 0.5 -> window mean 4.05 (max 9.88, change 710.4%), onset 2026-09-02T14:01:00Z
- [INFERENCE] `hist-HIST-2025-014` (weak): Past incident HIST-2025-014 'Payment latency from leaked DB connections' (similarity 0.362): Connection leak in refund path held pooled connections; pool exhausted.

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-payment-service-cpu_pct-1330-1425` (weak): payment-service cpu_pct: baseline 39.9 -> window mean 40.03 (max 44.07, change 0.3%), onset none detected
- [OBSERVED EVIDENCE] `met-api-gateway-timeout_rate-1330-1425` (weak): api-gateway timeout_rate: baseline 0.1 -> window mean 0.1 (max 0.11, change 0.4%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Refund request volume or traffic data for the 13:30-14:00 period, to show whether a refund burst or a code change caused the leak
- [UNKNOWN] Postgres-side metrics (active connections, lock waits, query duration), which were not available as a service
- [UNKNOWN] Code or version diff for RefundService; no deployment to payment-service was found in 12:00-14:25Z

### 2. H2 - `upstream_dependency_degradation` in `auth-service` (confidence 0.05, critic: n/a)
**INFERENCE:** Auth-service degradation slowed payment calls and caused connection hold times to rise. Mechanism: Slow auth calls would hold request threads and DB connections in payment-service.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- none

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-auth-service-p95_latency_ms-1330-1425` (strong): auth-service p95_latency_ms: baseline 44.97 -> window mean 44.96 (max 49.46, change -0.0%), onset none detected
- [OBSERVED EVIDENCE] `met-auth-service-error_rate-1330-1425` (strong): auth-service error_rate: baseline 0.3 -> window mean 0.3 (max 0.33, change 1.2%), onset none detected
- [OBSERVED EVIDENCE] `met-auth-service-db_conn_util_pct-1330-1425` (moderate): auth-service db_conn_util_pct: baseline 29.53 -> window mean 30.06 (max 32.48, change 1.8%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Auth-side logs for the window

### 3. H3 - `deployment_regression` in `notification-service` (confidence 0.02, critic: n/a)
**INFERENCE:** The notification-service deploy at 13:54Z (3.4.0 to 3.4.1, email templates) caused the incident. Mechanism: Would require a dependency path from notification-service to payment-service.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- none

Contradicting evidence:
- [CONFIRMED FACT] `dep-d757f128` (moderate): Deployment of notification-service 3.4.0->3.4.1 at 2026-09-02T13:54:00Z (SUCCEEDED): Update email templates for receipts

## Critic Review
- **Verdict:** `NOT_RUN` (rounds reviewed: 0)
- **Reasoning:** 

## Probable Root Cause
MOST PROBABLE EXPLANATION (INFERENCE, not confirmed): db_connection_pool_exhaustion in payment-service - Connection leak in the partial-refund code path (RefundService.processPartialRefund) holds pooled DB connections until the payment-db-pool is saturated, causing acquisition timeouts, latency and 5xx.

## Corrective Actions
- Restart payment-service pods to release leaked connections and restore checkout (immediate mitigation).
- Fix the connection leak in RefundService.processPartialRefund (close connections via try-with-resources or equivalent), then redeploy.
- Verify that partial refunds are not blocked or failing in a way that compounds the leak; reprocess any stuck refunds.

## Preventive Actions
- Alert on Hikari leak detection warnings and on pool utilization above 80% for sustained periods.
- Add a statement or connection-hold timeout on the payment DB pool so leaks fail fast.
- Add a load and soak test for the refund path that checks for connection return.

## Monitoring Recommendations
- payment-service db_conn_util_pct and active/waiting connection counts on payment-db-pool.
- Count of 'Connection leak detection triggered' warnings by call site.
- payment-service P95 and error rate, with api-gateway P95 as a downstream signal.
- Postgres idle-in-transaction and long-running session counts for the payment database.

## Evidence Gaps
- none recorded

## Limitations
- No Postgres or refund-volume telemetry was available; the refund-path trigger is inferred.
- Historical match HIST-2025-014 is an analogy only (similarity 0.36).
- [agent-reported gap] No refund traffic data to explain why the refund leak began at 13:45Z.
- [agent-reported gap] No code or version diff for RefundService.
- [agent-reported gap] No Postgres-side metrics.
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: agent submitted

## Final Status
`PROBABLE_ROOT_CAUSE`

The most likely cause is a connection leak in RefundService.processPartialRefund that exhausted payment-service's payment-db-pool (max 50). The leak began about 13:45Z, the pool was saturated by 14:00Z, and connection-acquisition timeouts drove the payment P95, error and timeout spikes, and the api-gateway latency and 5xx that followed. Alternatives (auth-service, CPU saturation, the notification deploy, a gateway-side issue) are contradicted by the evidence. The status is PROBABLE rather than ROOT_CAUSE_IDENTIFIED because the trigger for the leaking refund path (traffic change or code change) has not been confirmed and no Postgres-side data was available.

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
  "evidence_records": 50,
  "duration_s": 22.4,
  "tokens": {
    "input_tokens": 10,
    "output_tokens": 5117,
    "cache_read_tokens": 28965,
    "cache_write_tokens": 18435,
    "llm_calls": 4,
    "cost_usd": 0.005153525000000001
  },
  "tokens_by_agent": {
    "single_agent": {
      "input_tokens": 10,
      "output_tokens": 5117,
      "cache_read_tokens": 28965,
      "cache_write_tokens": 18435,
      "llm_calls": 4,
      "cost_usd": 0.005153525000000001
    }
  }
}
```
