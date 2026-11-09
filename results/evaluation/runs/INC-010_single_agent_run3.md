# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-010
- **Title:** Intermittent gateway latency
- **Severity:** SEV3
- **Affected services:** api-gateway
- **Start time:** 2026-09-29T19:45:00+00:00
- **Investigation ID:** inv-0694d90ce6 (single_agent)
- **Final status:** `INCONCLUSIVE`

## Executive Summary
api-gateway P99 latency rose about 18.5% (baseline mean 252.9 ms to 299.6 ms) with onset around 19:40Z and a peak of 557 ms at 19:45Z, consistent with the reported T0 of 19:45Z. The rise is small, p95, error rate, timeout rate, request rate and CPU were flat, and no deployments or config changes occurred in the 18:00-20:10Z window. Over half of the gateway and downstream telemetry is missing after about 19:35-19:50Z, so the cause cannot be confirmed. The most notable signal is a recurring slow statement SELECT report_rollup() on postgres (11.7 s at 19:30Z, 15.8 s at 19:40Z, 14.5 s at 20:03Z). Its timing is suggestive but not proven to affect gateway latency, and postgres's own metrics show no change.

## Incident Timeline
| Time (UTC) | Label | Event | Evidence |
|---|---|---|---|
| 2026-09-29T19:45:00Z | CONFIRMED FACT | Reported symptom start |  |
| 2026-09-29T19:51:00Z | CONFIRMED FACT | Incident reported |  |

## Observed Symptoms

## Investigation Performed

## Root-Cause Hypotheses (ranked by evidence strength)
### 1. H1 - `db_connection_pool_exhaustion` in `postgres` (confidence 0.30, critic: n/a)
**INFERENCE:** Long-running report_rollup() queries on postgres hold resources/connections and slow requests that traverse the gateway's upstream services (order/auth/payment/user), raising gateway P99. Mechanism: Periodic heavy report job executes for 11-16 s; if it contends with OLTP queries or holds locks/connections, requests waiting on DB calls see elevated tail latency, showing up as gateway P99 spikes at 19:40-19:45Z.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-postgres-44883ca5` (moderate): 2x WARN on postgres: 'duration: 15802 ms statement: SELECT report_rollup()' (first 2026-09-29T19:40:44Z, last 2026-09-29T20:03:45Z)
- [OBSERVED EVIDENCE] `log-87888189` (weak): WARN postgres: duration: 11702 ms statement: SELECT report_rollup()
- [OBSERVED EVIDENCE] `log-13313f6d` (weak): WARN postgres: duration: 15802 ms statement: SELECT report_rollup()
- [OBSERVED EVIDENCE] `met-api-gateway-p99_latency_ms-1915-2010` (moderate): api-gateway p99_latency_ms: baseline 252.9 -> window mean 299.56 (max 556.96, change 18.5%), onset 2026-09-29T19:40:00Z, 24 points missing

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-postgres-db_conn_util_pct-1915-2010` (moderate): postgres db_conn_util_pct: baseline 40.12 -> window mean 39.73 (max 43.8, change -1.0%), onset none detected
- [OBSERVED EVIDENCE] `met-postgres-p99_latency_ms-1915-2010` (moderate): postgres p99_latency_ms: baseline 25.14 -> window mean 24.94 (max 26.4, change -0.8%), onset none detected
- [OBSERVED EVIDENCE] `met-postgres-cpu_pct-1915-2010` (weak): postgres cpu_pct: baseline 35.19 -> window mean 35.1 (max 39.16, change -0.3%), onset none detected
- [OBSERVED EVIDENCE] `met-order-service-p99_latency_ms-1915-2010` (weak): order-service p99_latency_ms: baseline 398.55 -> window mean 394.55 (max 415.95, change -1.0%), onset none detected, 36 points missing

Remaining uncertainties / missing evidence:
- [UNKNOWN] Gateway-to-upstream span or trace data for the 19:40-19:50Z window.
- [UNKNOWN] Whether report_rollup() shares locks or connections with the request path.
- [UNKNOWN] Telemetry for postgres and upstream services after 19:35Z (about 36 of 56 datapoints missing).

### 2. H3 - `unknown` in `None` (confidence 0.20, critic: n/a)
**INFERENCE:** Transient or ingestion-related effect: the gateway P99 bump may be partly a measurement artifact, given the telemetry gaps and the small magnitude. Mechanism: Telemetry delivery was delayed or incomplete after 19:35-19:50Z, so the P99 spike may reflect sparse sampling rather than a real, sustained degradation.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `met-api-gateway-p99_latency_ms-1915-2010` (weak): api-gateway p99_latency_ms: baseline 252.9 -> window mean 299.56 (max 556.96, change 18.5%), onset 2026-09-29T19:40:00Z, 24 points missing

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-api-gateway-p95_latency_ms-1915-2010` (weak): api-gateway p95_latency_ms: baseline 120.41 -> window mean 126.01 (max 151.58, change 4.6%), onset none detected, 24 points missing

Remaining uncertainties / missing evidence:
- [UNKNOWN] Raw request-level latency logs for the gateway.

### 3. H2 - `traffic_surge` in `api-gateway` (confidence 0.15, critic: n/a)
**INFERENCE:** A client-side issue (large or slow uploads, or retries) occupies gateway worker capacity and inflates tail latency. Mechanism: Slow large-body uploads hold gateway connections, increasing tail latency for other requests.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-api-gateway-88b04940` (weak): 2x WARN on api-gateway: 'Slow client upload from 10.4.53.12 (1.9MB)' (first 2026-09-29T19:57:04Z, last 2026-09-29T20:01:21Z)
- [INFERENCE] `hist-HIST-2025-068` (weak): Past incident HIST-2025-068 'Retry storm from mobile client' (similarity 0.139): Mobile release ignored Retry-After causing retry storm.

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-api-gateway-request_rate-1915-2010` (moderate): api-gateway request_rate: baseline 1219.56 -> window mean 1200.06 (max 1323.96, change -1.6%), onset none detected, 24 points missing
- [OBSERVED EVIDENCE] `met-api-gateway-cpu_pct-1915-2010` (moderate): api-gateway cpu_pct: baseline 34.72 -> window mean 34.67 (max 37.46, change -0.2%), onset none detected, 24 points missing
- [OBSERVED EVIDENCE] `met-api-gateway-p95_latency_ms-1915-2010` (moderate): api-gateway p95_latency_ms: baseline 120.41 -> window mean 126.01 (max 151.58, change 4.6%), onset none detected, 24 points missing

Remaining uncertainties / missing evidence:
- [UNKNOWN] Gateway connection/worker-pool metrics.
- [UNKNOWN] Client-level breakdown of request sizes and retries.

## Critic Review
- **Verdict:** `NOT_RUN` (rounds reviewed: 0)
- **Reasoning:** 

## Probable Root Cause
Root cause could not be conclusively established with the available evidence.

## Corrective Actions
- Pull request-level traces for api-gateway between 19:35Z and 19:50Z to attribute the tail latency to a specific upstream call.
- Review the report_rollup() schedule and, if it is confirmed to interfere, move it off the peak path or add a statement timeout.

## Preventive Actions
- Add alerting on gateway P99 with a deviation threshold, so tail regressions are detected even when the average stays flat.
- Fix telemetry pipeline gaps so that per-service metrics are complete during incidents.

## Monitoring Recommendations
- Track postgres slow-statement duration for report_rollup() and alert above 5 s.
- Track gateway P99 and P99 per upstream dependency, plus gateway connection-pool utilisation.
- Monitor telemetry completeness (datapoint availability) per service.

## Evidence Gaps
- [UNKNOWN] query_logs returned incomplete data for all (PARTIAL_DATA)
- [UNKNOWN] query_logs returned incomplete data for service=api-gateway (PARTIAL_DATA)
- [UNKNOWN] query_logs returned incomplete data for service=postgres, keyword=report_rollup (PARTIAL_DATA)

## Limitations
- Tool budget was partly used; the investigation was not exhaustive.
- Historical incident matches have low similarity (0.14-0.16) and are analogies only.
- [agent-reported gap] About 24 of 56 gateway datapoints and 36 of 56 upstream datapoints are missing after 19:35-19:50Z.
- [agent-reported gap] No trace or span data linking gateway requests to upstream calls.
- [agent-reported gap] Log search results are flagged as incomplete, so absence of errors cannot be concluded.
- [agent-reported gap] No gateway connection-pool or worker-saturation metrics were available.
- 0 tool calls failed and 3 returned partial data; affected areas are treated as unknown, not healthy.
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: agent submitted

## Final Status
`INCONCLUSIVE`

Root cause could not be conclusively established with the available evidence. The evidence does not establish a root cause for the intermittent gateway P99 increase. The rise is modest and confined to the tail (p95 and error rates are flat), with no deployments or config changes. Heavy telemetry gaps weaken all conclusions after about 19:35-19:50Z. The recurring slow report_rollup() statements on postgres are the most promising lead but are not supported by postgres's own latency or connection metrics. Status is INCONCLUSIVE.

## Execution Statistics
```json
{
  "rounds": 1,
  "tool_calls": 13,
  "tool_failures": 0,
  "tool_retries": 0,
  "partial_results": 3,
  "agent_failures": 0,
  "agent_retries": 0,
  "invalid_llm_outputs": 0,
  "messages_exchanged": 0,
  "evidence_records": 41,
  "duration_s": 25.17,
  "tokens": {
    "input_tokens": 10,
    "output_tokens": 6129,
    "cache_read_tokens": 31869,
    "cache_write_tokens": 13068,
    "llm_calls": 4,
    "cost_usd": 0.00501769
  },
  "tokens_by_agent": {
    "single_agent": {
      "input_tokens": 10,
      "output_tokens": 6129,
      "cache_read_tokens": 31869,
      "cache_write_tokens": 13068,
      "llm_calls": 4,
      "cost_usd": 0.00501769
    }
  }
}
```
