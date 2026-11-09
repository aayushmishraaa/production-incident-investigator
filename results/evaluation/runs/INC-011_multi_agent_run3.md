# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-011
- **Title:** Platform-wide slowness and 429s
- **Severity:** SEV2
- **Affected services:** api-gateway, auth-service, user-service
- **Start time:** 2026-10-02T20:00:00+00:00
- **Investigation ID:** inv-e359abd7fd (multi_agent)
- **Final status:** `ROOT_CAUSE_IDENTIFIED`

## Executive Summary
INC-011 (SEV2) affected api-gateway, auth-service and user-service with widespread latency and HTTP 429 errors starting around 20:00Z on 2026-10-02. Final status is ROOT_CAUSE_IDENTIFIED. The leading hypothesis (confidence 0.83) is a traffic surge at api-gateway driven by mobile-ios-7.4.0 clients retrying without honouring Retry-After. Gateway request rate stepped from a baseline of about 1195 rps to a window mean of about 2839 rps beginning 19:55Z (H1; met-api-gateway-request_rate-1930-2030). The gateway logged the mobile-ios-7.4.0 retry attribution at 19:55:11Z (logpat-api-gateway-d39f8491) and the first 429 at 19:56:06Z (logpat-api-gateway-8a499a8e). A single client reported at 1700 rps (logpat-api-gateway-8575c4f9) exceeds the pre-incident gateway baseline, which is sufficient to explain the step. The gateway rate limiter then returned 429s, and retries sustained the elevated load through about 20:25Z. Error rate rose from 0.51% to a window mean of 4.14% (max 7.6%). Auth-service and user-service load doubled at 19:55Z, consistent with being reached through the gateway. The user-service 7.1.3 release (19:48Z) was rejected as the cause (H2), and a stricter rate-limit configuration was rejected (H3). The unnamed external-driver hypothesis (H4) was rejected, though not fully excluded.

## Incident Timeline
| Time (UTC) | Label | Event | Evidence |
|---|---|---|---|
| 2026-10-02T19:32:46Z | OBSERVED EVIDENCE | First log: 6x WARN on auth-service: 'Login rate limit hit for user id u-79' (first 2026-10-02T19:32:46Z, last 2026-10-02T20:28:37Z) | logpat-auth-service-cc8d3b87 |
| 2026-10-02T19:35:26Z | OBSERVED EVIDENCE | First log: 7x WARN on payment-service: 'Card network soft decline (code 05) for charge ch_30' (first 2026-10-02T19:35:26Z, last 2026-10-02T20:17:02Z) | logpat-payment-service-7e9bf84f |
| 2026-10-02T19:35:44Z | OBSERVED EVIDENCE | First log: 6x WARN on postgres: 'duration: 14702 ms statement: SELECT report_rollup()' (first 2026-10-02T19:35:44Z, last 2026-10-02T20:27:55Z) | logpat-postgres-44883ca5 |
| 2026-10-02T19:40:07Z | OBSERVED EVIDENCE | First log: 5x WARN on api-gateway: 'Slow client upload from 10.4.50.12 (1.9MB)' (first 2026-10-02T19:40:07Z, last 2026-10-02T20:24:11Z) | logpat-api-gateway-88b04940 |
| 2026-10-02T19:47:26Z | OBSERVED EVIDENCE | First log: 5x WARN on notification-service: 'SMTP provider throttled 1 message' (first 2026-10-02T19:47:26Z, last 2026-10-02T20:20:56Z) | logpat-notification-service-54b86179 |
| 2026-10-02T19:48:00Z | CONFIRMED FACT | Deployment of user-service 7.1.2->7.1.3 at 2026-10-02T19:48:00Z (SUCCEEDED): Copy changes on profile page | dep-78c036fc |
| 2026-10-02T19:55:00Z | OBSERVED EVIDENCE | Anomaly onset: api-gateway request_rate: baseline 1195.01 -> window mean 2839.14 (max 4529.1, change 137.6%), onset 2026-10-02T19:55:00Z | met-api-gateway-request_rate-1930-2030 |
| 2026-10-02T19:55:00Z | OBSERVED EVIDENCE | Anomaly onset: api-gateway cpu_pct: baseline 34.95 -> window mean 65.54 (max 92.91, change 87.5%), onset 2026-10-02T19:55:00Z | met-api-gateway-cpu_pct-1930-2030 |
| 2026-10-02T19:55:00Z | OBSERVED EVIDENCE | Anomaly onset: auth-service request_rate: baseline 903.83 -> window mean 2103.51 (max 3274.57, change 132.7%), onset 2026-10-02T19:55:00Z | met-auth-service-request_rate-1930-2030 |
| 2026-10-02T19:55:00Z | OBSERVED EVIDENCE | Anomaly onset: auth-service cpu_pct: baseline 30.15 -> window mean 56.71 (max 86.3, change 88.1%), onset 2026-10-02T19:55:00Z | met-auth-service-cpu_pct-1930-2030 |
| 2026-10-02T19:55:00Z | OBSERVED EVIDENCE | Anomaly onset: user-service request_rate: baseline 500.78 -> window mean 1173.59 (max 1838.14, change 134.4%), onset 2026-10-02T19:55:00Z | met-user-service-request_rate-1930-2030 |
| 2026-10-02T19:55:00Z | OBSERVED EVIDENCE | Anomaly onset: api-gateway request_rate: baseline 1195.01 -> window mean 2732.17 (max 4529.1, change 128.6%), onset 2026-10-02T19:55:00Z | met-api-gateway-request_rate-1930-2025 |
| 2026-10-02T19:55:11Z | OBSERVED EVIDENCE | First log: 10x WARN on api-gateway: 'Rate limiter: 363% of requests from client_id=mobile-ios-7.4.0 are retries (Retry-After ignored)' (first 2026-10-02T19:55:11Z, last 2026-10-02T20:25:00Z) | logpat-api-gateway-d39f8491 |
| 2026-10-02T19:56:00Z | OBSERVED EVIDENCE | Anomaly onset: api-gateway error_rate: baseline 0.51 -> window mean 4.14 (max 7.6, change 718.4%), onset 2026-10-02T19:56:00Z | met-api-gateway-error_rate-1930-2030 |
| 2026-10-02T19:56:00Z | OBSERVED EVIDENCE | Anomaly onset: user-service cpu_pct: baseline 29.56 -> window mean 50.36 (max 72.53, change 70.4%), onset 2026-10-02T19:56:00Z | met-user-service-cpu_pct-1930-2030 |
| 2026-10-02T19:56:00Z | OBSERVED EVIDENCE | Anomaly onset: api-gateway error_rate: baseline 0.51 -> window mean 3.86 (max 7.6, change 664.0%), onset 2026-10-02T19:56:00Z | met-api-gateway-error_rate-1930-2025 |
| 2026-10-02T19:56:06Z | OBSERVED EVIDENCE | First log: 10x WARN on api-gateway: '429 Too Many Requests returned to client 58' (first 2026-10-02T19:56:06Z, last 2026-10-02T20:25:01Z) | logpat-api-gateway-8a499a8e |
| 2026-10-02T20:00:00Z | CONFIRMED FACT | Reported symptom start |  |
| 2026-10-02T20:06:00Z | CONFIRMED FACT | Incident reported |  |

## Observed Symptoms
- **OBSERVED EVIDENCE:** api-gateway error_rate: baseline 0.51 -> window mean 4.14 (max 7.6, change 718.4%), onset 2026-10-02T19:56:00Z (met-api-gateway-error_rate-1930-2030)
- **OBSERVED EVIDENCE:** api-gateway request_rate: baseline 1195.01 -> window mean 2839.14 (max 4529.1, change 137.6%), onset 2026-10-02T19:55:00Z (met-api-gateway-request_rate-1930-2030)
- **OBSERVED EVIDENCE:** api-gateway cpu_pct: baseline 34.95 -> window mean 65.54 (max 92.91, change 87.5%), onset 2026-10-02T19:55:00Z (met-api-gateway-cpu_pct-1930-2030)
- **OBSERVED EVIDENCE:** auth-service request_rate: baseline 903.83 -> window mean 2103.51 (max 3274.57, change 132.7%), onset 2026-10-02T19:55:00Z (met-auth-service-request_rate-1930-2030)
- **OBSERVED EVIDENCE:** auth-service cpu_pct: baseline 30.15 -> window mean 56.71 (max 86.3, change 88.1%), onset 2026-10-02T19:55:00Z (met-auth-service-cpu_pct-1930-2030)
- **OBSERVED EVIDENCE:** user-service request_rate: baseline 500.78 -> window mean 1173.59 (max 1838.14, change 134.4%), onset 2026-10-02T19:55:00Z (met-user-service-request_rate-1930-2030)
- **OBSERVED EVIDENCE:** user-service cpu_pct: baseline 29.56 -> window mean 50.36 (max 72.53, change 70.4%), onset 2026-10-02T19:56:00Z (met-user-service-cpu_pct-1930-2030)
- **OBSERVED EVIDENCE:** api-gateway request_rate: baseline 1195.01 -> window mean 2732.17 (max 4529.1, change 128.6%), onset 2026-10-02T19:55:00Z (met-api-gateway-request_rate-1930-2025)
- **OBSERVED EVIDENCE:** api-gateway error_rate: baseline 0.51 -> window mean 3.86 (max 7.6, change 664.0%), onset 2026-10-02T19:56:00Z (met-api-gateway-error_rate-1930-2025)
- **OBSERVED EVIDENCE:** [dependency] user-service deployed 7.1.2 -> 7.1.3 (SUCCEEDED, by ci-pipeline), described as 'Copy changes on profile page'. This is 12 minutes before T0 and 42 minutes after the window start. (dep-78c036fc)
- **OBSERVED EVIDENCE:** [dependency] Topology v2 (effective 2026-09-15) added edge notification-service -> user-service. user-service's downstream dependents are api-gateway, notification-service, order-service; upstream dependencies are postgres and redis. The edge was added ~2 weeks before the incident, so it is not a recent change. (topo-user-service-both-d2)
- **OBSERVED EVIDENCE:** [observability] DB connection utilisation, p95/p99 latency and CPU were flat versus baseline across 19:30-20:25 (conn util mean 39.85% vs 40.16% baseline; p95 11.9ms vs 12.0ms; p99 25.0ms vs 24.8ms; CPU 35.2% vs 34.9%). No onset detected. (met-postgres-db_conn_util_pct-1930-2025, met-postgres-p95_latency_ms-1930-2025, met-postgres-p99_latency_ms-1930-2025, met-postgres-cpu_pct-1930-2025)
- **OBSERVED EVIDENCE:** [observability] Postgres logged 5 slow-statement WARNs for SELECT report_rollup() (11-18 s each) at 19:35:44, 19:42:52, 19:56:49, 20:21:05 and 20:24:30. Recurring, not tied to a clear onset at T0; the recurring pattern is not visible in p95/p99 metrics. (logpat-postgres-44883ca5, log-2c74e237, log-325f90f1, log-3574f4d6, log-976540a6, log-a5065b53)
- **OBSERVED EVIDENCE:** [observability] Redis cache hit rate (94.98% vs 94.93% baseline) and p95 latency (1.48ms vs 1.5ms) were unchanged; memory 60.1% vs 59.6%. No redis WARN/ERROR logs in the window. (met-redis-cache_hit_rate-1930-2025, met-redis-p95_latency_ms-1930-2025, met-redis-memory_pct-1930-2025)
- **OBSERVED EVIDENCE:** [observability] notification-service request rate was flat (149.3 vs 148.2 rps baseline), error rate 0.2% unchanged, timeout rate 0.05% unchanged, p95 ~90ms unchanged. No evidence of an elevated notification-service call pattern toward user-service in this window (only its own metrics were queried; user-service traffic from notification-service was not directly measured). (met-notification-service-request_rate-1930-2025, met-notification-service-error_rate-1930-2025, met-notification-service-timeout_rate-1930-2025, met-notification-service-p95_latency_ms-1930-2025)
- **OBSERVED EVIDENCE:** [observability] order-service error rate (0.6%), timeout rate (0.1%), p95 (~203ms vs 201ms) and request rate (249.5 vs 250.5 rps) were all flat versus baseline. (met-order-service-error_rate-1930-2025, met-order-service-timeout_rate-1930-2025, met-order-service-p95_latency_ms-1930-2025, met-order-service-request_rate-1930-2025)
- **OBSERVED EVIDENCE:** [observability] payment-service error rate (0.8%), timeout rate (0.1%), p95 (~152ms vs 151ms) and request rate (299.8 vs 301.3 rps) were flat versus baseline. (met-payment-service-error_rate-1930-2025, met-payment-service-timeout_rate-1930-2025, met-payment-service-p95_latency_ms-1930-2025, met-payment-service-request_rate-1930-2025)
- **INFERENCE:** [observability] The report_rollup() slow queries are a recurring background issue that does not align with T0; they may be unrelated to the incident, or may affect a path not captured by aggregate metrics. Whether they contribute to user-service pressure is unknown from this data. 
- **OBSERVED EVIDENCE:** [observability] api-gateway request_rate rose from baseline mean 1195 to window mean 2839 (+137.6%); onset 19:55 (5-min sample 1914 at 19:55, ~4190 at 20:00). (met-api-gateway-request_rate-1930-2030)
- **OBSERVED EVIDENCE:** [observability] api-gateway CPU rose from 34.95% to 65.54% mean (max 92.9%); onset 19:55, sustained ~90% from 20:00. (met-api-gateway-cpu_pct-1930-2030)
- **OBSERVED EVIDENCE:** [observability] api-gateway error_rate rose from 0.51% to 4.14% mean (max 7.6%); onset 19:56, step to ~6.8% at 20:00 sample. (met-api-gateway-error_rate-1930-2030)
- **OBSERVED EVIDENCE:** [observability] api-gateway p99 latency was flat (baseline 247.9 ms vs window 250.2 ms, +0.9%); timeout_rate flat (~0.1%). Latency did not visibly change at the gateway in this window. (met-api-gateway-p99_latency_ms-1930-2030, met-api-gateway-timeout_rate-1930-2030)
- **OBSERVED EVIDENCE:** [observability] api-gateway WARN logs: rate limiter reports client_id=mobile-ios-7.4.0 retries at 363% of requests with Retry-After ignored (first 19:55:11, last 20:25:00, 10 occurrences); 10 '429 Too Many Requests returned to client' WARNs first at 19:56:06, last 20:25:01. (logpat-api-gateway-d39f8491, logpat-api-gateway-8a499a8e, log-43defc9f, log-6f435356)
- **OBSERVED EVIDENCE:** [observability] auth-service request_rate rose from 903.8 to 2103.5 (+132.7%), onset 19:55; CPU rose from 30.2% to 56.7% (max 86.3%), onset 19:55 with step to ~75% at 20:00. Its p99 (-1.5%), error_rate (~0.3%), timeout_rate and memory were essentially unchanged. Sparse 'Login rate limit hit' WARNs (6 total, 19:32-20:28) are not clearly tied to onset. (met-auth-service-request_rate-1930-2030, met-auth-service-cpu_pct-1930-2030, met-auth-service-p99_latency_ms-1930-2030, met-auth-service-error_rate-1930-2030, met-auth-service-timeout_rate-1930-2030, met-auth-service-memory_pct-1930-2030, logpat-auth-service-cc8d3b87)
- **OBSERVED EVIDENCE:** [observability] user-service request_rate rose from 500.8 to 1173.6 (+134.4%), onset 19:55 (780 at 19:55, 1624 at 20:00). (met-user-service-request_rate-1930-2030)
- **ASSUMPTION:** [critic: unsupported assumption] Retry-share metric (363–396%) is a valid volume measure 
- **ASSUMPTION:** [critic: unsupported assumption] Retry-After is ignored by the client SDK rather than merely logged as such by the gateway 
- **ASSUMPTION:** [critic: unsupported assumption] Retries, not organic demand, sustain the step through 20:25 

## Investigation Performed
- Round 1 | dependency | completed | attempts 1 | 5 tool calls | Identify deployments and configuration changes in the 60 minutes before 2026-10-02T20:00:00Z for user-service and its callers/dependencies, including the user-s
- Round 1 | observability | completed | attempts 1 | 5 tool calls | Analyze latency, error rate, and HTTP 429 volume for api-gateway, auth-service, and user-service from 2026-10-02T19:30Z to 20:30Z, and determine which service f
- Round 1 | observability | completed | attempts 1 | 7 tool calls | Check the shared datastores and downstream dependents for saturation or errors over the same window, to see whether the slowdown is coming from shared resources
- Round 1 | reasoning | completed | attempts 1 | 0 tool calls | Develop and rank competing hypotheses
- Round 1 | critic | completed | attempts 1 | 3 tool calls | Independently review hypotheses
- Round 2 | observability | completed | attempts 1 | 8 tool calls | FOLLOW-UP requested by critic: Break down api-gateway, auth-service and user-service request rate and 429 volume by client_id (from logs) for 19:30-20:30Z. Conf
- Round 2 | dependency | completed | attempts 1 | 4 tool calls | FOLLOW-UP requested by critic: Check for a mobile-ios-7.4.0 client release, server-side feature flag or push/notification trigger around 19:45-19:55Z, and wheth
- Round 2 | reasoning | completed | attempts 1 | 0 tool calls | Develop and rank competing hypotheses
- Round 2 | critic | completed | attempts 1 | 4 tool calls | Independently review hypotheses
- Round 2 | reporting | completed | attempts 1 | 0 tool calls | Write final report

## Root-Cause Hypotheses (ranked by evidence strength)
### 1. H1 - `traffic_surge` in `api-gateway` (confidence 0.83, critic: accept)
**INFERENCE:** A surge of inbound traffic beginning 19:55Z, driven by mobile-ios-7.4.0 clients retrying without honouring Retry-After, roughly doubled load at api-gateway. The gateway rate limiter then returned 429s, which feed further retries. Mechanism: Client retry behaviour (mobile-ios-7.4.0, Retry-After ignored) -> request rate at api-gateway steps ~2.3x at 19:55 -> gateway CPU rises to ~65-90% and error rate steps from 0.5% to ~7% at 19:56-20:00 as the rate limiter returns 429s -> clients keep retrying, sustaining the step through 20:25. Auth-service and user-service see the same step at 19:55 because they are reached through the gateway.

Confidence breakdown: base 0.10; +0.08 corroboration across >=2 independent source types; +0.78 supporting evidence (5 refs, reliability-weighted, capped); -0.10 contradicting evidence (2 refs, capped 0.45); +0.08 proposed cause (19:55) precedes/coincides with first observed anomaly (19:55); -0.08 4 acknowledged evidence gaps; +0.05 critic review adjustment; = 0.83 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-api-gateway-d39f8491` (strong): 10x WARN on api-gateway: 'Rate limiter: 363% of requests from client_id=mobile-ios-7.4.0 are retries (Retry-After ignored)' (first 2026-10-02T19:55:11Z, last 2026-10-02T20:25:00Z)
- [OBSERVED EVIDENCE] `logpat-api-gateway-8a499a8e` (strong): 10x WARN on api-gateway: '429 Too Many Requests returned to client 58' (first 2026-10-02T19:56:06Z, last 2026-10-02T20:25:01Z)
- [OBSERVED EVIDENCE] `met-api-gateway-request_rate-1930-2030` (strong): api-gateway request_rate: baseline 1195.01 -> window mean 2839.14 (max 4529.1, change 137.6%), onset 2026-10-02T19:55:00Z
- [OBSERVED EVIDENCE] `met-api-gateway-error_rate-1930-2030` (strong): api-gateway error_rate: baseline 0.51 -> window mean 4.14 (max 7.6, change 718.4%), onset 2026-10-02T19:56:00Z
- [OBSERVED EVIDENCE] `met-api-gateway-cpu_pct-1930-2030` (moderate): api-gateway cpu_pct: baseline 34.95 -> window mean 65.54 (max 92.91, change 87.5%), onset 2026-10-02T19:55:00Z

Contradicting evidence:
- [OBSERVED EVIDENCE] `logpat-api-gateway-d39f8491` (weak): 10x WARN on api-gateway: 'Rate limiter: 363% of requests from client_id=mobile-ios-7.4.0 are retries (Retry-After ignored)' (first 2026-10-02T19:55:11Z, last 2026-10-02T20:25:00Z)
- [OBSERVED EVIDENCE] `met-auth-service-request_rate-1930-2030` (weak): auth-service request_rate: baseline 903.83 -> window mean 2103.51 (max 3274.57, change 132.7%), onset 2026-10-02T19:55:00Z

Remaining uncertainties / missing evidence:
- [UNKNOWN] Per-client request volume at api-gateway for 19:50-20:00 (confirms whether mobile-ios-7.4.0 makes up the step).
- [UNKNOWN] Mobile client release, feature-flag, or push trigger record for 19:45-19:55 (not accessible to tools).
- [UNKNOWN] Whether the gateway/iOS SDK honours Retry-After.
- [UNKNOWN] Per-client breakdown for auth-service and user-service.

### 2. H4 - `unknown` in `None` (confidence 0.15, critic: reject)
**INFERENCE:** A shared upstream driver outside the monitored services (for example an external client, partner integration, scheduled job, or push-triggered wave) caused a simultaneous ~2.3x traffic step at 19:55 across api-gateway, auth-service and user-service. The 429s are a downstream consequence, not the origin. Mechanism: External or upstream traffic source ramps at 19:55 -> gateway, auth and user-service all see the same step -> gateway limiter starts 429ing -> client retries sustain load.

Confidence breakdown: base 0.10; +0.46 supporting evidence (3 refs, reliability-weighted, capped); -0.05 contradicting evidence (1 refs, capped 0.45); +0.08 proposed cause (19:55) precedes/coincides with first observed anomaly (19:55); -0.04 2 acknowledged evidence gaps; -0.40 critic review adjustment; = 0.15 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [OBSERVED EVIDENCE] `met-api-gateway-request_rate-1930-2030` (strong): api-gateway request_rate: baseline 1195.01 -> window mean 2839.14 (max 4529.1, change 137.6%), onset 2026-10-02T19:55:00Z
- [OBSERVED EVIDENCE] `met-auth-service-request_rate-1930-2030` (moderate): auth-service request_rate: baseline 903.83 -> window mean 2103.51 (max 3274.57, change 132.7%), onset 2026-10-02T19:55:00Z
- [OBSERVED EVIDENCE] `met-user-service-request_rate-1930-2030` (moderate): user-service request_rate: baseline 500.78 -> window mean 1173.59 (max 1838.14, change 134.4%), onset 2026-10-02T19:55:00Z

Contradicting evidence:
- [OBSERVED EVIDENCE] `logpat-api-gateway-d39f8491` (weak): 10x WARN on api-gateway: 'Rate limiter: 363% of requests from client_id=mobile-ios-7.4.0 are retries (Retry-After ignored)' (first 2026-10-02T19:55:11Z, last 2026-10-02T20:25:00Z)

Remaining uncertainties / missing evidence:
- [UNKNOWN] Per-client and per-source request volume (not available in any log source).
- [UNKNOWN] Upstream/external traffic records outside the monitored services.

### 3. H2 - `deployment_regression` in `user-service` (confidence 0.00, critic: reject)
**INFERENCE:** The user-service 7.1.3 release (19:48Z) introduced a behaviour change that increased calls into user-service, which in turn drove the gateway traffic step and rate limiting. Mechanism: 7.1.3 deploy at 19:48 -> altered call pattern to user-service -> more requests through api-gateway -> gateway rate limiter 429s.

Confidence breakdown: base 0.10; +0.08 corroboration across >=2 independent source types; +0.36 supporting evidence (3 refs, reliability-weighted, capped); -0.45 contradicting evidence (4 refs, capped 0.45); +0.08 proposed cause (19:48) precedes/coincides with first observed anomaly (19:55); -0.05 tool failures/partial data for user-service; -0.04 2 acknowledged evidence gaps; -0.40 critic review adjustment; = 0.00 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [CONFIRMED FACT] `dep-78c036fc` (moderate): Deployment of user-service 7.1.2->7.1.3 at 2026-10-02T19:48:00Z (SUCCEEDED): Copy changes on profile page
- [OBSERVED EVIDENCE] `logpat-user-service-5c9a79ef` (weak): 1x INFO on user-service: 'Starting user-service v7.1.3 (build 3290)' (first 2026-10-02T19:48:00Z, last 2026-10-02T19:48:00Z)
- [OBSERVED EVIDENCE] `met-user-service-request_rate-1930-2030` (moderate): user-service request_rate: baseline 500.78 -> window mean 1173.59 (max 1838.14, change 134.4%), onset 2026-10-02T19:55:00Z

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-auth-service-request_rate-1930-2030` (strong): auth-service request_rate: baseline 903.83 -> window mean 2103.51 (max 3274.57, change 132.7%), onset 2026-10-02T19:55:00Z
- [CONFIRMED FACT] `topo-auth-service-both-d2` (moderate): auth-service depends on ['postgres', 'redis']; called by ['api-gateway', 'payment-service'] (graph topology-v2)
- [OBSERVED EVIDENCE] `met-user-service-p99_latency_ms-1930-2030` (moderate): user-service p99_latency_ms: baseline 161.15 -> window mean 161.05 (max 173.38, change -0.1%), onset none detected
- [CONFIRMED FACT] `dep-78c036fc` (moderate): Deployment of user-service 7.1.2->7.1.3 at 2026-10-02T19:48:00Z (SUCCEEDED): Copy changes on profile page

Remaining uncertainties / missing evidence:
- [UNKNOWN] Any mechanism by which 7.1.3 changes call volume from callers (none found).
- [UNKNOWN] Per-caller volume into user-service.

### 4. H3 - `configuration_regression` in `api-gateway` (confidence 0.00, critic: reject)
**INFERENCE:** A rate-limit configuration at api-gateway became stricter or stopped honouring Retry-After, so ordinary traffic was throttled into 429s. Mechanism: Stricter rate-limit config or disabled Retry-After handling -> gateway rejects requests with 429 -> clients retry -> error rate rises.

Confidence breakdown: base 0.10; +0.16 supporting evidence (2 refs, reliability-weighted, capped); -0.45 contradicting evidence (2 refs, capped 0.45); +0.00 no cause time given; temporal precedence unverified; -0.04 2 acknowledged evidence gaps; -0.40 critic review adjustment; = 0.00 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-api-gateway-8a499a8e` (moderate): 10x WARN on api-gateway: '429 Too Many Requests returned to client 58' (first 2026-10-02T19:56:06Z, last 2026-10-02T20:25:01Z)
- [OBSERVED EVIDENCE] `logpat-api-gateway-d39f8491` (weak): 10x WARN on api-gateway: 'Rate limiter: 363% of requests from client_id=mobile-ios-7.4.0 are retries (Retry-After ignored)' (first 2026-10-02T19:55:11Z, last 2026-10-02T20:25:00Z)

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-api-gateway-request_rate-1930-2030` (strong): api-gateway request_rate: baseline 1195.01 -> window mean 2839.14 (max 4529.1, change 137.6%), onset 2026-10-02T19:55:00Z
- [OBSERVED EVIDENCE] `met-auth-service-request_rate-1930-2030` (moderate): auth-service request_rate: baseline 903.83 -> window mean 2103.51 (max 3274.57, change 132.7%), onset 2026-10-02T19:55:00Z

Remaining uncertainties / missing evidence:
- [UNKNOWN] Config store outside the change log (rate-limit settings may be held elsewhere).
- [UNKNOWN] Rate-limit policy history from the runtime.

## Critic Review
- **Verdict:** `APPROVED` (rounds reviewed: 2)
- **Reasoning:** H1 is the leading hypothesis and is supported by independent sources. New evidence from this round: the gateway logged "Top client by RPS: mobile-ios-7.4.0 (1700 rps)" at 19:56:19 (logpat-api-gateway-8575c4f9). That single client accounts for more than the entire pre-incident gateway baseline (~1195 rps), so it is sufficient to explain the ~1640 rps step. Timing is consistent: the gateway request_rate step begins at 19:55, the retry attribution for mobile-ios-7.4.0 appears at 19:55:11, and the first 429 at 19:56:06, followed by the error-rate step at 19:56. The auth-service doubling is also explained by this path. Auth is called only by api-gateway and payment-service (topology), and payment-service request rate is flat (+0.3%, met-payment-service-request_rate-1945-2030), so the auth step must arrive through the gateway. H2 is rejected: user-service 7.1.3 is a copy-only change, it cannot drive auth traffic (which does not depend on user-service), user-service p99 is flat, and its request step is downstream of the same gateway surge. H3 is rejected: inbound volume rose before any 429, no config changes exist in the window (get_config_changes returned none), and a stricter limiter cannot increase upstream load. H4 is largely superseded: the client-level attribution identifies a named driver, so an unnamed external source is not required, though it is not fully excluded. Residual caveats: the retry-ratio figures (314–396%) are not a valid fraction and should not be used as a volume measure; the Retry-After-ignored behaviour is reported by the gateway's own log, not verified in the client SDK; and what triggered the mobile-ios-7.4.0 client wave at 19:55 is not visible to the tools. These limit the explanation of the trigger but not the root-cause category (traffic surge from a client retry storm) or the culprit (mobile-ios-7.4.0 traffic at api-gateway).
- H1: **accept** - Named client mobile-ios-7.4.0 at 1700 rps exceeds the entire gateway baseline; onset at 19:55 precedes 429s (19:56:06) and error-rate step (19:56). Payment-service flat, so auth step comes via gateway. Caveat: retry-ratio metric validity and Retry-After handling unverified in client; trigger unknown.
- H2: **reject** - 7.1.3 is a copy change with no mechanism to raise callers' traffic; auth-service (no dependency on user-service) doubles at the same minute; user-service p99 flat; user-service step is downstream of the gateway surge.
- H3: **reject** - Inbound request volume rises at 19:55 before any 429; no config changes in the window; a stricter limiter cannot create the upstream load increase on auth and user-service.
- H4: **reject** - An unnamed upstream driver is not needed: the gateway's top client by RPS is identified as mobile-ios-7.4.0 at 1700 rps, which accounts for the step. Not fully excluded, but no supporting evidence for an external source beyond the shared timing already explained by H1.
- pre-check warning `cause_time` on H3: no cause time given; temporal precedence cannot be verified
- pre-check warning `single_source` on H3: all support comes from one source type (log)
- pre-check warning `single_source` on H4: all support comes from one source type (metric)
- alternative: Organic or external traffic growth at 19:55 with mobile-ios-7.4.0 as a minor contributor (not supported: single client exceeds baseline)
- alternative: Stricter gateway rate-limit config (no config change found in change log; live policy not checked)

## Probable Root Cause
ROOT CAUSE IDENTIFIED (critic-approved; still an INFERENCE from evidence): traffic_surge in api-gateway - A surge of inbound traffic beginning 19:55Z, driven by mobile-ios-7.4.0 clients retrying without honouring Retry-After, roughly doubled load at api-gateway. The gateway rate limiter then returned 429s, which feed further retries.

## Corrective Actions
- Immediately throttle or rate-limit mobile-ios-7.4.0 traffic at api-gateway, or temporarily raise per-client limits, to break the retry loop and restore headroom (cite logpat-api-gateway-d39f8491).
- Enforce Retry-After server-side at the gateway (for example, reject or delay retries that arrive before the advertised window) so that retry amplification stops while clients are updated.
- Confirm that gateway CPU (peak about 93%) and auth/user-service latency return to baseline after throttling, and communicate status to affected teams.
- Consider a temporary rollback or hold on mobile-ios-7.4.0 distribution or server-side feature flags for the affected client version, if throttling is insufficient.

## Preventive Actions
- Fix the mobile-ios-7.4.0 client retry logic so that it honours Retry-After with exponential backoff and jitter. Verify this in the client SDK, since the Retry-After-ignored behaviour is currently reported from the gateway log only.
- Add per-client quotas and fair-share limits at api-gateway so that a single client cannot consume more than a bounded share of capacity.
- Add capacity headroom or autoscaling for api-gateway so that a roughly 2.3x step does not push CPU to 90%+.
- Investigate what triggered the mobile-ios-7.4.0 client wave at 19:55Z (for example a push notification, feature rollout, or scheduled sync). This is not visible to current tools and is an open item.

## Monitoring Recommendations
- Alert on per-client request rate at api-gateway (for example, any single client_id above 2x its 7-day baseline, or above 500 rps) and on the retry share metric once it is validated as a true fraction.
- Alert on api-gateway 429 rate and error rate above 1% for more than 2 minutes, and on gateway CPU above 75% sustained.
- Track the mobile-ios-7.4.0 version mix and the Retry-After compliance rate in gateway logs, to confirm recovery as clients update.
- Close the evidence gap: user-service query_metrics failed because the request exceeded the 6-metric limit. Re-run the p99_latency_ms, timeout_rate and db_conn_util_pct queries for user-service in separate calls to fully confirm the H2 rejection.

## Evidence Gaps
- [UNKNOWN] query_metrics failed for service=user-service, metrics=['p99_latency_ms', 'error_rate', 'request_rate', 'cpu_pct', 'memory_pct', 'db_conn_util_pct', 'timeout_rate']: metrics: List should have at most 6 items after validation, not 7 (INVALID_QUERY)

## Limitations
- The Retry-After-ignored behaviour is reported by the gateway's own log and was not verified in the client SDK.
- The retry-share metric (314-396%) is not a valid fraction and was not used as a volume measure.
- The trigger for the mobile-ios-7.4.0 client wave at 19:55Z is not visible to the available tools.
- The live rate-limit policy was not checked. Only the change log was reviewed, and it showed no changes in the window.
- query_metrics failed for user-service because the request exceeded the 6-metric limit, so user-service p99 and other metrics were only partially checked.
- 1 tool calls failed and 0 returned partial data; affected areas are treated as unknown, not healthy.
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: critic verdict APPROVED

## Final Status
`ROOT_CAUSE_IDENTIFIED`

The most probable explanation for INC-011 is a client-driven traffic surge at api-gateway: mobile-ios-7.4.0 clients sent a large volume of requests and retried without honouring Retry-After. The gateway rate limiter responded with 429s, and these retries sustained the load until about 20:25Z. This is the most probable root cause, not a confirmed fact. The mechanism and culprit are supported by independent gateway logs and metrics. Remaining caveats are the unverified Retry-After behaviour in the client SDK, the untraced trigger for the 19:55Z client wave, and the invalid retry-share figures. These caveats do not change the root-cause category or culprit. Mitigation should focus on throttling the offending client and enforcing Retry-After at the gateway, followed by client and capacity fixes.

## Execution Statistics
```json
{
  "rounds": 2,
  "tool_calls": 38,
  "tool_failures": 0,
  "tool_retries": 0,
  "partial_results": 0,
  "agent_failures": 0,
  "agent_retries": 0,
  "invalid_llm_outputs": 2,
  "messages_exchanged": 31,
  "evidence_records": 131,
  "duration_s": 130.72,
  "tokens": {
    "input_tokens": 72,
    "output_tokens": 41523,
    "cache_read_tokens": 81418,
    "cache_write_tokens": 109584,
    "llm_calls": 25,
    "cost_usd": 0.03528088
  },
  "tokens_by_agent": {
    "orchestrator": {
      "input_tokens": 6,
      "output_tokens": 1247,
      "cache_read_tokens": 2654,
      "cache_write_tokens": 1252,
      "llm_calls": 2,
      "cost_usd": 0.00080714
    },
    "dependency": {
      "input_tokens": 16,
      "output_tokens": 7014,
      "cache_read_tokens": 16293,
      "cache_write_tokens": 12360,
      "llm_calls": 6,
      "cost_usd": 0.0052165300000000005
    },
    "observability": {
      "input_tokens": 26,
      "output_tokens": 17380,
      "cache_read_tokens": 47392,
      "cache_write_tokens": 38974,
      "llm_calls": 10,
      "cost_usd": 0.014038270000000002
    },
    "reasoning": {
      "input_tokens": 8,
      "output_tokens": 8390,
      "cache_read_tokens": 0,
      "cache_write_tokens": 31661,
      "llm_calls": 2,
      "cost_usd": 0.008153424999999999
    },
    "critic": {
      "input_tokens": 12,
      "output_tokens": 5549,
      "cache_read_tokens": 15079,
      "cache_write_tokens": 21271,
      "llm_calls": 4,
      "cost_usd": 0.005585365
    },
    "reporting": {
      "input_tokens": 4,
      "output_tokens": 1943,
      "cache_read_tokens": 0,
      "cache_write_tokens": 4066,
      "llm_calls": 1,
      "cost_usd": 0.0014801500000000002
    }
  }
}
```
