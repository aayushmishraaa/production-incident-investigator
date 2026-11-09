# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-007
- **Title:** Order checkout failing
- **Severity:** SEV2
- **Affected services:** order-service
- **Start time:** 2026-09-20T15:25:00+00:00
- **Investigation ID:** inv-1f276bd125 (single_agent)
- **Final status:** `ROOT_CAUSE_IDENTIFIED`

## Executive Summary
INC-007 checkout failures are caused by a configuration change in order-service that lowered payment_client.timeout_ms from 3000 ms to 300 ms at 15:22Z (OPS-2375, config-bot). Starting at 15:23Z, order-service's calls to payment-service began timing out at 300 ms, error rate rose from ~0.6% to ~29-32%, and the payment-service circuit breaker opened. payment-service itself shows no error or latency regression; the payment team's "healthy" assessment is consistent with its own metrics.

## Incident Timeline
| Time (UTC) | Label | Event | Evidence |
|---|---|---|---|
| 2026-09-20T14:40:00Z | CONFIRMED FACT | Deployment of payment-service 5.8.0->5.8.1 at 2026-09-20T14:40:00Z (SUCCEEDED): Improve charge idempotency | dep-7cf38f2d |
| 2026-09-20T14:55:41Z | OBSERVED EVIDENCE | First log: 6x WARN on order-service: 'Inventory reservation retry for sku-75' (first 2026-09-20T14:55:41Z, last 2026-09-20T15:47:11Z) | logpat-order-service-95abd1bb |
| 2026-09-20T15:00:17Z | OBSERVED EVIDENCE | First log: 3x WARN on payment-service: 'Card network soft decline (code 05) for charge ch_30' (first 2026-09-20T15:00:17Z, last 2026-09-20T15:37:11Z) | logpat-payment-service-7e9bf84f |
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
### 1. H1 - `configuration_regression` in `order-service` (confidence 0.90, critic: n/a)
**INFERENCE:** Misconfigured payment client timeout (3000 -> 300 ms) in order-service causes premature timeouts on POST /v1/charges. Mechanism: At 15:22Z payment_client.timeout_ms was changed to 300. From 15:23Z, order-service logged PaymentClient timeouts after 300ms; timeout_rate went from 0.1% to ~35%, error_rate from 0.6% to ~30%, the payment circuit breaker opened (failure ratio 0.64), and retry budget was exhausted. Payment-service's p50 (~60ms) and p99 (~300ms) are unchanged, so a large share of calls that previously completed within the 3s budget now exceed 300ms.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [CONFIRMED FACT] `cfg-7f81d14a` (strong): Config change on order-service: payment_client.timeout_ms 3000 -> 300 at 2026-09-20T15:22:00Z (OPS-2375)
- [OBSERVED EVIDENCE] `logpat-order-service-f003ad98` (strong): 29x ERROR on order-service: 'PaymentClient: request to payment-service timed out after 300ms (POST /v1/charges, req 30)' (first 2026-09-20T15:23:20Z, last 2026-09-20T15:49:24Z)
- [OBSERVED EVIDENCE] `met-order-service-error_rate-1455-1550` (strong): order-service error_rate: baseline 0.6 -> window mean 14.54 (max 31.99, change 2328.5%), onset 2026-09-20T15:23:00Z
- [OBSERVED EVIDENCE] `met-order-service-timeout_rate-1455-1550` (strong): order-service timeout_rate: baseline 0.1 -> window mean 16.87 (max 35.8, change 16649.6%), onset 2026-09-20T15:23:00Z
- [OBSERVED EVIDENCE] `logpat-order-service-e2b30f44` (moderate): 7x WARN on order-service: 'Circuit breaker payment-service OPEN (failure ratio 0.64)' (first 2026-09-20T15:24:10Z, last 2026-09-20T15:46:21Z)
- [OBSERVED EVIDENCE] `logpat-order-service-809f4936` (moderate): 5x WARN on order-service: 'Retry budget exhausted for payment calls' (first 2026-09-20T15:25:13Z, last 2026-09-20T15:45:20Z)

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-payment-service-p99_latency_ms-1455-1550` (weak): payment-service p99_latency_ms: baseline 299.35 -> window mean 300.26 (max 321.35, change 0.3%), onset none detected
- [OBSERVED EVIDENCE] `met-payment-service-error_rate-1455-1550` (weak): payment-service error_rate: baseline 0.8 -> window mean 0.8 (max 0.88, change 0.7%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Client-side latency distribution for order->payment calls (not server-side only)
- [UNKNOWN] Confirmation that the config change was applied to all order-service instances and its rollout time

### 2. H2 - `upstream_dependency_degradation` in `payment-service` (confidence 0.05, critic: n/a)
**INFERENCE:** payment-service degraded (latency or capacity), causing order-service timeouts. Mechanism: If payment-service slowed, order calls would time out at any timeout value.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- none

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-payment-service-p50_latency_ms-1455-1550` (strong): payment-service p50_latency_ms: baseline 60.17 -> window mean 60.25 (max 65.57, change 0.1%), onset none detected
- [OBSERVED EVIDENCE] `met-payment-service-p99_latency_ms-1455-1550` (strong): payment-service p99_latency_ms: baseline 299.35 -> window mean 300.26 (max 321.35, change 0.3%), onset none detected
- [OBSERVED EVIDENCE] `met-payment-service-error_rate-1455-1550` (strong): payment-service error_rate: baseline 0.8 -> window mean 0.8 (max 0.88, change 0.7%), onset none detected
- [OBSERVED EVIDENCE] `logpat-payment-service-0e974150` (moderate): 5x INFO on payment-service: 'Processed 46 charges in last minute' (first 2026-09-20T15:04:38Z, last 2026-09-20T15:42:11Z)

Remaining uncertainties / missing evidence:
- [UNKNOWN] Payment-service-side CPU/DB metrics were not queried

### 3. H3 - `deployment_regression` in `payment-service` (confidence 0.05, critic: n/a)
**INFERENCE:** payment-service 5.8.1 deployment at 14:40Z (charge idempotency change) introduced a regression. Mechanism: A code change could add latency or errors to charges.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- none

Contradicting evidence:
- [CONFIRMED FACT] `dep-7cf38f2d` (moderate): Deployment of payment-service 5.8.0->5.8.1 at 2026-09-20T14:40:00Z (SUCCEEDED): Improve charge idempotency
- [OBSERVED EVIDENCE] `met-payment-service-error_rate-1455-1550` (strong): payment-service error_rate: baseline 0.8 -> window mean 0.8 (max 0.88, change 0.7%), onset none detected

## Critic Review
- **Verdict:** `NOT_RUN` (rounds reviewed: 0)
- **Reasoning:** 

## Probable Root Cause
ROOT CAUSE IDENTIFIED (critic-approved; still an INFERENCE from evidence): configuration_regression in order-service - Misconfigured payment client timeout (3000 -> 300 ms) in order-service causes premature timeouts on POST /v1/charges.

## Corrective Actions
- Revert payment_client.timeout_ms in order-service from 300 back to 3000 ms (OPS-2375), verify on all instances.
- Once reverted, confirm the payment circuit breaker closes and error_rate returns to ~0.6%.
- Retry or replay failed checkouts from the 15:23Z-revert window if the payment charges are idempotent-safe.

## Preventive Actions
- Require review and a canary for timeout changes on payment-facing clients; reject changes that drop timeouts by more than 50% without a load test.
- Add config validation bounds for payment_client.timeout_ms relative to payment-service p99 latency plus margin.

## Monitoring Recommendations
- Alert on order-service PaymentClient timeout rate > 2% and on the payment circuit breaker opening.
- Alert on config changes to timeout keys in order-service.
- Track order->payment client-side latency histograms, not only server-side payment latency.

## Evidence Gaps
- none recorded

## Limitations
- Server-side payment metrics cannot fully explain a ~30% client timeout rate at a 300 ms threshold; the magnitude needs client-side traces to confirm.
- Payment-service request_rate dropped ~14% from 15:37Z; cause unknown but likely downstream of order-service failures.
- [agent-reported gap] No client-side latency histograms for order->payment calls
- [agent-reported gap] Rollout scope of the config change across order-service instances not confirmed
- [agent-reported gap] No historical incident search performed
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: agent submitted

## Final Status
`ROOT_CAUSE_IDENTIFIED`

The checkout outage is best explained by the 15:22Z order-service config change that cut payment_client.timeout_ms from 3000 to 300 ms. The timing matches onset within about one minute, the log messages name the 300 ms timeout, and payment-service shows no internal regression. Revert the timeout to restore checkout.

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
  "evidence_records": 44,
  "duration_s": 18.73,
  "tokens": {
    "input_tokens": 8,
    "output_tokens": 4473,
    "cache_read_tokens": 18278,
    "cache_write_tokens": 8148,
    "llm_calls": 3,
    "cost_usd": 0.00343858
  },
  "tokens_by_agent": {
    "single_agent": {
      "input_tokens": 8,
      "output_tokens": 4473,
      "cache_read_tokens": 18278,
      "cache_write_tokens": 8148,
      "llm_calls": 3,
      "cost_usd": 0.00343858
    }
  }
}
```
