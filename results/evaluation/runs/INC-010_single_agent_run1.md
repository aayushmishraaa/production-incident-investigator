# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-010
- **Title:** Intermittent gateway latency
- **Severity:** SEV3
- **Affected services:** api-gateway
- **Start time:** 2026-09-29T19:45:00+00:00
- **Investigation ID:** inv-8820f10b69 (single_agent)
- **Final status:** `INCONCLUSIVE`

## Executive Summary
api-gateway P99 rose about 18.5% (baseline mean 252.9 ms to 299.6 ms), with a single-bucket spike to about 557 ms at 19:45. P95, error rate, timeout rate, request rate and CPU were flat versus baseline. No deployments or config changes were recorded in the window. Upstream services (auth, payment, order) show no latency, error or timeout change in their available data. Telemetry is badly incomplete after about 19:45 for most services, so recovery and the later window cannot be assessed. The evidence does not identify a root cause.

## Incident Timeline
| Time (UTC) | Label | Event | Evidence |
|---|---|---|---|
| 2026-09-29T19:45:00Z | CONFIRMED FACT | Reported symptom start |  |
| 2026-09-29T19:51:00Z | CONFIRMED FACT | Incident reported |  |

## Observed Symptoms

## Investigation Performed

## Root-Cause Hypotheses (ranked by evidence strength)
### 1. H3 - `unknown` in `None` (confidence 0.30, critic: n/a)
**INFERENCE:** Telemetry gap or transient noise: the observed P99 rise may be within normal variance, and the only spike is one 5-minute bucket. Mechanism: The gateway P99 rise is 18.5% on a 56-point window with 24 missing points. The spike at 19:45 is a single bucket and is not followed by data, so it cannot be confirmed as sustained.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `met-api-gateway-p99_latency_ms-1915-2010` (moderate): api-gateway p99_latency_ms: baseline 252.9 -> window mean 299.56 (max 556.96, change 18.5%), onset 2026-09-29T19:40:00Z, 24 points missing

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-api-gateway-p95_latency_ms-1915-2010` (moderate): api-gateway p95_latency_ms: baseline 120.41 -> window mean 126.01 (max 151.58, change 4.6%), onset none detected, 24 points missing

Remaining uncertainties / missing evidence:
- [UNKNOWN] Gateway telemetry after 19:45

### 2. H1 - `infrastructure_degradation` in `postgres` (confidence 0.20, critic: n/a)
**INFERENCE:** Transient database slowness (a single long-running report_rollup query on postgres) briefly delayed requests that depend on the database, producing the P99 spike. Mechanism: A report_rollup statement took 11.7 s at 19:30:27, shortly before the gateway P99 onset at 19:40. A long-running query could hold locks or resources and add tail latency. However, postgres CPU, connection utilisation, disk IO wait and p95 were all flat, and the gateway P99 rise is small.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-postgres-44883ca5` (weak): 1x WARN on postgres: 'duration: 11702 ms statement: SELECT report_rollup()' (first 2026-09-29T19:30:27Z, last 2026-09-29T19:30:27Z)
- [OBSERVED EVIDENCE] `met-api-gateway-p99_latency_ms-1915-2010` (weak): api-gateway p99_latency_ms: baseline 252.9 -> window mean 299.56 (max 556.96, change 18.5%), onset 2026-09-29T19:40:00Z, 24 points missing

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-postgres-db_conn_util_pct-1915-2010` (moderate): postgres db_conn_util_pct: baseline 40.12 -> window mean 39.73 (max 43.8, change -1.0%), onset none detected
- [OBSERVED EVIDENCE] `met-postgres-disk_io_wait_ms-1915-2010` (moderate): postgres disk_io_wait_ms: baseline 1.99 -> window mean 2.0 (max 2.17, change 0.6%), onset none detected
- [OBSERVED EVIDENCE] `met-postgres-p95_latency_ms-1915-2010` (moderate): postgres p95_latency_ms: baseline 12.04 -> window mean 12.03 (max 13.21, change -0.0%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Postgres slow-query log for 19:30-19:50 beyond one entry
- [UNKNOWN] Gateway per-route latency breakdown

### 3. H2 - `traffic_surge` in `api-gateway` (confidence 0.10, critic: n/a)
**INFERENCE:** Large or slow client uploads consumed gateway resources and produced tail latency for some requests. Mechanism: Slow client uploads of about 1.9 MB were logged at 19:37 and 19:48. Slow uploads can hold connections and workers, which increases P99 for other requests.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-api-gateway-88b04940` (weak): 2x WARN on api-gateway: 'Slow client upload from 10.4.82.12 (1.9MB)' (first 2026-09-29T19:37:24Z, last 2026-09-29T19:48:39Z)

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-api-gateway-request_rate-1915-2010` (moderate): api-gateway request_rate: baseline 1219.56 -> window mean 1200.06 (max 1323.96, change -1.6%), onset none detected, 24 points missing
- [OBSERVED EVIDENCE] `met-api-gateway-cpu_pct-1915-2010` (moderate): api-gateway cpu_pct: baseline 34.72 -> window mean 34.67 (max 37.46, change -0.2%), onset none detected, 24 points missing

Remaining uncertainties / missing evidence:
- [UNKNOWN] Gateway connection/worker pool metrics
- [UNKNOWN] Upload size distribution over time

## Critic Review
- **Verdict:** `NOT_RUN` (rounds reviewed: 0)
- **Reasoning:** 

## Probable Root Cause
Root cause could not be conclusively established with the available evidence.

## Corrective Actions
- No corrective action is justified yet; continue monitoring and gather the missing telemetry.

## Preventive Actions
- Add per-route and per-client latency breakdown to gateway dashboards to make intermittent tail latency diagnosable.
- Investigate telemetry pipeline gaps (24-36 missing datapoints per service after 19:45).

## Monitoring Recommendations
- Alert on api-gateway P99 sustained above 350 ms over 10 minutes.
- Track postgres statement duration for report_rollup and similar long queries.
- Monitor gateway worker/connection pool saturation and slow-upload counts.

## Evidence Gaps
- [UNKNOWN] query_logs returned incomplete data for all (PARTIAL_DATA)
- [UNKNOWN] query_logs returned incomplete data for service=api-gateway (PARTIAL_DATA)

## Limitations
- Telemetry gaps limit the ability to see the full incident window.
- Historical matches have low similarity (0.14-0.17) and are analogies only.
- Tool-call budget was not exhausted, but further queries would not fill the telemetry gaps.
- [agent-reported gap] Gateway metrics missing for 24 of 56 datapoints (most after 19:45); the window after the spike is unassessable.
- [agent-reported gap] Upstream service metrics missing for 36 of 56 datapoints after about 19:35.
- [agent-reported gap] Log query results were flagged as incomplete, so absence of logs is not evidence of absence.
- [agent-reported gap] No per-route or per-client latency breakdown was available.
- 0 tool calls failed and 2 returned partial data; affected areas are treated as unknown, not healthy.
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: agent submitted

## Final Status
`INCONCLUSIVE`

Root cause could not be conclusively established with the available evidence. No root cause can be confirmed. The gateway P99 movement is small and short-lived in the available data. Several candidates were checked and none is supported: no deployments or config changes, no upstream latency change, no postgres resource stress, and no error or timeout increase. Gateway and most upstream telemetry is missing after about 19:45, so the later window and any recovery cannot be assessed. The 19:30 slow report_rollup query and the slow client uploads are noted as weak leads only.

## Execution Statistics
```json
{
  "rounds": 1,
  "tool_calls": 11,
  "tool_failures": 0,
  "tool_retries": 0,
  "partial_results": 2,
  "agent_failures": 0,
  "agent_retries": 0,
  "invalid_llm_outputs": 1,
  "messages_exchanged": 0,
  "evidence_records": 35,
  "duration_s": 28.62,
  "tokens": {
    "input_tokens": 12,
    "output_tokens": 7324,
    "cache_read_tokens": 45432,
    "cache_write_tokens": 13520,
    "llm_calls": 5,
    "cost_usd": 0.00580752
  },
  "tokens_by_agent": {
    "single_agent": {
      "input_tokens": 12,
      "output_tokens": 7324,
      "cache_read_tokens": 45432,
      "cache_write_tokens": 13520,
      "llm_calls": 5,
      "cost_usd": 0.00580752
    }
  }
}
```
