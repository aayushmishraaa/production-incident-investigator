# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-003
- **Title:** Payment service slow responses
- **Severity:** SEV2
- **Affected services:** payment-service
- **Start time:** 2026-09-08T18:10:00+00:00
- **Investigation ID:** inv-cb423b9842 (single_agent)
- **Final status:** `PROBABLE_ROOT_CAUSE`

## Executive Summary
Payment-service slowness (p99 ~300ms to ~3.4s, timeouts 0.1% to ~6%) is caused by auth-service degradation. auth-service p99 rose from 86ms to ~3.3s at 18:07-18:10, its error rate rose to ~2.9%, and CPU went from 30% to ~47%, with request-queue waits of 2-10s on /v1/token/verify. Payment logs show 3000ms upstream timeouts to auth-service starting at 18:10:19. Request volume was flat, so this is not a traffic surge. The probable trigger is slow JWKS refresh from identity-provider (120-970ms, first at 18:06:12), but this is not confirmed. Payment's own resources and error rate were unchanged.

## Incident Timeline
| Time (UTC) | Label | Event | Evidence |
|---|---|---|---|
| 2026-09-08T17:35:00Z | CONFIRMED FACT | Config change on payment-service: log.level INFO -> DEBUG at 2026-09-08T17:35:00Z (OPS-2898) | cfg-5c71fbd0 |
| 2026-09-08T17:40:49Z | OBSERVED EVIDENCE | First log: 6x WARN on auth-service: 'Login rate limit hit for user id u-37' (first 2026-09-08T17:40:49Z, last 2026-09-08T18:16:34Z) | logpat-auth-service-cc8d3b87 |
| 2026-09-08T17:41:57Z | OBSERVED EVIDENCE | First log: 5x WARN on user-service: 'Deprecated API /v1/users/legacy called by client web-38' (first 2026-09-08T17:41:57Z, last 2026-09-08T18:03:53Z) | logpat-user-service-742b555e |
| 2026-09-08T17:43:13Z | OBSERVED EVIDENCE | First log: 7x WARN on order-service: 'Inventory reservation retry for sku-47' (first 2026-09-08T17:43:13Z, last 2026-09-08T18:33:57Z) | logpat-order-service-95abd1bb |
| 2026-09-08T17:43:32Z | OBSERVED EVIDENCE | First log: 6x WARN on postgres: 'duration: 16002 ms statement: SELECT report_rollup()' (first 2026-09-08T17:43:32Z, last 2026-09-08T18:20:00Z) | logpat-postgres-44883ca5 |
| 2026-09-08T17:47:23Z | OBSERVED EVIDENCE | First log: 6x WARN on api-gateway: 'Slow client upload from 10.4.71.12 (1.9MB)' (first 2026-09-08T17:47:23Z, last 2026-09-08T18:33:02Z) | logpat-api-gateway-88b04940 |
| 2026-09-08T17:49:55Z | OBSERVED EVIDENCE | First log: 4x WARN on notification-service: 'SMTP provider throttled 1 message' (first 2026-09-08T17:49:55Z, last 2026-09-08T18:17:11Z) | logpat-notification-service-54b86179 |
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
### 1. H1 - `upstream_dependency_degradation` in `auth-service` (confidence 0.70, critic: n/a)
**INFERENCE:** auth-service is saturated or queueing on /v1/token/verify, and payment-service times out waiting on it. Mechanism: auth-service CPU rose ~30% to ~47% at 18:10 with flat request rate. Its request queue time reached 2-10s, so calls from payment exceed the 3000ms timeout and fail. Payment's latency and timeouts follow auth's degradation.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `met-auth-service-p99_latency_ms-1740-1835` (strong): auth-service p99_latency_ms: baseline 90.36 -> window mean 1981.57 (max 4228.52, change 2092.9%), onset 2026-09-08T18:07:00Z
- [OBSERVED EVIDENCE] `met-auth-service-error_rate-1740-1835` (strong): auth-service error_rate: baseline 0.3 -> window mean 1.55 (max 3.29, change 416.1%), onset 2026-09-08T18:08:00Z
- [OBSERVED EVIDENCE] `met-auth-service-cpu_pct-1740-1835` (moderate): auth-service cpu_pct: baseline 30.04 -> window mean 38.64 (max 52.26, change 28.6%), onset 2026-09-08T18:10:00Z
- [OBSERVED EVIDENCE] `logpat-auth-service-9246cbf2` (strong): 9x WARN on auth-service: 'Request queue time high for /v1/token/verify: 9700ms' (first 2026-09-08T18:07:11Z, last 2026-09-08T18:31:56Z)
- [OBSERVED EVIDENCE] `logpat-payment-service-4672e5cc` (strong): 8x ERROR on payment-service: 'Upstream timeout calling auth-service after 3000ms (charge ch_15)' (first 2026-09-08T18:10:19Z, last 2026-09-08T18:31:52Z)
- [OBSERVED EVIDENCE] `met-payment-service-timeout_rate-1740-1835` (strong): payment-service timeout_rate: baseline 0.1 -> window mean 2.68 (max 6.26, change 2564.7%), onset 2026-09-08T18:10:00Z
- [CONFIRMED FACT] `topo-payment-service-upstream-d2` (moderate): payment-service depends on ['auth-service', 'postgres', 'redis']; called by ? (graph topology-v1)

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-auth-service-timeout_rate-1740-1835` (moderate): auth-service timeout_rate: baseline 0.05 -> window mean 0.05 (max 0.06, change -0.3%), onset none detected
- [OBSERVED EVIDENCE] `met-auth-service-db_conn_util_pct-1740-1835` (weak): auth-service db_conn_util_pct: baseline 30.29 -> window mean 30.2 (max 33.16, change -0.3%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Thread pool, goroutine or event-loop metrics for auth-service
- [UNKNOWN] Auth per-endpoint latency breakdown and downstream call timing (auth -> redis / postgres)
- [UNKNOWN] Auth error logs explaining the failures themselves

### 2. H2 - `upstream_dependency_degradation` in `identity-provider` (confidence 0.45, critic: n/a)
**INFERENCE:** A slowdown at the external identity provider degrades auth-service JWKS refresh, which starves or stalls token verification. Mechanism: JWKS refresh calls to identity-provider slowed from 18:06 (120-970ms). Verification of tokens may block on refresh or on shared resources, and this starts auth degradation about 4 minutes before payment is affected.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-auth-service-171612d3` (strong): 11x WARN on auth-service: 'Slow JWKS refresh from identity-provider: 480 ms' (first 2026-09-08T18:06:12Z, last 2026-09-08T18:32:23Z)
- [INFERENCE] `hist-HIST-2025-031` (moderate): Past incident HIST-2025-031 'Checkout slow due to slow identity calls' (similarity 0.447): auth-service degraded by slow identity-provider JWKS refresh.
- [OBSERVED EVIDENCE] `met-auth-service-p99_latency_ms-1740-1835` (moderate): auth-service p99_latency_ms: baseline 90.36 -> window mean 1981.57 (max 4228.52, change 2092.9%), onset 2026-09-08T18:07:00Z

Contradicting evidence:
- [OBSERVED EVIDENCE] `logpat-auth-service-171612d3` (moderate): 11x WARN on auth-service: 'Slow JWKS refresh from identity-provider: 480 ms' (first 2026-09-08T18:06:12Z, last 2026-09-08T18:32:23Z)
- [OBSERVED EVIDENCE] `logpat-auth-service-dede43d7` (weak): 1x INFO on auth-service: 'JWKS cache refreshed (keys=4)' (first 2026-09-08T18:01:53Z, last 2026-09-08T18:01:53Z)

Remaining uncertainties / missing evidence:
- [UNKNOWN] identity-provider's own health and latency metrics (no telemetry was available for it)
- [UNKNOWN] Whether auth verification blocks synchronously on JWKS refresh

### 3. H3 - `configuration_regression` in `payment-service` (confidence 0.05, critic: n/a)
**INFERENCE:** A DEBUG log-level change on payment-service adds overhead. This is a weak alternative and is ruled out as the primary cause. Mechanism: cfg-5c71fbd0 changed log.level INFO to DEBUG at 17:35, which could add logging cost on the request path.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [CONFIRMED FACT] `cfg-5c71fbd0` (weak): Config change on payment-service: log.level INFO -> DEBUG at 2026-09-08T17:35:00Z (OPS-2898)

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-payment-service-cpu_pct-1740-1835` (strong): payment-service cpu_pct: baseline 40.41 -> window mean 40.36 (max 43.59, change -0.1%), onset none detected
- [OBSERVED EVIDENCE] `met-payment-service-p99_latency_ms-1740-1835` (strong): payment-service p99_latency_ms: baseline 300.58 -> window mean 1703.85 (max 3577.47, change 466.8%), onset 2026-09-08T18:09:00Z
- [OBSERVED EVIDENCE] `met-auth-service-p99_latency_ms-1740-1835` (moderate): auth-service p99_latency_ms: baseline 90.36 -> window mean 1981.57 (max 4228.52, change 2092.9%), onset 2026-09-08T18:07:00Z

Remaining uncertainties / missing evidence:
- [UNKNOWN] Payment log volume before and after 17:35

## Critic Review
- **Verdict:** `NOT_RUN` (rounds reviewed: 0)
- **Reasoning:** 

## Probable Root Cause
MOST PROBABLE EXPLANATION (INFERENCE, not confirmed): upstream_dependency_degradation in auth-service - auth-service is saturated or queueing on /v1/token/verify, and payment-service times out waiting on it.

## Corrective Actions
- Mitigate now: raise or relax the payment->auth timeout (3000ms) with a circuit breaker, or fail over token verification to a cached/local JWT validation path.
- Scale auth-service or relieve its verify queue (add replicas, or shed load) to stop the queue growth.
- Investigate the identity-provider JWKS slowdown and extend the JWKS cache TTL so verification stops depending on live refresh.

## Preventive Actions
- Add timeouts, retries budgets and circuit breakers around auth-service calls from payment-service.
- Make JWKS refresh asynchronous with stale-while-revalidate, so identity-provider slowness cannot block token verification.
- Alert on auth-service queue time and CPU, not only error rate.

## Monitoring Recommendations
- Alert on auth-service /v1/token/verify queue time > 500ms and p99 > 500ms.
- Track identity-provider latency and JWKS refresh duration as a dashboard panel.
- Alert on payment-service to auth-service timeout rate > 0.5%.

## Evidence Gaps
- none recorded

## Limitations
- The causal link from JWKS refresh to auth saturation is inferred, not proven.
- Historical incident HIST-2025-031 is an analogy only.
- The order of onset (JWKS 18:06, auth 18:07, payment 18:09-18:10) is based on 5-minute sampled metrics plus log timestamps.
- [agent-reported gap] No telemetry for identity-provider itself.
- [agent-reported gap] No thread-pool or event-loop metrics for auth-service.
- [agent-reported gap] No payment log volume data around the 17:35 DEBUG change.
- [agent-reported gap] Payment dashboard pods looked healthy, but the cause is in auth-service.
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: agent submitted

## Final Status
`PROBABLE_ROOT_CAUSE`

Payment-service latency and timeouts are downstream effects of degraded auth-service. auth-service p99 and error rate rose ~7 minutes before payment-service p99 did, auth-service CPU rose at the same time, and payment's timeouts are specifically 3000ms timeouts calling auth-service /v1/token/verify. Payment's own CPU, DB connection utilisation and error rate were flat. The trigger inside auth-service is not fully confirmed: slow JWKS refreshes from identity-provider began at 18:06 and match a past incident, but the magnitudes are modest and auth CPU growth is not fully explained by them.

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
  "evidence_records": 76,
  "duration_s": 25.51,
  "tokens": {
    "input_tokens": 10,
    "output_tokens": 5759,
    "cache_read_tokens": 34872,
    "cache_write_tokens": 12953,
    "llm_calls": 4,
    "cost_usd": 0.004848345
  },
  "tokens_by_agent": {
    "single_agent": {
      "input_tokens": 10,
      "output_tokens": 5759,
      "cache_read_tokens": 34872,
      "cache_write_tokens": 12953,
      "llm_calls": 4,
      "cost_usd": 0.004848345
    }
  }
}
```
