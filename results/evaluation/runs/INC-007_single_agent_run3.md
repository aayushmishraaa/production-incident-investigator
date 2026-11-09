# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-007
- **Title:** Order checkout failing
- **Severity:** SEV2
- **Affected services:** order-service
- **Start time:** 2026-09-20T15:25:00+00:00
- **Investigation ID:** inv-7a75b8c6e3 (single_agent)
- **Final status:** `PROBABLE_ROOT_CAUSE`

## Executive Summary
Order checkout failures (order-service error rate ~0.6% -> ~29-32%, onset 15:23-15:25Z) coincide within about one minute of a configuration change by config-bot (OPS-2375) that cut order-service's payment_client.timeout_ms from 3000ms to 300ms at 15:22Z. Order-service logs are dominated by 'request to payment-service timed out after 300ms' errors, followed by circuit-breaker OPEN and retry-budget exhaustion. payment-service shows no degradation (p50/p95 latency, error rate and CPU flat vs baseline), consistent with the payment team's claim that their service is healthy. The timeout reduction is the most likely cause; the mechanism for why a 300ms timeout times out on a payment service whose p95 is ~150ms is not fully explained by the available data.

## Incident Timeline
| Time (UTC) | Label | Event | Evidence |
|---|---|---|---|
| 2026-09-20T14:40:00Z | CONFIRMED FACT | Deployment of payment-service 5.8.0->5.8.1 at 2026-09-20T14:40:00Z (SUCCEEDED): Improve charge idempotency | dep-7cf38f2d |
| 2026-09-20T14:55:41Z | OBSERVED EVIDENCE | First log: 6x WARN on order-service: 'Inventory reservation retry for sku-75' (first 2026-09-20T14:55:41Z, last 2026-09-20T15:47:11Z) | logpat-order-service-95abd1bb |
| 2026-09-20T15:22:00Z | CONFIRMED FACT | Config change on order-service: payment_client.timeout_ms 3000 -> 300 at 2026-09-20T15:22:00Z (OPS-2375) | cfg-7f81d14a |
| 2026-09-20T15:23:00Z | OBSERVED EVIDENCE | Anomaly onset: order-service error_rate: baseline 0.6 -> window mean 14.54 (max 31.99, change 2328.5%), onset 2026-09-20T15:23:00Z | met-order-service-error_rate-1455-1550 |
| 2026-09-20T15:23:00Z | OBSERVED EVIDENCE | Anomaly onset: order-service timeout_rate: baseline 0.1 -> window mean 16.87 (max 35.8, change 16649.6%), onset 2026-09-20T15:23:00Z | met-order-service-timeout_rate-1455-1550 |
| 2026-09-20T15:23:20Z | OBSERVED EVIDENCE | First log: 29x ERROR on order-service: 'PaymentClient: request to payment-service timed out after 300ms (POST /v1/charges, req 30)' (first 2026-09-20T15:23:20Z, last 2026-09-20T15:49:24Z) | logpat-order-service-f003ad98 |
| 2026-09-20T15:24:10Z | OBSERVED EVIDENCE | First log: 7x WARN on order-service: 'Circuit breaker payment-service OPEN (failure ratio 0.64)' (first 2026-09-20T15:24:10Z, last 2026-09-20T15:46:21Z) | logpat-order-service-e2b30f44 |
| 2026-09-20T15:25:00Z | CONFIRMED FACT | Reported symptom start |  |
| 2026-09-20T15:25:13Z | OBSERVED EVIDENCE | First log: 5x WARN on order-service: 'Retry budget exhausted for payment calls' (first 2026-09-20T15:25:13Z, last 2026-09-20T15:45:20Z) | logpat-order-service-809f4936 |
| 2026-09-20T15:31:00Z | CONFIRMED FACT | Incident reported |  |

## Observed Symptoms
- **OBSERVED EVIDENCE:** order-service error_rate: baseline 0.6 -> window mean 14.54 (max 31.99, change 2328.5%), onset 2026-09-20T15:23:00Z (met-order-service-error_rate-1455-1550)
- **OBSERVED EVIDENCE:** order-service timeout_rate: baseline 0.1 -> window mean 16.87 (max 35.8, change 16649.6%), onset 2026-09-20T15:23:00Z (met-order-service-timeout_rate-1455-1550)

## Investigation Performed

## Root-Cause Hypotheses (ranked by evidence strength)
### 1. H1 - `configuration_regression` in `order-service` (confidence 0.80, critic: n/a)
**INFERENCE:** Config change reducing order-service payment_client.timeout_ms from 3000ms to 300ms (cfg-7f81d14a, OPS-2375) causes payment calls to time out, driving checkout failures. Mechanism: With a 300ms client timeout, a fraction of POST /v1/charges calls exceed the budget, triggering timeouts, circuit breaker opening (failure ratio 0.64) and retry-budget exhaustion, so checkout requests fail. Order-service error and timeout rates step up at 15:23-15:25Z, within ~1-3 minutes of the change at 15:22Z.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [CONFIRMED FACT] `cfg-7f81d14a` (strong): Config change on order-service: payment_client.timeout_ms 3000 -> 300 at 2026-09-20T15:22:00Z (OPS-2375)
- [OBSERVED EVIDENCE] `met-order-service-error_rate-1455-1550` (strong): order-service error_rate: baseline 0.6 -> window mean 14.54 (max 31.99, change 2328.5%), onset 2026-09-20T15:23:00Z
- [OBSERVED EVIDENCE] `met-order-service-timeout_rate-1455-1550` (strong): order-service timeout_rate: baseline 0.1 -> window mean 16.87 (max 35.8, change 16649.6%), onset 2026-09-20T15:23:00Z
- [OBSERVED EVIDENCE] `logpat-order-service-f003ad98` (strong): 29x ERROR on order-service: 'PaymentClient: request to payment-service timed out after 300ms (POST /v1/charges, req 30)' (first 2026-09-20T15:23:20Z, last 2026-09-20T15:49:24Z)
- [OBSERVED EVIDENCE] `logpat-order-service-e2b30f44` (moderate): 7x WARN on order-service: 'Circuit breaker payment-service OPEN (failure ratio 0.64)' (first 2026-09-20T15:24:10Z, last 2026-09-20T15:46:21Z)
- [OBSERVED EVIDENCE] `logpat-order-service-809f4936` (moderate): 5x WARN on order-service: 'Retry budget exhausted for payment calls' (first 2026-09-20T15:25:13Z, last 2026-09-20T15:45:20Z)

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-payment-service-p95_latency_ms-1455-1550` (moderate): payment-service p95_latency_ms: baseline 150.46 -> window mean 150.97 (max 167.91, change 0.3%), onset none detected
- [OBSERVED EVIDENCE] `met-order-service-p99_latency_ms-1455-1550` (weak): order-service p99_latency_ms: baseline 403.46 -> window mean 399.41 (max 433.28, change -1.0%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] payment-service p99 / tail latency and request-level traces for POST /v1/charges
- [UNKNOWN] confirmation that the 300ms timeout applies only to the charge path
- [UNKNOWN] direct measurement of payment-service response times as seen from order-service

### 2. H2 - `upstream_dependency_degradation` in `payment-service` (confidence 0.10, critic: n/a)
**INFERENCE:** Payment-service degradation (e.g., tail latency) causes charge calls to exceed timeout. Mechanism: Payment-service tail latency increases so that calls exceed the 300ms budget.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- none

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-payment-service-p50_latency_ms-1455-1550` (strong): payment-service p50_latency_ms: baseline 60.17 -> window mean 60.25 (max 65.57, change 0.1%), onset none detected
- [OBSERVED EVIDENCE] `met-payment-service-p95_latency_ms-1455-1550` (strong): payment-service p95_latency_ms: baseline 150.46 -> window mean 150.97 (max 167.91, change 0.3%), onset none detected
- [OBSERVED EVIDENCE] `met-payment-service-error_rate-1455-1550` (strong): payment-service error_rate: baseline 0.8 -> window mean 0.8 (max 0.88, change 0.7%), onset none detected
- [CONFIRMED FACT] `dep-7cf38f2d` (weak): Deployment of payment-service 5.8.0->5.8.1 at 2026-09-20T14:40:00Z (SUCCEEDED): Improve charge idempotency

Remaining uncertainties / missing evidence:
- [UNKNOWN] payment-service p99 tail latency

### 3. H3 - `db_connection_pool_exhaustion` in `None` (confidence 0.05, critic: n/a)
**INFERENCE:** Order-service database connection pool exhaustion causes checkout failures. Mechanism: Connection starvation would cause errors and latency rises in order-service.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- none

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-order-service-db_conn_util_pct-1455-1550` (strong): order-service db_conn_util_pct: baseline 30.19 -> window mean 30.17 (max 32.46, change -0.1%), onset none detected

## Critic Review
- **Verdict:** `NOT_RUN` (rounds reviewed: 0)
- **Reasoning:** 

## Probable Root Cause
MOST PROBABLE EXPLANATION (INFERENCE, not confirmed): configuration_regression in order-service - Config change reducing order-service payment_client.timeout_ms from 3000ms to 300ms (cfg-7f81d14a, OPS-2375) causes payment calls to time out, driving checkout failures.

## Corrective Actions
- Revert payment_client.timeout_ms on order-service from 300ms to the previous 3000ms (cfg-7f81d14a) and confirm error rate returns to ~0.6%
- Reset the payment-service circuit breaker on order-service after the revert and verify recovery of checkout

## Preventive Actions
- Require review/validation for timeout changes on payment clients; guard config-bot changes with bounds checks (e.g., reject >10x reduction without approval)
- Canary config changes to a subset of order-service instances before fleet-wide rollout

## Monitoring Recommendations
- Alert on order-service payment_client timeout rate and circuit-breaker OPEN events
- Dashboard payment-service p99 and client-side latency as seen by order-service to validate timeout budgets

## Evidence Gaps
- none recorded

## Limitations
- Investigation relied on aggregated metrics and log patterns; individual request traces were not available
- Deployment and config queries were limited to the 14:00-15:50Z window and specific keys
- [agent-reported gap] payment-service tail latency (p99/p999) and client-side traces not available
- [agent-reported gap] No direct trace of timed-out requests showing where the time was spent
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: agent submitted

## Final Status
`PROBABLE_ROOT_CAUSE`

The checkout failure is most likely caused by the order-service payment client timeout being reduced from 3000ms to 300ms at 15:22Z (cfg-7f81d14a), which precedes the error onset at 15:23Z. Payment-service shows no degradation, so the payment team's health claim is consistent with the data. Status is PROBABLE rather than confirmed because payment tail latency and request-level traces are not available to explain why a 300ms timeout fails at this rate when payment p95 is ~150ms.

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
  "evidence_records": 30,
  "duration_s": 18.77,
  "tokens": {
    "input_tokens": 8,
    "output_tokens": 4156,
    "cache_read_tokens": 23176,
    "cache_write_tokens": 1798,
    "llm_calls": 3,
    "cost_usd": 0.00253531
  },
  "tokens_by_agent": {
    "single_agent": {
      "input_tokens": 8,
      "output_tokens": 4156,
      "cache_read_tokens": 23176,
      "cache_write_tokens": 1798,
      "llm_calls": 3,
      "cost_usd": 0.00253531
    }
  }
}
```
