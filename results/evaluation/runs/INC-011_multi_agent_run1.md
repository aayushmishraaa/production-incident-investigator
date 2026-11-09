# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-011
- **Title:** Platform-wide slowness and 429s
- **Severity:** SEV2
- **Affected services:** api-gateway, auth-service, user-service
- **Start time:** 2026-10-02T20:00:00+00:00
- **Investigation ID:** inv-79c97c8879 (multi_agent)
- **Final status:** `PROBABLE_ROOT_CAUSE`

## Executive Summary
INC-011 (SEV2) was a platform-wide latency and HTTP 429 event affecting api-gateway, auth-service and user-service, with symptoms starting at 20:00Z. The investigation status is PROBABLE_ROOT_CAUSE with confidence 0.58, meaning this is the most probable explanation rather than a confirmed fact. The leading hypothesis (H1) is a client-side retry storm from mobile-ios-7.4.0: the gateway rate limiter logged a WARN at 19:55:11Z stating that 363% of requests from this client were retries with Retry-After ignored (logpat-api-gateway-d39f8491). Gateway, auth-service and user-service request rates all stepped up at 19:55:00Z (+138%, +133%, +134% respectively; met-api-gateway-request_rate-1930-2030, met-auth-service-request_rate-1930-2030, met-user-service-request_rate-1930-2030). Gateway p95 latency and error rate rose at 19:56:00Z, and the first 429 was returned at 19:56:06Z (logpat-api-gateway-8a499a8e). Clients kept retrying, sustaining load through about 20:25Z. The user-service 7.1.3 release (19:48Z) and an edge/load-balancer change were rejected based on timing and metrics. The initial trigger of the mobile retries before 19:55Z was not identified.

## Incident Timeline
| Time (UTC) | Label | Event | Evidence |
|---|---|---|---|
| 2026-10-02T19:35:26Z | OBSERVED EVIDENCE | First log: 4x WARN on payment-service: 'Card network soft decline (code 05) for charge ch_30' (first 2026-10-02T19:35:26Z, last 2026-10-02T19:54:43Z) | logpat-payment-service-7e9bf84f |
| 2026-10-02T19:48:00Z | CONFIRMED FACT | Deployment of user-service 7.1.2->7.1.3 at 2026-10-02T19:48:00Z (SUCCEEDED): Copy changes on profile page | dep-78c036fc |
| 2026-10-02T19:55:00Z | OBSERVED EVIDENCE | Anomaly onset: api-gateway request_rate: baseline 1195.01 -> window mean 2839.14 (max 4529.1, change 137.6%), onset 2026-10-02T19:55:00Z | met-api-gateway-request_rate-1930-2030 |
| 2026-10-02T19:55:00Z | OBSERVED EVIDENCE | Anomaly onset: api-gateway cpu_pct: baseline 34.95 -> window mean 65.54 (max 92.91, change 87.5%), onset 2026-10-02T19:55:00Z | met-api-gateway-cpu_pct-1930-2030 |
| 2026-10-02T19:55:00Z | OBSERVED EVIDENCE | Anomaly onset: auth-service request_rate: baseline 903.83 -> window mean 2103.51 (max 3274.57, change 132.7%), onset 2026-10-02T19:55:00Z | met-auth-service-request_rate-1930-2030 |
| 2026-10-02T19:55:00Z | OBSERVED EVIDENCE | Anomaly onset: auth-service cpu_pct: baseline 30.15 -> window mean 56.71 (max 86.3, change 88.1%), onset 2026-10-02T19:55:00Z | met-auth-service-cpu_pct-1930-2030 |
| 2026-10-02T19:55:00Z | OBSERVED EVIDENCE | Anomaly onset: user-service request_rate: baseline 500.78 -> window mean 1173.59 (max 1838.14, change 134.4%), onset 2026-10-02T19:55:00Z | met-user-service-request_rate-1930-2030 |
| 2026-10-02T19:55:00Z | OBSERVED EVIDENCE | Anomaly onset: user-service request_rate: baseline 500.78 -> window mean 1124.49 (max 1838.14, change 124.5%), onset 2026-10-02T19:55:00Z | met-user-service-request_rate-1930-2025 |
| 2026-10-02T19:55:00Z | OBSERVED EVIDENCE | Anomaly onset: api-gateway request_rate: baseline 1195.01 -> window mean 2486.17 (max 4215.23, change 108.0%), onset 2026-10-02T19:55:00Z | met-api-gateway-request_rate-1945-2005 |
| 2026-10-02T19:55:00Z | OBSERVED EVIDENCE | Anomaly onset: auth-service request_rate: baseline 903.83 -> window mean 1853.11 (max 3224.91, change 105.0%), onset 2026-10-02T19:55:00Z | met-auth-service-request_rate-1945-2005 |
| 2026-10-02T19:55:00Z | OBSERVED EVIDENCE | Anomaly onset: user-service request_rate: baseline 500.78 -> window mean 1040.64 (max 1838.14, change 107.8%), onset 2026-10-02T19:55:00Z | met-user-service-request_rate-1945-2005 |
| 2026-10-02T19:55:11Z | OBSERVED EVIDENCE | First log: 3x WARN on api-gateway: 'Rate limiter: 363% of requests from client_id=mobile-ios-7.4.0 are retries (Retry-After ignored)' (first 2026-10-02T19:55:11Z, last 2026-10-02T20:01:40Z) | logpat-api-gateway-d39f8491 |
| 2026-10-02T19:56:00Z | OBSERVED EVIDENCE | Anomaly onset: api-gateway p95_latency_ms: baseline 120.83 -> window mean 661.73 (max 1250.29, change 447.7%), onset 2026-10-02T19:56:00Z | met-api-gateway-p95_latency_ms-1930-2030 |
| 2026-10-02T19:56:00Z | OBSERVED EVIDENCE | Anomaly onset: api-gateway error_rate: baseline 0.51 -> window mean 4.14 (max 7.6, change 718.4%), onset 2026-10-02T19:56:00Z | met-api-gateway-error_rate-1930-2030 |
| 2026-10-02T19:56:00Z | OBSERVED EVIDENCE | Anomaly onset: auth-service p95_latency_ms: baseline 45.08 -> window mean 350.2 (max 643.9, change 676.9%), onset 2026-10-02T19:56:00Z | met-auth-service-p95_latency_ms-1930-2030 |
| 2026-10-02T19:56:00Z | OBSERVED EVIDENCE | Anomaly onset: user-service p95_latency_ms: baseline 81.02 -> window mean 423.35 (max 746.4, change 422.5%), onset 2026-10-02T19:56:00Z | met-user-service-p95_latency_ms-1930-2030 |
| 2026-10-02T19:56:00Z | OBSERVED EVIDENCE | Anomaly onset: user-service cpu_pct: baseline 29.56 -> window mean 50.36 (max 72.53, change 70.4%), onset 2026-10-02T19:56:00Z | met-user-service-cpu_pct-1930-2030 |
| 2026-10-02T19:56:00Z | OBSERVED EVIDENCE | Anomaly onset: user-service p95_latency_ms: baseline 81.02 -> window mean 398.41 (max 746.4, change 391.7%), onset 2026-10-02T19:56:00Z | met-user-service-p95_latency_ms-1930-2025 |
| 2026-10-02T19:56:00Z | OBSERVED EVIDENCE | Anomaly onset: api-gateway error_rate: baseline 0.51 -> window mean 3.16 (max 7.25, change 525.6%), onset 2026-10-02T19:56:00Z | met-api-gateway-error_rate-1945-2005 |
| 2026-10-02T19:56:06Z | OBSERVED EVIDENCE | First log: 10x WARN on api-gateway: '429 Too Many Requests returned to client 58' (first 2026-10-02T19:56:06Z, last 2026-10-02T20:25:01Z) | logpat-api-gateway-8a499a8e |
| 2026-10-02T20:00:00Z | CONFIRMED FACT | Reported symptom start |  |
| 2026-10-02T20:06:00Z | CONFIRMED FACT | Incident reported |  |

## Observed Symptoms
- **OBSERVED EVIDENCE:** api-gateway p95_latency_ms: baseline 120.83 -> window mean 661.73 (max 1250.29, change 447.7%), onset 2026-10-02T19:56:00Z (met-api-gateway-p95_latency_ms-1930-2030)
- **OBSERVED EVIDENCE:** api-gateway error_rate: baseline 0.51 -> window mean 4.14 (max 7.6, change 718.4%), onset 2026-10-02T19:56:00Z (met-api-gateway-error_rate-1930-2030)
- **OBSERVED EVIDENCE:** api-gateway request_rate: baseline 1195.01 -> window mean 2839.14 (max 4529.1, change 137.6%), onset 2026-10-02T19:55:00Z (met-api-gateway-request_rate-1930-2030)
- **OBSERVED EVIDENCE:** api-gateway cpu_pct: baseline 34.95 -> window mean 65.54 (max 92.91, change 87.5%), onset 2026-10-02T19:55:00Z (met-api-gateway-cpu_pct-1930-2030)
- **OBSERVED EVIDENCE:** auth-service p95_latency_ms: baseline 45.08 -> window mean 350.2 (max 643.9, change 676.9%), onset 2026-10-02T19:56:00Z (met-auth-service-p95_latency_ms-1930-2030)
- **OBSERVED EVIDENCE:** auth-service request_rate: baseline 903.83 -> window mean 2103.51 (max 3274.57, change 132.7%), onset 2026-10-02T19:55:00Z (met-auth-service-request_rate-1930-2030)
- **OBSERVED EVIDENCE:** auth-service cpu_pct: baseline 30.15 -> window mean 56.71 (max 86.3, change 88.1%), onset 2026-10-02T19:55:00Z (met-auth-service-cpu_pct-1930-2030)
- **OBSERVED EVIDENCE:** user-service p95_latency_ms: baseline 81.02 -> window mean 423.35 (max 746.4, change 422.5%), onset 2026-10-02T19:56:00Z (met-user-service-p95_latency_ms-1930-2030)
- **OBSERVED EVIDENCE:** user-service request_rate: baseline 500.78 -> window mean 1173.59 (max 1838.14, change 134.4%), onset 2026-10-02T19:55:00Z (met-user-service-request_rate-1930-2030)
- **OBSERVED EVIDENCE:** user-service cpu_pct: baseline 29.56 -> window mean 50.36 (max 72.53, change 70.4%), onset 2026-10-02T19:56:00Z (met-user-service-cpu_pct-1930-2030)
- **OBSERVED EVIDENCE:** user-service p95_latency_ms: baseline 81.02 -> window mean 398.41 (max 746.4, change 391.7%), onset 2026-10-02T19:56:00Z (met-user-service-p95_latency_ms-1930-2025)
- **OBSERVED EVIDENCE:** user-service request_rate: baseline 500.78 -> window mean 1124.49 (max 1838.14, change 124.5%), onset 2026-10-02T19:55:00Z (met-user-service-request_rate-1930-2025)
- **OBSERVED EVIDENCE:** api-gateway request_rate: baseline 1195.01 -> window mean 2486.17 (max 4215.23, change 108.0%), onset 2026-10-02T19:55:00Z (met-api-gateway-request_rate-1945-2005)
- **OBSERVED EVIDENCE:** api-gateway error_rate: baseline 0.51 -> window mean 3.16 (max 7.25, change 525.6%), onset 2026-10-02T19:56:00Z (met-api-gateway-error_rate-1945-2005)
- **OBSERVED EVIDENCE:** auth-service request_rate: baseline 903.83 -> window mean 1853.11 (max 3224.91, change 105.0%), onset 2026-10-02T19:55:00Z (met-auth-service-request_rate-1945-2005)
- **OBSERVED EVIDENCE:** user-service request_rate: baseline 500.78 -> window mean 1040.64 (max 1838.14, change 107.8%), onset 2026-10-02T19:55:00Z (met-user-service-request_rate-1945-2005)
- **OBSERVED EVIDENCE:** [observability] DB connection utilisation flat: baseline mean 40.16% vs window mean 39.85% (max 44.41%); no onset detected. CPU, memory, p95 latency and disk IO wait also flat vs baseline. postgres timeout_rate is not collected. (met-postgres-db_conn_util_pct-1930-2025, met-postgres-cpu_pct-1930-2025, met-postgres-memory_pct-1930-2025, met-postgres-p95_latency_ms-1930-2025, met-postgres-disk_io_wait_ms-1930-2025)
- **OBSERVED EVIDENCE:** [observability] Redis cache hit rate (94.93% -> 94.98%), p95 latency (1.5 -> 1.48 ms), CPU (~15%) and memory (59.6 -> 60.1%) are unchanged vs baseline; no onset. Redis timeout_rate and eviction metrics are not collected, so evictions cannot be assessed. (met-redis-cache_hit_rate-1930-2025, met-redis-p95_latency_ms-1930-2025, met-redis-cpu_pct-1930-2025, met-redis-memory_pct-1930-2025)
- **OBSERVED EVIDENCE:** [observability] Redis request rate rose only 1.3% (5966 -> 6041 ops/s mean), with no step change; it does not match the ~2.2x jump seen at user-service. (met-redis-request_rate-1930-2025)
- **OBSERVED EVIDENCE:** [observability] notification-service shows no saturation: request rate 148 -> 149 rps, error rate ~0.2% flat, p95 latency ~90 ms flat, timeout rate ~0.05% flat, CPU ~20%, memory ~40%. No onset. (met-notification-service-request_rate-1930-2025, met-notification-service-error_rate-1930-2025, met-notification-service-p95_latency_ms-1930-2025, met-notification-service-timeout_rate-1930-2025, met-notification-service-cpu_pct-1930-2025, met-notification-service-memory_pct-1930-2025)
- **OBSERVED EVIDENCE:** [observability] user-service request rate onset at 19:55Z (baseline mean 501 rps; window mean 1124 rps, ~1625-1730 rps from 20:00Z). p95 latency onset at 19:56Z, jumping from ~80 ms to ~700 ms at 20:00Z. Error rate and timeout rate are unchanged. (met-user-service-request_rate-1930-2025, met-user-service-p95_latency_ms-1930-2025, met-user-service-error_rate-1930-2025, met-user-service-timeout_rate-1930-2025)
- **INFERENCE:** [observability] Shared dependencies postgres, redis and notification-service show no saturation, so the user-service latency/traffic step is not explained by resource exhaustion in these dependencies. The load increase at user-service is a candidate driver of the downstream 429s, but this is not confirmed by my data. (met-user-service-request_rate-1930-2025, met-postgres-db_conn_util_pct-1930-2025, met-redis-request_rate-1930-2025)
- **OBSERVED EVIDENCE:** [dependency] user-service deployment dep-78c036fc succeeded at 19:48Z, version 7.1.2 -> 7.1.3, by ci-pipeline, described as 'Copy changes on profile page'. This is the only deployment in 19:00-20:10Z across the queried scope (all services were queried, not just the focus set). (dep-78c036fc)
- **OBSERVED EVIDENCE:** [dependency] user-service p95 latency rose from ~80ms baseline to ~398ms window mean (+392%); the step is at the 20:00 sample (~726ms) and the detected onset is 19:56Z, i.e. about 8 minutes AFTER the 19:48Z deployment. Latency was flat (75-83ms) at 19:30-19:55 samples, which is after deployment. (met-user-service-p95_latency_ms-1930-2025)
- **OBSERVED EVIDENCE:** [dependency] user-service request_rate roughly doubled to tripled (baseline ~501 rps -> ~1124 rps window mean, sample 780 at 19:55 and 1625+ from 20:00). Onset 19:55Z, before p95 onset; the load increase precedes the latency step. error_rate did not change (~0.4% throughout). (met-user-service-request_rate-1930-2025, met-user-service-error_rate-1930-2025)
- **ASSUMPTION:** [critic: unsupported assumption] The root cause of the initial mobile-ios-7.4.0 retries before 19:55Z is unknown; no error or release trigger was found 
- **ASSUMPTION:** [critic: unsupported assumption] The 1700-9500 rps client figure is unverified and conflicts with the 77 req/min routed count 
- **ASSUMPTION:** [critic: unsupported assumption] The mechanism linking the gateway step to auth and user-service load is inferred from timing and not from a traced call path 
- **ASSUMPTION:** [critic: unsupported assumption] The redis flat request rate is not explained by the H1 path 

## Investigation Performed
- Round 1 | dependency | completed | attempts 1 | 4 tool calls | Identify the user-service release shortly before 2026-10-02T20:00:00Z: version, diff, config changes, and any other deployments or config changes across api-gat
- Round 1 | observability | completed | attempts 1 | 4 tool calls | Characterize latency, error rate, and 429 volume for api-gateway, auth-service, and user-service from 19:30Z to 20:30Z; determine which service first deviates a
- Round 1 | observability | completed | attempts 1 | 4 tool calls | Check shared dependencies postgres and redis plus notification-service for saturation signals (connections, CPU, memory, latency, timeouts, request rate to user
- Round 1 | reasoning | completed | attempts 1 | 0 tool calls | Develop and rank competing hypotheses
- Round 1 | critic | completed | attempts 1 | 0 tool calls | Independently review hypotheses
- Round 2 | observability | completed | attempts 1 | 4 tool calls | FOLLOW-UP requested by critic: Pull request_rate and error_rate for the services that call api-gateway and payment-service (and any other upstream callers) over
- Round 2 | observability | completed | attempts 1 | 2 tool calls | FOLLOW-UP requested by critic: Query api-gateway application logs 19:50-20:05Z for caller/client identifiers and the 429 rate-limit messages, to see which calle
- Round 2 | observability | completed | attempts 1 | 3 tool calls | FOLLOW-UP requested by critic: Query redis cache_hit_rate and db_conn_util_pct for user-service and auth-service over 19:30-20:30Z. (reason: Explains why redis 
- Round 2 | reasoning | completed | attempts 1 | 0 tool calls | Develop and rank competing hypotheses
- Round 2 | critic | completed | attempts 1 | 4 tool calls | Independently review hypotheses
- Round 2 | reporting | completed | attempts 1 | 0 tool calls | Write final report

## Root-Cause Hypotheses (ranked by evidence strength)
### 1. H1 - `traffic_surge` in `api-gateway` (confidence 0.58, critic: accept)
**INFERENCE:** A client-side retry storm from mobile-ios-7.4.0 began before 19:55Z. The gateway rate limiter throttled it, producing the 429s. The traffic step then loaded auth-service and user-service, which caused the latency rises. Mechanism: Trigger outside the observed services -> mobile-ios-7.4.0 retries at ~363-396% of normal volume with Retry-After ignored (first limiter WARN 19:55:11Z) -> gateway, auth and user request rates step up ~+105-138% at 19:55 -> gateway CPU rises and p95 latency rises at 19:56 -> gateway rate limiter returns 429s (first logged 19:56:06Z) -> clients keep retrying, sustaining load through 20:25.

Confidence breakdown: base 0.10; +0.08 corroboration across >=2 independent source types; +0.78 supporting evidence (8 refs, reliability-weighted, capped); -0.35 contradicting evidence (3 refs, capped 0.45); +0.08 proposed cause (19:55) precedes/coincides with first observed anomaly (19:55); -0.08 5 acknowledged evidence gaps; +0.05 critic review adjustment; = 0.58 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-api-gateway-d39f8491` (strong): 3x WARN on api-gateway: 'Rate limiter: 363% of requests from client_id=mobile-ios-7.4.0 are retries (Retry-After ignored)' (first 2026-10-02T19:55:11Z, last 2026-10-02T20:01:40Z)
- [OBSERVED EVIDENCE] `logpat-api-gateway-8a499a8e` (moderate): 10x WARN on api-gateway: '429 Too Many Requests returned to client 58' (first 2026-10-02T19:56:06Z, last 2026-10-02T20:25:01Z)
- [OBSERVED EVIDENCE] `logpat-api-gateway-8575c4f9` (moderate): 2x INFO on api-gateway: 'Top client by RPS: mobile-ios-7.4.0 (1700 rps)' (first 2026-10-02T19:56:19Z, last 2026-10-02T20:01:58Z)
- [OBSERVED EVIDENCE] `met-api-gateway-request_rate-1930-2030` (strong): api-gateway request_rate: baseline 1195.01 -> window mean 2839.14 (max 4529.1, change 137.6%), onset 2026-10-02T19:55:00Z
- [OBSERVED EVIDENCE] `met-auth-service-request_rate-1930-2030` (strong): auth-service request_rate: baseline 903.83 -> window mean 2103.51 (max 3274.57, change 132.7%), onset 2026-10-02T19:55:00Z
- [OBSERVED EVIDENCE] `met-user-service-request_rate-1930-2030` (strong): user-service request_rate: baseline 500.78 -> window mean 1173.59 (max 1838.14, change 134.4%), onset 2026-10-02T19:55:00Z
- [OBSERVED EVIDENCE] `met-api-gateway-p95_latency_ms-1930-2030` (moderate): api-gateway p95_latency_ms: baseline 120.83 -> window mean 661.73 (max 1250.29, change 447.7%), onset 2026-10-02T19:56:00Z
- [OBSERVED EVIDENCE] `met-payment-service-request_rate-1945-2005` (moderate): payment-service request_rate: baseline 301.34 -> window mean 298.02 (max 322.54, change -1.1%), onset none detected

Contradicting evidence:
- [OBSERVED EVIDENCE] `logpat-api-gateway-1bc55a4d` (moderate): 2x INFO on api-gateway: 'Routed 77 requests in last minute' (first 2026-10-02T19:54:35Z, last 2026-10-02T20:01:05Z)
- [OBSERVED EVIDENCE] `met-redis-request_rate-1930-2030` (moderate): redis request_rate: baseline 5966.73 -> window mean 6025.02 (max 6941.35, change 1.0%), onset none detected
- [OBSERVED EVIDENCE] `met-user-service-db_conn_util_pct-1930-2030` (weak): user-service db_conn_util_pct: baseline 30.04 -> window mean 30.14 (max 33.21, change 0.3%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Per-client request rate and 429 breakdown from the gateway
- [UNKNOWN] Gateway rate-limit limit value and window
- [UNKNOWN] The mobile-ios-7.4.0 client change log or release that might have triggered the retries
- [UNKNOWN] What initially made the client retry (errors or timeouts before 19:55)
- [UNKNOWN] Caller-side metrics for mobile-ios-7.4.0 and the edge/LB

### 2. H3 - `configuration_regression` in `api-gateway` (confidence 0.00, critic: reject)
**INFERENCE:** A gateway rate-limit or threshold change that the config store does not record lowered the effective limit, so the limiter began rejecting normal traffic at 19:56 and clients retried. Mechanism: Unrecorded limit change at gateway -> limiter rejects traffic above the new threshold -> 429s from 19:56:06Z -> clients ignore Retry-After and retry -> gateway load and latency rise and the traffic step appears.

Confidence breakdown: base 0.10; +0.08 corroboration across >=2 independent source types; +0.24 supporting evidence (2 refs, reliability-weighted, capped); -0.30 contradicting evidence (2 refs, capped 0.45); +0.08 proposed cause (19:55) precedes/coincides with first observed anomaly (19:55); -0.06 3 acknowledged evidence gaps; -0.40 critic review adjustment; = 0.00 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-api-gateway-8a499a8e` (moderate): 10x WARN on api-gateway: '429 Too Many Requests returned to client 58' (first 2026-10-02T19:56:06Z, last 2026-10-02T20:25:01Z)
- [OBSERVED EVIDENCE] `met-api-gateway-error_rate-1930-2030` (weak): api-gateway error_rate: baseline 0.51 -> window mean 4.14 (max 7.6, change 718.4%), onset 2026-10-02T19:56:00Z

Contradicting evidence:
- [OBSERVED EVIDENCE] `logpat-api-gateway-d39f8491` (moderate): 3x WARN on api-gateway: 'Rate limiter: 363% of requests from client_id=mobile-ios-7.4.0 are retries (Retry-After ignored)' (first 2026-10-02T19:55:11Z, last 2026-10-02T20:01:40Z)
- [OBSERVED EVIDENCE] `met-api-gateway-request_rate-1930-2030` (moderate): api-gateway request_rate: baseline 1195.01 -> window mean 2839.14 (max 4529.1, change 137.6%), onset 2026-10-02T19:55:00Z

Remaining uncertainties / missing evidence:
- [UNKNOWN] Gateway rate-limit configuration and its change history (the config store is not authoritative for the gateway)
- [UNKNOWN] Config-reload events on api-gateway
- [UNKNOWN] Limiter counters and limit values

### 3. H2 - `deployment_regression` in `user-service` (confidence 0.00, critic: reject)
**INFERENCE:** The user-service 7.1.3 release (19:48Z) caused a latency regression and extra load, with 429s as a downstream effect. Mechanism: Release 7.1.3 -> user-service latency and load rise -> callers retry -> gateway throttles.

Confidence breakdown: base 0.10; +0.04 supporting evidence (1 refs, reliability-weighted, capped); -0.45 contradicting evidence (3 refs, capped 0.45); +0.08 proposed cause (19:48) precedes/coincides with first observed anomaly (19:55); -0.04 2 acknowledged evidence gaps; -0.40 critic review adjustment; = 0.00 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [CONFIRMED FACT] `dep-78c036fc` (weak): Deployment of user-service 7.1.2->7.1.3 at 2026-10-02T19:48:00Z (SUCCEEDED): Copy changes on profile page

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-user-service-p95_latency_ms-1930-2025` (strong): user-service p95_latency_ms: baseline 81.02 -> window mean 398.41 (max 746.4, change 391.7%), onset 2026-10-02T19:56:00Z
- [OBSERVED EVIDENCE] `met-auth-service-request_rate-1930-2030` (strong): auth-service request_rate: baseline 903.83 -> window mean 2103.51 (max 3274.57, change 132.7%), onset 2026-10-02T19:55:00Z
- [OBSERVED EVIDENCE] `met-user-service-error_rate-1930-2030` (weak): user-service error_rate: baseline 0.4 -> window mean 0.4 (max 0.43, change -0.6%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Release diff for 7.1.3
- [UNKNOWN] user-service latency profile per endpoint after the deploy

### 4. H4 - `traffic_surge` in `api-gateway` (confidence 0.00, critic: reject)
**INFERENCE:** An edge, load balancer, or internal caller change (not a client) routed extra traffic to the gateway at 19:55Z, which the gateway then throttled. Mechanism: Edge/LB or internal caller routing change at 19:55 -> extra traffic reaches api-gateway -> gateway, auth and user request rates step up -> latency rises at 19:56 -> limiter returns 429s.

Confidence breakdown: base 0.10; +0.16 supporting evidence (2 refs, reliability-weighted, capped); -0.15 contradicting evidence (1 refs, capped 0.45); +0.08 proposed cause (19:55) precedes/coincides with first observed anomaly (19:55); -0.04 2 acknowledged evidence gaps; -0.40 critic review adjustment; = 0.00 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [OBSERVED EVIDENCE] `met-api-gateway-request_rate-1930-2030` (moderate): api-gateway request_rate: baseline 1195.01 -> window mean 2839.14 (max 4529.1, change 137.6%), onset 2026-10-02T19:55:00Z
- [OBSERVED EVIDENCE] `met-payment-service-request_rate-1945-2005` (weak): payment-service request_rate: baseline 301.34 -> window mean 298.02 (max 322.54, change -1.1%), onset none detected

Contradicting evidence:
- [OBSERVED EVIDENCE] `logpat-api-gateway-d39f8491` (moderate): 3x WARN on api-gateway: 'Rate limiter: 363% of requests from client_id=mobile-ios-7.4.0 are retries (Retry-After ignored)' (first 2026-10-02T19:55:11Z, last 2026-10-02T20:01:40Z)

Remaining uncertainties / missing evidence:
- [UNKNOWN] Edge/LB metrics and change history
- [UNKNOWN] Per-caller breakdown of api-gateway requests

## Critic Review
- **Verdict:** `APPROVED` (rounds reviewed: 2)
- **Reasoning:** Leading hypothesis H1 (mobile-ios-7.4.0 retry storm loading the gateway, then auth and user-service, with 429s from the gateway rate limiter) is the best-supported explanation. The client-attributed limiter WARN (19:55:11Z) precedes the first 429 (19:56:06Z), and the gateway, auth and user request-rate steps all start at 19:55:00Z, one minute before the latency and error onsets at 19:56. payment-service and redis are flat, so the surge is not platform-wide. My own checks found no api-gateway config change and no api-gateway deployment in 19:00-20:30Z, which weakens H3. The only user-service deploy (19:48Z, H2) is contradicted: user-service p95 was flat from 19:30 to 19:55 and auth-service shows the same step without any dependency on user-service. H4 is contradicted by the log attribution of the surge to one client. The pre-19:55 log scan found no mobile-ios-7.4.0 errors or other trigger, so what initially prompted retries is unexplained. The 1700-9500 rps figure conflicts with the 77 req/min routed count and needs reconciling, but it does not undermine the time ordering.
- H1: **accept** - Client-attributed retry WARN at 19:55:11Z precedes the 429s at 19:56:06Z. Gateway, auth and user request-rate steps align at 19:55 and latency/error onsets follow at 19:56. Payment and redis are flat. The initial retry trigger and the rps discrepancy are open limitations, not contradictions.
- H2: **reject** - user-service p95 was flat (75-83 ms) from 19:30-19:55 after the 19:48 deploy, and the rise starts at 19:56 after the traffic step. There is no error change, and auth-service shows the same step without depending on user-service. The pre-check flagged this as correlation only.
- H3: **reject** - No api-gateway config change or deployment appears in the config and deployment records for 19:00-20:30Z. The limiter WARN and the traffic step both precede the first 429, so load, not a new threshold, is the better-timed cause. The config store is not authoritative for the gateway, but the timing evidence already disfavours this.
- H4: **reject** - The gateway logs attribute the excess to a single client (mobile-ios-7.4.0, retries with Retry-After ignored), which points to client behaviour rather than an edge or LB routing change. No edge or LB evidence supports a routing change.
- pre-check blocking `correlation_only` on H2: change hypothesis supported only by the change record itself (temporal correlation); no log/metric evidence of the changed behaviour
- pre-check warning `culprit_symptom` on H2: no log/metric evidence cited for culprit user-service
- pre-check warning `single_source` on H2: all support comes from one source type (deployment)
- pre-check warning `single_source` on H4: all support comes from one source type (metric)
- alternative: An edge/LB or internal caller routing change at 19:55Z (H4), which the per-client log attribution argues against but does not fully exclude
- alternative: A user-service 7.1.3 regression (H2), which the flat pre-19:55 latency and the shared auth-service step argue against
- alternative: An unrecorded gateway limit change (H3), with no config or deploy record found but the config store not being authoritative for the gateway

## Probable Root Cause
MOST PROBABLE EXPLANATION (INFERENCE, not confirmed): traffic_surge in api-gateway - A client-side retry storm from mobile-ios-7.4.0 began before 19:55Z. The gateway rate limiter throttled it, producing the 429s. The traffic step then loaded auth-service and user-service, which caused the latency rises.

## Corrective Actions
- Throttle or block mobile-ios-7.4.0 traffic at the gateway (or edge) to reduce retry load on api-gateway, auth-service and user-service, and confirm request rates return toward baseline (~1195, ~904, ~501 rps).
- Enforce Retry-After or apply a temporary per-client cap for mobile-ios-7.4.0 so that retries stop amplifying the 429 cycle (logpat-api-gateway-d39f8491, logpat-api-gateway-8a499a8e).
- Monitor gateway CPU and p95 latency after mitigation to confirm recovery, and keep the user-service 7.1.3 release under observation without rolling back unless new evidence appears.
- Coordinate with mobile owners to determine whether a client-side mobile release or user-facing change triggered retries before 19:55Z.

## Preventive Actions
- Fix mobile-ios-7.4.0 retry behaviour so it honours Retry-After and uses exponential backoff with jitter, and add a retry budget to the client.
- Add per-client rate limits and fair-share quotas at the gateway so a single client cannot drive shared auth and user-service load.
- Reconcile the gateway rate-limit configuration with the config store, since the config store was not authoritative for the gateway in this investigation, and record all limiter changes.
- Investigate and document the dependency path from api-gateway to auth-service and user-service with traced call paths, so the load-propagation mechanism is verified rather than inferred.
- Review the client-reported rps figure (1700-9500 rps) against the 77 req/min routed count to fix the metric source and avoid misleading capacity assessments.

## Monitoring Recommendations
- Alert when api-gateway request rate exceeds about 2x its 7-day baseline, or when any single client_id exceeds a set share of total traffic.
- Alert on the rate-limiter WARN 'retries (Retry-After ignored)' log pattern and on any sustained 429 count above a threshold.
- Track per-client retry ratio and Retry-After compliance as metrics on the gateway.
- Alert on api-gateway p95 latency above roughly 2x baseline and on error rate above 1% for more than 2 minutes.
- Monitor auth-service and user-service request rate and latency with step-change detection to catch load propagation early.
- Log and alert on any gateway config or deployment change, and on user-service deploys, with correlation to incident timelines.

## Evidence Gaps
- none recorded

## Limitations
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: critic verdict APPROVED

## Final Status
`PROBABLE_ROOT_CAUSE`

The most probable explanation for INC-011 is a retry storm from mobile-ios-7.4.0 that began before 19:55Z. The gateway rate limiter throttled it, producing 429s from 19:56Z, while the traffic step loaded auth-service and user-service and drove latency increases. This conclusion is supported by timing, per-client log attribution and flat payment-service and redis traffic, but it is not confirmed. Open gaps include the unexplained trigger for the initial retries, the unreconciled rps figures, and an inferred rather than traced dependency path. The user-service 7.1.3 release and an edge/LB change were rejected, and an unrecorded gateway config change remains a lower-likelihood alternative.

## Execution Statistics
```json
{
  "rounds": 2,
  "tool_calls": 28,
  "tool_failures": 0,
  "tool_retries": 0,
  "partial_results": 0,
  "agent_failures": 0,
  "agent_retries": 0,
  "invalid_llm_outputs": 0,
  "messages_exchanged": 35,
  "evidence_records": 97,
  "duration_s": 108.37,
  "tokens": {
    "input_tokens": 68,
    "output_tokens": 35218,
    "cache_read_tokens": 36437,
    "cache_write_tokens": 99510,
    "llm_calls": 22,
    "cost_usd": 0.030418919999999995
  },
  "tokens_by_agent": {
    "orchestrator": {
      "input_tokens": 6,
      "output_tokens": 1143,
      "cache_read_tokens": 1327,
      "cache_write_tokens": 2532,
      "llm_calls": 2,
      "cost_usd": 0.0009018699999999999
    },
    "dependency": {
      "input_tokens": 8,
      "output_tokens": 2579,
      "cache_read_tokens": 7164,
      "cache_write_tokens": 5170,
      "llm_calls": 3,
      "cost_usd": 0.00200819
    },
    "observability": {
      "input_tokens": 32,
      "output_tokens": 15128,
      "cache_read_tokens": 19506,
      "cache_write_tokens": 37219,
      "llm_calls": 11,
      "cost_usd": 0.012414634999999999
    },
    "reasoning": {
      "input_tokens": 8,
      "output_tokens": 9544,
      "cache_read_tokens": 0,
      "cache_write_tokens": 31191,
      "llm_calls": 2,
      "cost_usd": 0.008671675
    },
    "critic": {
      "input_tokens": 10,
      "output_tokens": 5164,
      "cache_read_tokens": 8440,
      "cache_write_tokens": 19481,
      "llm_calls": 3,
      "cost_usd": 0.005102525
    },
    "reporting": {
      "input_tokens": 4,
      "output_tokens": 1660,
      "cache_read_tokens": 0,
      "cache_write_tokens": 3917,
      "llm_calls": 1,
      "cost_usd": 0.001320025
    }
  }
}
```
