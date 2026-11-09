# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-010
- **Title:** Intermittent gateway latency
- **Severity:** SEV3
- **Affected services:** api-gateway
- **Start time:** 2026-09-29T19:45:00+00:00
- **Investigation ID:** inv-2c209c56be (single_agent)
- **Final status:** `INCONCLUSIVE`

## Executive Summary
INC-010 reports intermittent api-gateway latency. The only clear signal is a p99 rise (baseline ~253 ms to ~300 ms window mean; a single 5-minute sample peaked at ~557 ms at 19:45Z, onset ~19:40Z). p95, error rate, timeout rate, request rate and CPU are flat versus baseline. Telemetry is heavily incomplete after 19:45Z (24/56 datapoints missing for api-gateway, 36/56 for order-service), so the incident window cannot be fully assessed. No deployments or config changes were recorded in the window. A cluster of slow SELECT report_rollup() statements in postgres (13-18 s, 19:34-19:42Z) overlaps the p99 onset, but postgres p99, CPU, connection utilisation and disk IO wait show no change, so no causal link is established. Root cause is not identified.

## Incident Timeline
| Time (UTC) | Label | Event | Evidence |
|---|---|---|---|
| 2026-09-29T19:17:38Z | OBSERVED EVIDENCE | First log: 3x WARN on order-service: 'Inventory reservation retry for sku-31' (first 2026-09-29T19:17:38Z, last 2026-09-29T20:07:18Z) | logpat-order-service-95abd1bb |
| 2026-09-29T19:45:00Z | CONFIRMED FACT | Reported symptom start |  |
| 2026-09-29T19:51:00Z | CONFIRMED FACT | Incident reported |  |

## Observed Symptoms

## Investigation Performed

## Root-Cause Hypotheses (ranked by evidence strength)
### 1. H2 - `unknown` in `api-gateway` (confidence 0.30, critic: n/a)
**INFERENCE:** Transient noise in api-gateway p99 (single-sample spike with incomplete telemetry) with no real sustained degradation. Mechanism: The 557 ms reading is one 5-minute bucket, p95 moved only 4.6%, and error/timeout rates are unchanged; the spike may be a sampling artifact or brief burst.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `met-api-gateway-p95_latency_ms-1915-2010` (moderate): api-gateway p95_latency_ms: baseline 120.41 -> window mean 126.01 (max 151.58, change 4.6%), onset none detected, 24 points missing
- [OBSERVED EVIDENCE] `met-api-gateway-error_rate-1915-2010` (moderate): api-gateway error_rate: baseline 0.5 -> window mean 0.5 (max 0.53, change 0.3%), onset none detected, 24 points missing
- [OBSERVED EVIDENCE] `met-api-gateway-timeout_rate-1915-2010` (moderate): api-gateway timeout_rate: baseline 0.1 -> window mean 0.1 (max 0.1, change -0.2%), onset none detected, 24 points missing

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-api-gateway-p99_latency_ms-1915-2010` (weak): api-gateway p99_latency_ms: baseline 252.9 -> window mean 299.56 (max 556.96, change 18.5%), onset 2026-09-29T19:40:00Z, 24 points missing

Remaining uncertainties / missing evidence:
- [UNKNOWN] Post-19:50Z telemetry (mostly missing)

### 2. H1 - `unknown` in `postgres` (confidence 0.25, critic: n/a)
**INFERENCE:** Transient tail-latency from slow postgres report_rollup() executions (possibly a scheduled batch) affecting a subset of gateway requests via a shared dependency path. Mechanism: Long-running report queries may hold locks or consume shared resources, delaying upstream calls and inflating p99 without moving p95 or error rates.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-postgres-44883ca5` (moderate): 2x WARN on postgres: 'duration: 17802 ms statement: SELECT report_rollup()' (first 2026-09-29T19:34:08Z, last 2026-09-29T19:42:06Z)
- [OBSERVED EVIDENCE] `met-api-gateway-p99_latency_ms-1915-2010` (weak): api-gateway p99_latency_ms: baseline 252.9 -> window mean 299.56 (max 556.96, change 18.5%), onset 2026-09-29T19:40:00Z, 24 points missing

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-postgres-p99_latency_ms-1915-2010` (moderate): postgres p99_latency_ms: baseline 25.14 -> window mean 24.94 (max 26.4, change -0.8%), onset none detected
- [OBSERVED EVIDENCE] `met-postgres-cpu_pct-1915-2010` (moderate): postgres cpu_pct: baseline 35.19 -> window mean 35.1 (max 39.16, change -0.3%), onset none detected
- [OBSERVED EVIDENCE] `met-postgres-disk_io_wait_ms-1915-2010` (weak): postgres disk_io_wait_ms: baseline 1.99 -> window mean 2.0 (max 2.17, change 0.6%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Whether api-gateway routes requests through report_rollup-affected paths
- [UNKNOWN] Trace-level latency breakdown for slow requests

### 3. H3 - `upstream_dependency_degradation` in `order-service` (confidence 0.15, critic: n/a)
**INFERENCE:** Intermittent slowness in an upstream dependency of api-gateway (order-service, payment-service, auth-service) not visible in the available data. Mechanism: Order-service inventory retries and payment card soft-declines and auth rate-limit warnings could add tail latency to some gateway requests.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-order-service-95abd1bb` (weak): 3x WARN on order-service: 'Inventory reservation retry for sku-31' (first 2026-09-29T19:17:38Z, last 2026-09-29T20:07:18Z)
- [OBSERVED EVIDENCE] `logpat-payment-service-7e9bf84f` (weak): 2x WARN on payment-service: 'Card network soft decline (code 05) for charge ch_63' (first 2026-09-29T19:45:54Z, last 2026-09-29T19:55:10Z)

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-order-service-p99_latency_ms-1915-2010` (moderate): order-service p99_latency_ms: baseline 398.55 -> window mean 394.55 (max 415.95, change -1.0%), onset none detected, 36 points missing

Remaining uncertainties / missing evidence:
- [UNKNOWN] Payment-service and auth-service latency metrics (not queried)
- [UNKNOWN] order-service telemetry after 19:30Z

## Critic Review
- **Verdict:** `NOT_RUN` (rounds reviewed: 0)
- **Reasoning:** 

## Probable Root Cause
Root cause could not be conclusively established with the available evidence.

## Corrective Actions
- No corrective action can be justified yet; re-evaluate after telemetry backfills and traces are reviewed.

## Preventive Actions
- Add reliable telemetry coverage for api-gateway and order-service so gaps don't hide incidents.
- Review long-running report_rollup() schedule and add statement timeouts or move it off the hot path.

## Monitoring Recommendations
- Alert on api-gateway p99 sustained above baseline (e.g. >1.2x for 10 min), not single samples.
- Track postgres slow-statement count and report_rollup duration.
- Monitor telemetry completeness (datapoint-missing rate) per service.

## Evidence Gaps
- [UNKNOWN] query_logs returned incomplete data for all (PARTIAL_DATA)
- [UNKNOWN] query_logs returned incomplete data for service=api-gateway (PARTIAL_DATA)

## Limitations
- Over 40% of api-gateway and order-service datapoints missing in the window; log results also flagged as incomplete.
- Payment-service, auth-service and user-service latency metrics were not queried.
- Single 5-minute p99 sample drives the peak; sustained impact is unclear.
- Historical incident matches had low similarity (0.14-0.16) and are analogies only.
- [agent-reported gap] Telemetry after 19:45Z for api-gateway, order-service (missing datapoints).
- [agent-reported gap] No distributed traces or per-route latency breakdown.
- [agent-reported gap] Latency metrics for payment-service and auth-service not checked.
- 0 tool calls failed and 2 returned partial data; affected areas are treated as unknown, not healthy.
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: agent submitted

## Final Status
`INCONCLUSIVE`

Root cause could not be conclusively established with the available evidence. Evidence shows a modest, possibly transient api-gateway p99 increase (onset ~19:40Z) with flat p95, errors, timeouts, CPU and request rate. No deployments or config changes were recorded. Telemetry after ~19:45Z is largely missing for key services, which prevents confirming or excluding a cause. Postgres slow report_rollup() queries overlap in time but show no resource impact. Final status is INCONCLUSIVE; further trace and telemetry review is required.

## Execution Statistics
```json
{
  "rounds": 1,
  "tool_calls": 9,
  "tool_failures": 0,
  "tool_retries": 0,
  "partial_results": 2,
  "agent_failures": 0,
  "agent_retries": 0,
  "invalid_llm_outputs": 0,
  "messages_exchanged": 0,
  "evidence_records": 38,
  "duration_s": 20.59,
  "tokens": {
    "input_tokens": 10,
    "output_tokens": 4594,
    "cache_read_tokens": 26855,
    "cache_write_tokens": 13917,
    "llm_calls": 4,
    "cost_usd": 0.004306175000000001
  },
  "tokens_by_agent": {
    "single_agent": {
      "input_tokens": 10,
      "output_tokens": 4594,
      "cache_read_tokens": 26855,
      "cache_write_tokens": 13917,
      "llm_calls": 4,
      "cost_usd": 0.004306175000000001
    }
  }
}
```
