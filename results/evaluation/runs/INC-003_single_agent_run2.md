# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-003
- **Title:** Payment service slow responses
- **Severity:** SEV2
- **Affected services:** payment-service
- **Start time:** 2026-09-08T18:10:00+00:00
- **Investigation ID:** inv-c45cb16a8a (single_agent)
- **Final status:** `PROBABLE_ROOT_CAUSE`

## Executive Summary
Payment-service p99 rose from ~300ms to ~3.4s and timeout rate from 0.1% to ~6% starting 18:09-18:10Z. Payment's own CPU, DB connection utilisation, Redis and Postgres were all unchanged, so the pods look healthy because the bottleneck is upstream. Auth-service degraded first (p99 from ~90ms to ~4s, error rate 0.3% to ~2.9%, CPU 30% to ~47%, queue times up to 9.7s), starting 18:07-18:08Z. Auth logs show slow JWKS refreshes from identity-provider. Payment's errors are "Upstream timeout calling auth-service after 3000ms" and slow verify calls. Historical incident HIST-2025-031 matches this pattern, but it is an analogy only.

## Incident Timeline
| Time (UTC) | Label | Event | Evidence |
|---|---|---|---|
| 2026-09-08T17:35:00Z | CONFIRMED FACT | Config change on payment-service: log.level INFO -> DEBUG at 2026-09-08T17:35:00Z (OPS-2898) | cfg-5c71fbd0 |
| 2026-09-08T18:03:37Z | OBSERVED EVIDENCE | First log: 3x WARN on auth-service: 'Login rate limit hit for user id u-92' (first 2026-09-08T18:03:37Z, last 2026-09-08T18:16:34Z) | logpat-auth-service-cc8d3b87 |
| 2026-09-08T18:06:12Z | OBSERVED EVIDENCE | First log: 6x WARN on auth-service: 'Slow JWKS refresh from identity-provider: 480 ms' (first 2026-09-08T18:06:12Z, last 2026-09-08T18:19:16Z) | logpat-auth-service-171612d3 |
| 2026-09-08T18:07:00Z | OBSERVED EVIDENCE | Anomaly onset: auth-service p99_latency_ms: baseline 90.36 -> window mean 1981.57 (max 4228.52, change 2092.9%), onset 2026-09-08T18:07:00Z | met-auth-service-p99_latency_ms-1740-1835 |
| 2026-09-08T18:07:11Z | OBSERVED EVIDENCE | First log: 5x WARN on auth-service: 'Request queue time high for /v1/token/verify: 9700ms' (first 2026-09-08T18:07:11Z, last 2026-09-08T18:19:36Z) | logpat-auth-service-9246cbf2 |
| 2026-09-08T18:08:00Z | OBSERVED EVIDENCE | Anomaly onset: auth-service error_rate: baseline 0.3 -> window mean 1.55 (max 3.29, change 416.1%), onset 2026-09-08T18:08:00Z | met-auth-service-error_rate-1740-1835 |
| 2026-09-08T18:09:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service p99_latency_ms: baseline 300.58 -> window mean 1703.85 (max 3577.47, change 466.8%), onset 2026-09-08T18:09:00Z | met-payment-service-p99_latency_ms-1740-1835 |
| 2026-09-08T18:09:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service p95_latency_ms: baseline 149.75 -> window mean 1290.1 (max 2845.09, change 761.5%), onset 2026-09-08T18:09:00Z | met-payment-service-p95_latency_ms-1740-1835 |
| 2026-09-08T18:09:13Z | OBSERVED EVIDENCE | First log: 8x WARN on payment-service: 'Call to auth-service /v1/token/verify took 2550ms' (first 2026-09-08T18:09:13Z, last 2026-09-08T18:18:40Z) | logpat-payment-service-4cb3914c |
| 2026-09-08T18:10:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service timeout_rate: baseline 0.1 -> window mean 2.68 (max 6.26, change 2564.7%), onset 2026-09-08T18:10:00Z | met-payment-service-timeout_rate-1740-1835 |
| 2026-09-08T18:10:00Z | CONFIRMED FACT | Reported symptom start |  |
| 2026-09-08T18:10:19Z | OBSERVED EVIDENCE | First log: 4x ERROR on payment-service: 'Upstream timeout calling auth-service after 3000ms (charge ch_15)' (first 2026-09-08T18:10:19Z, last 2026-09-08T18:19:42Z) | logpat-payment-service-4672e5cc |
| 2026-09-08T18:16:00Z | CONFIRMED FACT | Incident reported |  |

## Observed Symptoms
- **OBSERVED EVIDENCE:** payment-service p99_latency_ms: baseline 300.58 -> window mean 1703.85 (max 3577.47, change 466.8%), onset 2026-09-08T18:09:00Z (met-payment-service-p99_latency_ms-1740-1835)
- **OBSERVED EVIDENCE:** payment-service p95_latency_ms: baseline 149.75 -> window mean 1290.1 (max 2845.09, change 761.5%), onset 2026-09-08T18:09:00Z (met-payment-service-p95_latency_ms-1740-1835)
- **OBSERVED EVIDENCE:** payment-service timeout_rate: baseline 0.1 -> window mean 2.68 (max 6.26, change 2564.7%), onset 2026-09-08T18:10:00Z (met-payment-service-timeout_rate-1740-1835)
- **OBSERVED EVIDENCE:** auth-service p99_latency_ms: baseline 90.36 -> window mean 1981.57 (max 4228.52, change 2092.9%), onset 2026-09-08T18:07:00Z (met-auth-service-p99_latency_ms-1740-1835)
- **OBSERVED EVIDENCE:** auth-service error_rate: baseline 0.3 -> window mean 1.55 (max 3.29, change 416.1%), onset 2026-09-08T18:08:00Z (met-auth-service-error_rate-1740-1835)

## Investigation Performed

## Root-Cause Hypotheses (ranked by evidence strength)
### 1. H1 - `upstream_dependency_degradation` in `auth-service` (confidence 0.75, critic: n/a)
**INFERENCE:** auth-service is saturated or stalled, likely because of slow JWKS/identity-provider calls, causing queueing on /v1/token/verify that propagates as timeouts to payment-service. Mechanism: auth-service p99 and queue time climb from 18:07; CPU rises at 18:10; payment calls to auth time out at 3000ms from 18:10. Payment latency and timeouts track auth degradation.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `met-auth-service-p99_latency_ms-1740-1835` (strong): auth-service p99_latency_ms: baseline 90.36 -> window mean 1981.57 (max 4228.52, change 2092.9%), onset 2026-09-08T18:07:00Z
- [OBSERVED EVIDENCE] `met-auth-service-error_rate-1740-1835` (strong): auth-service error_rate: baseline 0.3 -> window mean 1.55 (max 3.29, change 416.1%), onset 2026-09-08T18:08:00Z
- [OBSERVED EVIDENCE] `met-auth-service-cpu_pct-1740-1835` (moderate): auth-service cpu_pct: baseline 30.04 -> window mean 38.64 (max 52.26, change 28.6%), onset 2026-09-08T18:10:00Z
- [OBSERVED EVIDENCE] `logpat-auth-service-9246cbf2` (strong): 5x WARN on auth-service: 'Request queue time high for /v1/token/verify: 9700ms' (first 2026-09-08T18:07:11Z, last 2026-09-08T18:19:36Z)
- [OBSERVED EVIDENCE] `logpat-auth-service-171612d3` (moderate): 6x WARN on auth-service: 'Slow JWKS refresh from identity-provider: 480 ms' (first 2026-09-08T18:06:12Z, last 2026-09-08T18:19:16Z)
- [OBSERVED EVIDENCE] `logpat-payment-service-4672e5cc` (strong): 4x ERROR on payment-service: 'Upstream timeout calling auth-service after 3000ms (charge ch_15)' (first 2026-09-08T18:10:19Z, last 2026-09-08T18:19:42Z)
- [OBSERVED EVIDENCE] `logpat-payment-service-4cb3914c` (strong): 8x WARN on payment-service: 'Call to auth-service /v1/token/verify took 2550ms' (first 2026-09-08T18:09:13Z, last 2026-09-08T18:18:40Z)
- [OBSERVED EVIDENCE] `met-payment-service-timeout_rate-1740-1835` (strong): payment-service timeout_rate: baseline 0.1 -> window mean 2.68 (max 6.26, change 2564.7%), onset 2026-09-08T18:10:00Z
- [INFERENCE] `hist-HIST-2025-031` (weak): Past incident HIST-2025-031 'Checkout slow due to slow identity calls' (similarity 0.465): auth-service degraded by slow identity-provider JWKS refresh.

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-auth-service-timeout_rate-1740-1835` (moderate): auth-service timeout_rate: baseline 0.05 -> window mean 0.05 (max 0.06, change -0.3%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] identity-provider latency/error metrics (service not in telemetry; query failed)
- [UNKNOWN] auth-service thread/connection pool metrics
- [UNKNOWN] auth-service dependency trace for JWKS fetch timing

### 2. H2 - `configuration_regression` in `payment-service` (confidence 0.10, critic: n/a)
**INFERENCE:** A log.level change on payment-service (INFO->DEBUG at 17:35Z, OPS-2898) increased logging overhead and contributed to latency. Mechanism: DEBUG logging adds I/O and CPU per request, which could slow payment handling.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [CONFIRMED FACT] `cfg-5c71fbd0` (moderate): Config change on payment-service: log.level INFO -> DEBUG at 2026-09-08T17:35:00Z (OPS-2898)

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-payment-service-cpu_pct-1740-1835` (strong): payment-service cpu_pct: baseline 40.41 -> window mean 40.36 (max 43.59, change -0.1%), onset none detected
- [OBSERVED EVIDENCE] `met-payment-service-db_conn_util_pct-1740-1835` (moderate): payment-service db_conn_util_pct: baseline 35.48 -> window mean 35.31 (max 38.24, change -0.5%), onset none detected
- [OBSERVED EVIDENCE] `logpat-payment-service-4672e5cc` (moderate): 4x ERROR on payment-service: 'Upstream timeout calling auth-service after 3000ms (charge ch_15)' (first 2026-09-08T18:10:19Z, last 2026-09-08T18:19:42Z)

Remaining uncertainties / missing evidence:
- [UNKNOWN] Payment latency segments showing time spent in local work vs. waiting on auth

### 3. H3 - `infrastructure_degradation` in `postgres` (confidence 0.05, critic: n/a)
**INFERENCE:** Database storage or connection degradation in postgres. Mechanism: Would raise payment DB latency and connection use.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- none

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-postgres-p99_latency_ms-1740-1835` (strong): postgres p99_latency_ms: baseline 25.02 -> window mean 24.92 (max 27.2, change -0.4%), onset none detected
- [OBSERVED EVIDENCE] `met-postgres-disk_io_wait_ms-1740-1835` (strong): postgres disk_io_wait_ms: baseline 2.0 -> window mean 2.01 (max 2.24, change 0.3%), onset none detected
- [OBSERVED EVIDENCE] `met-postgres-db_conn_util_pct-1740-1835` (moderate): postgres db_conn_util_pct: baseline 40.03 -> window mean 40.31 (max 44.04, change 0.7%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] postgres timeout_rate (not collected)

## Critic Review
- **Verdict:** `NOT_RUN` (rounds reviewed: 0)
- **Reasoning:** 

## Probable Root Cause
MOST PROBABLE EXPLANATION (INFERENCE, not confirmed): upstream_dependency_degradation in auth-service - auth-service is saturated or stalled, likely because of slow JWKS/identity-provider calls, causing queueing on /v1/token/verify that propagates as timeouts to payment-service.

## Corrective Actions
- Mitigate auth-service: scale out replicas or shed load on /v1/token/verify.
- Engage identity-provider owners to check JWKS endpoint latency and availability.
- Revert payment-service log.level from DEBUG to INFO (OPS-2898) to remove unnecessary load.

## Preventive Actions
- Add timeouts, retries with backoff, and a circuit breaker around payment's auth calls, so a slow auth-service fails fast instead of holding threads.
- Cache JWKS keys with a longer TTL and stale-while-revalidate, so identity-provider slowness does not block token verification.
- Add identity-provider to the monitored service catalog.

## Monitoring Recommendations
- Alert on auth-service p99 and queue time for /v1/token/verify.
- Alert on JWKS refresh duration from identity-provider.
- Dashboard payment timeouts split by upstream dependency, so the upstream cause is visible from the payment dashboard.

## Evidence Gaps
- [UNKNOWN] query_metrics failed for service=identity-provider, metrics=['p99_latency_ms', 'error_rate', 'timeout_rate']: unknown service 'identity-provider'. Known: ['api-gateway', 'auth-service', 'message-queue', 'notification-service', 'order-service', 'payment-service', 'postgres', 'redis', 'user-service'] (INVALID_QUERY)

## Limitations
- Timing correlation between auth and payment onset is about 1-2 minutes, so causation is inferred from the dependency direction and log messages, not proven.
- Deployment history was checked over 16:00-18:35 for auth and 17:00-18:35 globally.
- [agent-reported gap] identity-provider is not a monitored service; query failed, so its health is unknown.
- [agent-reported gap] No deployments or config changes were recorded for auth-service in the window (empty results), so a trigger on that side is not observed.
- [agent-reported gap] timeout_rate is not collected for redis or postgres.
- [agent-reported gap] No thread-pool or queue-depth metrics for auth-service.
- 1 tool calls failed and 0 returned partial data; affected areas are treated as unknown, not healthy.
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: agent submitted

## Final Status
`PROBABLE_ROOT_CAUSE`

Payment-service latency and timeouts are downstream effects of degraded auth-service (/v1/token/verify). Auth-service degraded first (~18:07-18:08Z, p99 and error-rate onset), about 1-2 minutes before payment-service's onset at 18:09-18:10Z. Auth logs show request queueing and slow JWKS refreshes from identity-provider, which points to an upstream identity-provider slowdown as the likely trigger. identity-provider is not a monitored service, so this link is unconfirmed. The DEBUG log-level change on payment-service is not supported as the cause: payment CPU and DB pool are flat, and the change precedes onset by ~35 minutes.

## Execution Statistics
```json
{
  "rounds": 1,
  "tool_calls": 13,
  "tool_failures": 1,
  "tool_retries": 0,
  "partial_results": 0,
  "agent_failures": 0,
  "agent_retries": 0,
  "invalid_llm_outputs": 1,
  "messages_exchanged": 0,
  "evidence_records": 57,
  "duration_s": 35.26,
  "tokens": {
    "input_tokens": 14,
    "output_tokens": 9037,
    "cache_read_tokens": 57914,
    "cache_write_tokens": 20611,
    "llm_calls": 6,
    "cost_usd": 0.007675415
  },
  "tokens_by_agent": {
    "single_agent": {
      "input_tokens": 14,
      "output_tokens": 9037,
      "cache_read_tokens": 57914,
      "cache_write_tokens": 20611,
      "llm_calls": 6,
      "cost_usd": 0.007675415
    }
  }
}
```
