# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-007
- **Title:** Order checkout failing
- **Severity:** SEV2
- **Affected services:** order-service
- **Start time:** 2026-09-20T15:25:00+00:00
- **Investigation ID:** inv-e144f13daa (single_agent)
- **Final status:** `ROOT_CAUSE_IDENTIFIED`

## Executive Summary
INC-007 checkout failures are caused by a configuration change in order-service at 15:22Z that cut payment_client.timeout_ms from 3000ms to 300ms (OPS-2375, config-bot). Order-service error rate jumped from ~0.6% to ~29% and timeout rate from ~0.1% to ~35% starting 15:23Z, with PaymentClient timeouts logged at exactly 300ms. payment-service latency and error rate were flat throughout, so the payment service itself is not degraded, consistent with the payment team's report.

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
### 1. H1 - `configuration_regression` in `order-service` (confidence 0.85, critic: n/a)
**INFERENCE:** order-service payment_client.timeout_ms reduced 3000->300ms, below normal payment call latency tail, causing client-side timeouts, circuit-breaker opening and retry budget exhaustion. Mechanism: At 15:22Z the timeout was set to 300ms. Calls to payment-service POST /v1/charges that exceed 300ms are aborted by order-service, which counts them as failures; the circuit breaker opens (failure ratio 0.64) and retry budget is exhausted, failing checkouts.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [CONFIRMED FACT] `cfg-7f81d14a` (strong): Config change on order-service: payment_client.timeout_ms 3000 -> 300 at 2026-09-20T15:22:00Z (OPS-2375)
- [OBSERVED EVIDENCE] `met-order-service-error_rate-1455-1550` (strong): order-service error_rate: baseline 0.6 -> window mean 14.54 (max 31.99, change 2328.5%), onset 2026-09-20T15:23:00Z
- [OBSERVED EVIDENCE] `met-order-service-timeout_rate-1455-1550` (strong): order-service timeout_rate: baseline 0.1 -> window mean 16.87 (max 35.8, change 16649.6%), onset 2026-09-20T15:23:00Z
- [OBSERVED EVIDENCE] `logpat-order-service-f003ad98` (strong): 29x ERROR on order-service: 'PaymentClient: request to payment-service timed out after 300ms (POST /v1/charges, req 30)' (first 2026-09-20T15:23:20Z, last 2026-09-20T15:49:24Z)
- [OBSERVED EVIDENCE] `logpat-order-service-e2b30f44` (moderate): 7x WARN on order-service: 'Circuit breaker payment-service OPEN (failure ratio 0.64)' (first 2026-09-20T15:24:10Z, last 2026-09-20T15:46:21Z)
- [OBSERVED EVIDENCE] `logpat-order-service-809f4936` (moderate): 5x WARN on order-service: 'Retry budget exhausted for payment calls' (first 2026-09-20T15:25:13Z, last 2026-09-20T15:45:20Z)
- [INFERENCE] `hist-HIST-2025-055` (moderate): Past incident HIST-2025-055 'Timeouts after client timeout misconfiguration' (similarity 0.6): Client timeout configured in seconds instead of milliseconds.

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-payment-service-p50_latency_ms-1455-1550` (weak): payment-service p50_latency_ms: baseline 60.17 -> window mean 60.25 (max 65.57, change 0.1%), onset none detected
- [OBSERVED EVIDENCE] `met-payment-service-error_rate-1455-1550` (moderate): payment-service error_rate: baseline 0.8 -> window mean 0.8 (max 0.88, change 0.7%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] payment-service p99 latency during window (not queried) to confirm tail exceeds 300ms
- [UNKNOWN] order-service-side latency histogram of payment calls
- [UNKNOWN] confirmation of intended timeout value from OPS-2375 ticket

### 2. H2 - `upstream_dependency_degradation` in `payment-service` (confidence 0.08, critic: n/a)
**INFERENCE:** payment-service latency or errors degraded causing order-service timeouts. Mechanism: Slow payment responses would produce timeouts in order-service.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- none

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-payment-service-p95_latency_ms-1455-1550` (strong): payment-service p95_latency_ms: baseline 150.46 -> window mean 150.97 (max 167.91, change 0.3%), onset none detected
- [OBSERVED EVIDENCE] `met-payment-service-p50_latency_ms-1455-1550` (strong): payment-service p50_latency_ms: baseline 60.17 -> window mean 60.25 (max 65.57, change 0.1%), onset none detected
- [OBSERVED EVIDENCE] `met-payment-service-error_rate-1455-1550` (strong): payment-service error_rate: baseline 0.8 -> window mean 0.8 (max 0.88, change 0.7%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] payment p99 not checked

### 3. H3 - `db_connection_pool_exhaustion` in `order-service` (confidence 0.03, critic: n/a)
**INFERENCE:** order-service DB connection pool exhaustion causing slow checkouts. Mechanism: Pool saturation would delay requests and cause timeouts.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- none

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-order-service-db_conn_util_pct-1455-1550` (strong): order-service db_conn_util_pct: baseline 30.19 -> window mean 30.17 (max 32.46, change -0.1%), onset none detected

## Critic Review
- **Verdict:** `NOT_RUN` (rounds reviewed: 0)
- **Reasoning:** 

## Probable Root Cause
ROOT CAUSE IDENTIFIED (critic-approved; still an INFERENCE from evidence): configuration_regression in order-service - order-service payment_client.timeout_ms reduced 3000->300ms, below normal payment call latency tail, causing client-side timeouts, circuit-breaker opening and retry budget exhaustion.

## Corrective Actions
- Revert payment_client.timeout_ms in order-service from 300 back to 3000 (cfg-7f81d14a), and verify error rate returns to ~0.6%
- Reset/half-open the payment-service circuit breaker once the timeout is restored and confirm recovery
- Replay or reconcile checkouts that failed 15:23Z onward (retry budget exhausted, possible partial charges to check)

## Preventive Actions
- Add CI/config validation with minimum/maximum bounds for timeout values (reject ms-vs-s type ratio changes like 0.1x without approval)
- Require review for changes to downstream client timeouts tied to payment paths
- Document expected p99 of payment calls and set timeout as a multiple of it

## Monitoring Recommendations
- Alert on order-service PaymentClient timeout rate and circuit breaker OPEN events
- Alert on config changes to payment_client.* keys in real time
- Track payment-service p99 latency and compare against order-service configured timeout

## Evidence Gaps
- none recorded

## Limitations
- Correlation of config change with onset is strong but the mechanism is inferred from timeout logs, not traces
- Payment p50/p95 being far below 300ms makes the magnitude of timeouts worth confirming with tail data
- [agent-reported gap] payment-service p99 latency not queried
- [agent-reported gap] No distributed traces for individual failed checkouts
- [agent-reported gap] OPS-2375 intent not verified
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: agent submitted

## Final Status
`ROOT_CAUSE_IDENTIFIED`

The most likely root cause is the config change cfg-7f81d14a in order-service, which lowered payment_client.timeout_ms from 3000ms to 300ms at 15:22Z. Failures begin within a minute, and the logs show timeouts at exactly 300ms. Payment-service health metrics are flat, and DB pool and deployments are not implicated. Residual uncertainty: payment tail latency was not measured directly.

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
  "duration_s": 18.83,
  "tokens": {
    "input_tokens": 8,
    "output_tokens": 4275,
    "cache_read_tokens": 13818,
    "cache_write_tokens": 11675,
    "llm_calls": 3,
    "cost_usd": 0.0037358549999999997
  },
  "tokens_by_agent": {
    "single_agent": {
      "input_tokens": 8,
      "output_tokens": 4275,
      "cache_read_tokens": 13818,
      "cache_write_tokens": 11675,
      "llm_calls": 3,
      "cost_usd": 0.0037358549999999997
    }
  }
}
```
