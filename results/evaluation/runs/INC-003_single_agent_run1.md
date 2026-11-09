# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-003
- **Title:** Payment service slow responses
- **Severity:** SEV2
- **Affected services:** payment-service
- **Start time:** 2026-09-08T18:10:00+00:00
- **Investigation ID:** inv-79344b24f4 (single_agent)
- **Final status:** `PROBABLE_ROOT_CAUSE`

## Executive Summary
Payment-service p99 latency rose from ~300ms to ~1.7s mean (peak 3.6s) starting ~18:09-18:10Z. The latency is inherited: payment-service calls to auth-service /v1/token/verify slowed first, and payment timeouts to auth-service (3000ms) followed. auth-service degraded starting ~18:07Z (p99 90ms to ~2s, error rate 0.3% to 1.5%, CPU 30% to 39%, request queue time up to 9.7s), and its logs show slow JWKS refreshes from the identity-provider starting 18:06Z. Payment's own DB, CPU, and error rate are flat, so the payment pods are not the source. The most likely cause is upstream degradation of the identity-provider/JWKS path inside auth-service, but no identity-provider telemetry is available to confirm it.

## Incident Timeline
| Time (UTC) | Label | Event | Evidence |
|---|---|---|---|
| 2026-09-08T17:35:00Z | CONFIRMED FACT | Config change on payment-service: log.level INFO -> DEBUG at 2026-09-08T17:35:00Z (OPS-2898) | cfg-5c71fbd0 |
| 2026-09-08T17:40:49Z | OBSERVED EVIDENCE | First log: 6x WARN on auth-service: 'Login rate limit hit for user id u-37' (first 2026-09-08T17:40:49Z, last 2026-09-08T18:16:34Z) | logpat-auth-service-cc8d3b87 |
| 2026-09-08T18:06:12Z | OBSERVED EVIDENCE | First log: 11x WARN on auth-service: 'Slow JWKS refresh from identity-provider: 480 ms' (first 2026-09-08T18:06:12Z, last 2026-09-08T18:32:23Z) | logpat-auth-service-171612d3 |
| 2026-09-08T18:07:00Z | OBSERVED EVIDENCE | Anomaly onset: auth-service p99_latency_ms: baseline 90.36 -> window mean 1981.57 (max 4228.52, change 2092.9%), onset 2026-09-08T18:07:00Z | met-auth-service-p99_latency_ms-1740-1835 |
| 2026-09-08T18:07:11Z | OBSERVED EVIDENCE | First log: 9x WARN on auth-service: 'Request queue time high for /v1/token/verify: 9700ms' (first 2026-09-08T18:07:11Z, last 2026-09-08T18:31:56Z) | logpat-auth-service-9246cbf2 |
| 2026-09-08T18:08:00Z | OBSERVED EVIDENCE | Anomaly onset: auth-service error_rate: baseline 0.3 -> window mean 1.55 (max 3.29, change 416.1%), onset 2026-09-08T18:08:00Z | met-auth-service-error_rate-1740-1835 |
| 2026-09-08T18:09:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service p99_latency_ms: baseline 300.58 -> window mean 1703.85 (max 3577.47, change 466.8%), onset 2026-09-08T18:09:00Z | met-payment-service-p99_latency_ms-1740-1835 |
| 2026-09-08T18:09:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service p95_latency_ms: baseline 149.75 -> window mean 1290.1 (max 2845.09, change 761.5%), onset 2026-09-08T18:09:00Z | met-payment-service-p95_latency_ms-1740-1835 |
| 2026-09-08T18:09:13Z | OBSERVED EVIDENCE | First log: 19x WARN on payment-service: 'Call to auth-service /v1/token/verify took 2550ms' (first 2026-09-08T18:09:13Z, last 2026-09-08T18:33:42Z) | logpat-payment-service-4cb3914c |
| 2026-09-08T18:10:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service timeout_rate: baseline 0.1 -> window mean 2.68 (max 6.26, change 2564.7%), onset 2026-09-08T18:10:00Z | met-payment-service-timeout_rate-1740-1835 |
| 2026-09-08T18:10:00Z | CONFIRMED FACT | Reported symptom start |  |
| 2026-09-08T18:10:19Z | OBSERVED EVIDENCE | First log: 8x ERROR on payment-service: 'Upstream timeout calling auth-service after 3000ms (charge ch_15)' (first 2026-09-08T18:10:19Z, last 2026-09-08T18:31:52Z) | logpat-payment-service-4672e5cc |
| 2026-09-08T18:16:00Z | CONFIRMED FACT | Incident reported |  |

## Observed Symptoms
- **OBSERVED EVIDENCE:** payment-service p99_latency_ms: baseline 300.58 -> window mean 1703.85 (max 3577.47, change 466.8%), onset 2026-09-08T18:09:00Z (met-payment-service-p99_latency_ms-1740-1835)
- **OBSERVED EVIDENCE:** payment-service p95_latency_ms: baseline 149.75 -> window mean 1290.1 (max 2845.09, change 761.5%), onset 2026-09-08T18:09:00Z (met-payment-service-p95_latency_ms-1740-1835)
- **OBSERVED EVIDENCE:** payment-service timeout_rate: baseline 0.1 -> window mean 2.68 (max 6.26, change 2564.7%), onset 2026-09-08T18:10:00Z (met-payment-service-timeout_rate-1740-1835)
- **OBSERVED EVIDENCE:** auth-service p99_latency_ms: baseline 90.36 -> window mean 1981.57 (max 4228.52, change 2092.9%), onset 2026-09-08T18:07:00Z (met-auth-service-p99_latency_ms-1740-1835)
- **OBSERVED EVIDENCE:** auth-service error_rate: baseline 0.3 -> window mean 1.55 (max 3.29, change 416.1%), onset 2026-09-08T18:08:00Z (met-auth-service-error_rate-1740-1835)

## Investigation Performed

## Root-Cause Hypotheses (ranked by evidence strength)
### 1. H1 - `upstream_dependency_degradation` in `auth-service` (confidence 0.60, critic: n/a)
**INFERENCE:** Slow identity-provider JWKS refresh (external dependency) degrades auth-service token verification, which queues requests and causes payment-service timeouts. Mechanism: Slow JWKS fetches from identity-provider (120-980ms, rising from 18:06Z) hold auth-service request threads; /v1/token/verify queue time grows (2-9.7s), auth p99 rises from ~90ms to ~2-4s and CPU climbs; payment-service calls to auth time out at 3000ms and its p99 follows about 2-3 minutes later. The causal ordering (auth onset 18:07 before payment onset 18:09-18:10) matches.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-auth-service-171612d3` (strong): 11x WARN on auth-service: 'Slow JWKS refresh from identity-provider: 480 ms' (first 2026-09-08T18:06:12Z, last 2026-09-08T18:32:23Z)
- [OBSERVED EVIDENCE] `met-auth-service-p99_latency_ms-1740-1835` (strong): auth-service p99_latency_ms: baseline 90.36 -> window mean 1981.57 (max 4228.52, change 2092.9%), onset 2026-09-08T18:07:00Z
- [OBSERVED EVIDENCE] `logpat-auth-service-9246cbf2` (strong): 9x WARN on auth-service: 'Request queue time high for /v1/token/verify: 9700ms' (first 2026-09-08T18:07:11Z, last 2026-09-08T18:31:56Z)
- [OBSERVED EVIDENCE] `met-auth-service-error_rate-1740-1835` (moderate): auth-service error_rate: baseline 0.3 -> window mean 1.55 (max 3.29, change 416.1%), onset 2026-09-08T18:08:00Z
- [OBSERVED EVIDENCE] `met-auth-service-cpu_pct-1740-1835` (moderate): auth-service cpu_pct: baseline 30.04 -> window mean 38.64 (max 52.26, change 28.6%), onset 2026-09-08T18:10:00Z
- [OBSERVED EVIDENCE] `logpat-payment-service-4cb3914c` (strong): 19x WARN on payment-service: 'Call to auth-service /v1/token/verify took 2550ms' (first 2026-09-08T18:09:13Z, last 2026-09-08T18:33:42Z)
- [OBSERVED EVIDENCE] `logpat-payment-service-4672e5cc` (strong): 8x ERROR on payment-service: 'Upstream timeout calling auth-service after 3000ms (charge ch_15)' (first 2026-09-08T18:10:19Z, last 2026-09-08T18:31:52Z)
- [OBSERVED EVIDENCE] `met-payment-service-p99_latency_ms-1740-1835` (strong): payment-service p99_latency_ms: baseline 300.58 -> window mean 1703.85 (max 3577.47, change 466.8%), onset 2026-09-08T18:09:00Z
- [OBSERVED EVIDENCE] `met-payment-service-timeout_rate-1740-1835` (strong): payment-service timeout_rate: baseline 0.1 -> window mean 2.68 (max 6.26, change 2564.7%), onset 2026-09-08T18:10:00Z
- [INFERENCE] `hist-HIST-2025-031` (weak): Past incident HIST-2025-031 'Checkout slow due to slow identity calls' (similarity 0.456): auth-service degraded by slow identity-provider JWKS refresh.

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-auth-service-request_rate-1740-1835` (moderate): auth-service request_rate: baseline 894.11 -> window mean 903.07 (max 1015.2, change 1.0%), onset none detected
- [OBSERVED EVIDENCE] `met-auth-service-db_conn_util_pct-1740-1835` (weak): auth-service db_conn_util_pct: baseline 30.29 -> window mean 30.2 (max 33.16, change -0.3%), onset none detected
- [OBSERVED EVIDENCE] `met-auth-service-timeout_rate-1740-1835` (weak): auth-service timeout_rate: baseline 0.05 -> window mean 0.05 (max 0.06, change -0.3%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] identity-provider latency or availability metrics (no telemetry was available for it)
- [UNKNOWN] auth-service JWKS fetch timeout settings and thread-pool/queue metrics
- [UNKNOWN] explanation of why auth CPU rose 28% without a request-rate change

### 2. H2 - `configuration_regression` in `payment-service` (confidence 0.10, critic: n/a)
**INFERENCE:** A logging configuration change in payment-service (log.level INFO to DEBUG at 17:35Z) increased logging overhead and contributed to payment slowness. Mechanism: DEBUG logging raises per-request CPU and I/O, slowing payment-service handling. However, the change preceded the latency onset by about 35 minutes with no change in payment metrics during the gap.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [CONFIRMED FACT] `cfg-5c71fbd0` (moderate): Config change on payment-service: log.level INFO -> DEBUG at 2026-09-08T17:35:00Z (OPS-2898)

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-payment-service-cpu_pct-1740-1835` (strong): payment-service cpu_pct: baseline 40.41 -> window mean 40.36 (max 43.59, change -0.1%), onset none detected
- [OBSERVED EVIDENCE] `met-payment-service-p99_latency_ms-1740-1835` (moderate): payment-service p99_latency_ms: baseline 300.58 -> window mean 1703.85 (max 3577.47, change 466.8%), onset 2026-09-08T18:09:00Z
- [OBSERVED EVIDENCE] `logpat-payment-service-4672e5cc` (moderate): 8x ERROR on payment-service: 'Upstream timeout calling auth-service after 3000ms (charge ch_15)' (first 2026-09-08T18:10:19Z, last 2026-09-08T18:31:52Z)

Remaining uncertainties / missing evidence:
- [UNKNOWN] payment-service log volume and I/O metrics for 17:35-18:10Z

### 3. H3 - `db_connection_pool_exhaustion` in `postgres` (confidence 0.05, critic: n/a)
**INFERENCE:** Database or connection-pool saturation in payment-service or postgres causing slow responses. Mechanism: Pool exhaustion or DB slowness would raise payment-service latency directly.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- none

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-payment-service-db_conn_util_pct-1740-1835` (strong): payment-service db_conn_util_pct: baseline 35.48 -> window mean 35.31 (max 38.24, change -0.5%), onset none detected
- [OBSERVED EVIDENCE] `met-postgres-p99_latency_ms-1740-1835` (strong): postgres p99_latency_ms: baseline 25.02 -> window mean 24.92 (max 27.2, change -0.4%), onset none detected
- [OBSERVED EVIDENCE] `met-postgres-db_conn_util_pct-1740-1835` (moderate): postgres db_conn_util_pct: baseline 40.03 -> window mean 40.31 (max 44.04, change 0.7%), onset none detected
- [OBSERVED EVIDENCE] `met-postgres-disk_io_wait_ms-1740-1835` (moderate): postgres disk_io_wait_ms: baseline 2.0 -> window mean 2.01 (max 2.24, change 0.3%), onset none detected

## Critic Review
- **Verdict:** `NOT_RUN` (rounds reviewed: 0)
- **Reasoning:** 

## Probable Root Cause
MOST PROBABLE EXPLANATION (INFERENCE, not confirmed): upstream_dependency_degradation in auth-service - Slow identity-provider JWKS refresh (external dependency) degrades auth-service token verification, which queues requests and causes payment-service timeouts.

## Corrective Actions
- Mitigate now: add tighter timeouts and a circuit breaker on payment-service calls to auth-service, and allow stale JWKS keys to be served in auth-service during IdP slowness
- Investigate the identity-provider/JWKS latency path and confirm with IdP health data
- Revert the payment-service log.level DEBUG change (OPS-2898) if still active

## Preventive Actions
- Increase JWKS cache TTL and use background refresh with stale-while-revalidate in auth-service
- Add bulkhead and queue limits for /v1/token/verify
- Add timeouts and a circuit breaker around all auth calls from payment-service (per HIST-2025-031)

## Monitoring Recommendations
- Dashboard for identity-provider latency and error rate, and auth-service JWKS refresh duration
- Alert on payment-to-auth timeout rate above 1%
- Alert on auth-service queue time and thread-pool saturation

## Evidence Gaps
- [UNKNOWN] query_metrics failed for service=auth-service, metrics=['p99_latency_ms', 'error_rate', 'db_conn_util_pct', 'cpu_pct', 'timeout_rate', 'cache_hit_rate', 'request_rate']: metrics: List should have at most 6 items after validation, not 7 (INVALID_QUERY)

## Limitations
- Telemetry covers only T0-60m to T0+30m, so the pre-17:35 baseline is limited
- Correlation of onset times (auth 18:07Z, payment 18:09Z) is consistent with causation but is not proof
- No identity-provider telemetry was available
- [agent-reported gap] No identity-provider metrics or logs beyond JWKS refresh warnings
- [agent-reported gap] auth-service cache_hit_rate not collected
- [agent-reported gap] One metrics query failed (7 metrics exceeded the 6-metric limit) and was re-run split, so no gap remains from that failure
- 1 tool calls failed and 0 returned partial data; affected areas are treated as unknown, not healthy.
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: agent submitted

## Final Status
`PROBABLE_ROOT_CAUSE`

Payment-service latency is a downstream symptom of auth-service degradation, which started about 18:07Z alongside slow identity-provider JWKS refreshes. Payment pods, payment DB, and postgres are healthy. The most probable root cause is upstream identity-provider/JWKS slowness, but this is unconfirmed because identity-provider telemetry is absent and the auth CPU increase is unexplained.

## Execution Statistics
```json
{
  "rounds": 1,
  "tool_calls": 14,
  "tool_failures": 0,
  "tool_retries": 0,
  "partial_results": 0,
  "agent_failures": 0,
  "agent_retries": 0,
  "invalid_llm_outputs": 1,
  "messages_exchanged": 0,
  "evidence_records": 72,
  "duration_s": 39.18,
  "tokens": {
    "input_tokens": 12,
    "output_tokens": 10531,
    "cache_read_tokens": 49002,
    "cache_write_tokens": 24163,
    "llm_calls": 5,
    "cost_usd": 0.008777094999999999
  },
  "tokens_by_agent": {
    "single_agent": {
      "input_tokens": 12,
      "output_tokens": 10531,
      "cache_read_tokens": 49002,
      "cache_write_tokens": 24163,
      "llm_calls": 5,
      "cost_usd": 0.008777094999999999
    }
  }
}
```
