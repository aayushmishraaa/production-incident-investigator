# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-001
- **Title:** Payment API latency spike
- **Severity:** SEV2
- **Affected services:** api-gateway, payment-service
- **Start time:** 2026-09-02T14:00:00+00:00
- **Investigation ID:** inv-8e3e3a318d (single_agent)
- **Final status:** `PROBABLE_ROOT_CAUSE`

## Executive Summary
Payment API latency and 5xx errors (INC-001) are caused by exhaustion of payment-service's DB connection pool (payment-db-pool). Connections leaked on the RefundService.processPartialRefund path were held for more than 30s starting about 13:45Z. Pool utilization climbed from about 13:49Z and reached 100% by 14:25Z. From 14:00Z, requests waited on the pool, timed out after 5s, and surfaced as p95 latency of about 2.7-3s and error rates near 20%. API gateway latency and errors follow the payment-service degradation. Auth, Postgres latency, CPU and disk are not implicated. No deployment or config change to payment-service was found in the window; the leak's trigger is unconfirmed.

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
### 1. H1 - `db_connection_pool_exhaustion` in `payment-service` (confidence 0.85, critic: n/a)
**INFERENCE:** Connection leak in the refund path (RefundService.processPartialRefund) exhausted payment-db-pool, causing acquisition timeouts, latency and 5xx. Mechanism: Refund code paths acquire DB connections and do not release them. Leak detection fires from 13:45Z with connections held >30s. Active connections reach the pool max of 50 with 0 idle, so new requests wait and time out after 5000ms. Latency and timeouts follow, which propagates to api-gateway.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-payment-service-9d1f3d29` (strong): 9x WARN on payment-service: 'HikariPool-payment - Connection leak detection triggered for connection conn-98, held > 30000 ms by RefundService.processPartialRefund' (first 2026-09-02T13:45:08Z, last 2026-09-02T14:00:16Z)
- [OBSERVED EVIDENCE] `logpat-payment-service-7d1739af` (strong): 29x ERROR on payment-service: 'Timeout acquiring connection from pool payment-db-pool after 5000ms (active=50, idle=0, waiting=46)' (first 2026-09-02T14:00:16Z, last 2026-09-02T14:24:16Z)
- [OBSERVED EVIDENCE] `met-payment-service-db_conn_util_pct-1330-1425` (strong): payment-service db_conn_util_pct: baseline 34.95 -> window mean 72.1 (max 100.0, change 106.3%), onset 2026-09-02T13:49:00Z
- [OBSERVED EVIDENCE] `met-payment-service-p95_latency_ms-1330-1425` (strong): payment-service p95_latency_ms: baseline 150.24 -> window mean 1315.14 (max 3018.96, change 775.3%), onset 2026-09-02T14:00:00Z
- [OBSERVED EVIDENCE] `met-payment-service-timeout_rate-1330-1425` (strong): payment-service timeout_rate: baseline 0.1 -> window mean 8.04 (max 19.09, change 7957.0%), onset 2026-09-02T14:00:00Z
- [OBSERVED EVIDENCE] `met-api-gateway-p95_latency_ms-1330-1425` (moderate): api-gateway p95_latency_ms: baseline 119.71 -> window mean 868.12 (max 2004.12, change 625.2%), onset 2026-09-02T14:01:00Z
- [INFERENCE] `hist-HIST-2025-014` (weak): Past incident HIST-2025-014 'Payment latency from leaked DB connections' (similarity 0.275): Connection leak in refund path held pooled connections; pool exhausted.

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-postgres-p95_latency_ms-1330-1425` (moderate): postgres p95_latency_ms: baseline 11.98 -> window mean 12.06 (max 12.83, change 0.7%), onset none detected
- [OBSERVED EVIDENCE] `met-payment-service-cpu_pct-1330-1425` (weak): payment-service cpu_pct: baseline 39.9 -> window mean 40.03 (max 44.07, change 0.3%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Code diff or deploy history for RefundService (no payment-service deployment in window)
- [UNKNOWN] Refund traffic volume to confirm a traffic-driven trigger
- [UNKNOWN] Thread dumps showing blocked refund connections

### 2. H2 - `upstream_dependency_degradation` in `auth-service` (confidence 0.05, critic: n/a)
**INFERENCE:** Auth-service degradation slowed payment calls. Mechanism: Slow auth calls hold payment threads, indirectly exhausting the pool.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- none

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-auth-service-p95_latency_ms-1330-1425` (strong): auth-service p95_latency_ms: baseline 44.97 -> window mean 44.96 (max 49.46, change -0.0%), onset none detected
- [OBSERVED EVIDENCE] `met-auth-service-error_rate-1330-1425` (strong): auth-service error_rate: baseline 0.3 -> window mean 0.3 (max 0.33, change 1.2%), onset none detected

### 3. H3 - `infrastructure_degradation` in `postgres` (confidence 0.05, critic: n/a)
**INFERENCE:** Postgres or infrastructure degradation. Mechanism: DB server slowness or disk I/O would make connections slow to release.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- none

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-postgres-p95_latency_ms-1330-1425` (strong): postgres p95_latency_ms: baseline 11.98 -> window mean 12.06 (max 12.83, change 0.7%), onset none detected
- [OBSERVED EVIDENCE] `met-postgres-disk_io_wait_ms-1330-1425` (moderate): postgres disk_io_wait_ms: baseline 2.0 -> window mean 1.99 (max 2.14, change -0.8%), onset none detected

## Critic Review
- **Verdict:** `NOT_RUN` (rounds reviewed: 0)
- **Reasoning:** 

## Probable Root Cause
MOST PROBABLE EXPLANATION (INFERENCE, not confirmed): db_connection_pool_exhaustion in payment-service - Connection leak in the refund path (RefundService.processPartialRefund) exhausted payment-db-pool, causing acquisition timeouts, latency and 5xx.

## Corrective Actions
- Restart payment-service pods to release leaked connections and restore capacity (short-term mitigation).
- Fix the leaked connection in RefundService.processPartialRefund by using try-with-resources or a finally-block release, then deploy.
- Add a statement or transaction timeout so refund connections cannot be held indefinitely.

## Preventive Actions
- Alert on Hikari leak-detection warnings and on pool utilization above 80% for more than 5 minutes.
- Add a load and soak test covering partial refund flows that checks for connection returns.

## Monitoring Recommendations
- Track payment-db-pool active, idle and waiting counts per pod.
- Track count of 'Connection leak detection triggered' logs by call site.
- Watch payment-service timeout_rate and p95 latency with recovery after the pod restart.

## Evidence Gaps
- none recorded

## Limitations
- Historical match similarity is low (0.275) and serves as an analogy only.
- Config and deployment queries returned no payment-service changes, which limits trigger analysis.
- [agent-reported gap] No refund traffic or code-change data in the window.
- [agent-reported gap] No thread dump or pool connection-owner snapshot.
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: agent submitted

## Final Status
`PROBABLE_ROOT_CAUSE`

The most likely root cause is a connection leak in the refund path (RefundService.processPartialRefund) that exhausted payment-service's DB connection pool beginning about 13:45Z. This caused acquisition timeouts from 14:00Z, which produced the latency and 5xx symptoms seen by api-gateway and customers. Auth, Postgres and payment CPU are ruled out as primary causes. Confidence is high but the leak trigger is not confirmed, so the status is PROBABLE_ROOT_CAUSE.

## Execution Statistics
```json
{
  "rounds": 1,
  "tool_calls": 10,
  "tool_failures": 0,
  "tool_retries": 0,
  "partial_results": 0,
  "agent_failures": 0,
  "agent_retries": 0,
  "invalid_llm_outputs": 0,
  "messages_exchanged": 0,
  "evidence_records": 52,
  "duration_s": 19.3,
  "tokens": {
    "input_tokens": 10,
    "output_tokens": 4448,
    "cache_read_tokens": 26344,
    "cache_write_tokens": 16243,
    "llm_calls": 4,
    "cost_usd": 0.004518815
  },
  "tokens_by_agent": {
    "single_agent": {
      "input_tokens": 10,
      "output_tokens": 4448,
      "cache_read_tokens": 26344,
      "cache_write_tokens": 16243,
      "llm_calls": 4,
      "cost_usd": 0.004518815
    }
  }
}
```
