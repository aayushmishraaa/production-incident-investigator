# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-011
- **Title:** Platform-wide slowness and 429s
- **Severity:** SEV2
- **Affected services:** api-gateway, auth-service, user-service
- **Start time:** 2026-10-02T20:00:00+00:00
- **Investigation ID:** inv-125c66dbe3 (multi_agent)
- **Final status:** `ROOT_CAUSE_IDENTIFIED`

## Executive Summary
INC-011 (SEV2) was a platform-wide latency and HTTP 429 incident affecting api-gateway, auth-service, and user-service, with symptoms starting at 2026-10-02T20:00Z. The investigation reached status ROOT_CAUSE_IDENTIFIED with a leading hypothesis of a traffic surge entering api-gateway (confidence 0.88). Gateway request rate rose about 129% from baseline starting 19:55Z (met-api-gateway-request_rate-1930-2025), and auth-service and user-service request rates rose by a similar 123-125% in the same bucket (met-auth-service-request_rate-1930-2025, met-user-service-request_rate-1930-2025). CPU climbed to roughly 86% on auth-service and 71% on user-service (met-auth-service-cpu_pct-1930-2025, met-user-service-cpu_pct-1930-2025), and user-service p95 latency rose from about 81 ms to about 398 ms mean (met-user-service-p95_latency_ms-1930-2025). The gateway then returned 429s to clients, starting 19:56:06Z (logpat-api-gateway-8a499a8e), and gateway error rate rose from about 0.5% to about 3.9% mean, peaking at 7.6% (met-api-gateway-error_rate-1930-2025). The most probable explanation is a client-side retry storm from the mobile-ios-7.4.0 client population, which began at 19:55:11Z and ignored Retry-After headers, according to the validation critic's review of gateway logs. The reason the retries began (client release, upstream error, or other) was not established. The 7.1.3 user-service deployment at 19:48Z was a copy-only change and was rejected as a cause (dep-78c036fc, H2).

## Incident Timeline
| Time (UTC) | Label | Event | Evidence |
|---|---|---|---|
| 2026-10-02T19:35:44Z | OBSERVED EVIDENCE | First log: 5x WARN on postgres: 'duration: 14702 ms statement: SELECT report_rollup()' (first 2026-10-02T19:35:44Z, last 2026-10-02T20:24:30Z) | logpat-postgres-44883ca5 |
| 2026-10-02T19:48:00Z | CONFIRMED FACT | Deployment of user-service 7.1.2->7.1.3 at 2026-10-02T19:48:00Z (SUCCEEDED): Copy changes on profile page | dep-78c036fc |
| 2026-10-02T19:55:00Z | OBSERVED EVIDENCE | Anomaly onset: user-service request_rate: baseline 500.78 -> window mean 1124.49 (max 1838.14, change 124.5%), onset 2026-10-02T19:55:00Z | met-user-service-request_rate-1930-2025 |
| 2026-10-02T19:55:00Z | OBSERVED EVIDENCE | Anomaly onset: api-gateway request_rate: baseline 1195.01 -> window mean 2732.17 (max 4529.1, change 128.6%), onset 2026-10-02T19:55:00Z | met-api-gateway-request_rate-1930-2025 |
| 2026-10-02T19:55:00Z | OBSERVED EVIDENCE | Anomaly onset: auth-service request_rate: baseline 903.83 -> window mean 2016.93 (max 3257.22, change 123.2%), onset 2026-10-02T19:55:00Z | met-auth-service-request_rate-1930-2025 |
| 2026-10-02T19:55:00Z | OBSERVED EVIDENCE | Anomaly onset: auth-service cpu_pct: baseline 30.15 -> window mean 55.05 (max 86.3, change 82.6%), onset 2026-10-02T19:55:00Z | met-auth-service-cpu_pct-1930-2025 |
| 2026-10-02T19:55:11Z | OBSERVED EVIDENCE | First log: 3x WARN on api-gateway: 'Rate limiter: 363% of requests from client_id=mobile-ios-7.4.0 are retries (Retry-After ignored)' (first 2026-10-02T19:55:11Z, last 2026-10-02T20:01:40Z) | logpat-api-gateway-d39f8491 |
| 2026-10-02T19:56:00Z | OBSERVED EVIDENCE | Anomaly onset: user-service p95_latency_ms: baseline 81.02 -> window mean 398.41 (max 746.4, change 391.7%), onset 2026-10-02T19:56:00Z | met-user-service-p95_latency_ms-1930-2025 |
| 2026-10-02T19:56:00Z | OBSERVED EVIDENCE | Anomaly onset: api-gateway p95_latency_ms: baseline 120.83 -> window mean 617.62 (max 1250.29, change 411.2%), onset 2026-10-02T19:56:00Z | met-api-gateway-p95_latency_ms-1930-2025 |
| 2026-10-02T19:56:00Z | OBSERVED EVIDENCE | Anomaly onset: api-gateway error_rate: baseline 0.51 -> window mean 3.86 (max 7.6, change 664.0%), onset 2026-10-02T19:56:00Z | met-api-gateway-error_rate-1930-2025 |
| 2026-10-02T19:56:00Z | OBSERVED EVIDENCE | Anomaly onset: auth-service p95_latency_ms: baseline 45.08 -> window mean 327.57 (max 638.62, change 626.6%), onset 2026-10-02T19:56:00Z | met-auth-service-p95_latency_ms-1930-2025 |
| 2026-10-02T19:56:00Z | OBSERVED EVIDENCE | Anomaly onset: user-service cpu_pct: baseline 29.56 -> window mean 48.83 (max 71.04, change 65.2%), onset 2026-10-02T19:56:00Z | met-user-service-cpu_pct-1930-2025 |
| 2026-10-02T19:56:06Z | OBSERVED EVIDENCE | First log: 9x WARN on api-gateway: '429 Too Many Requests returned to client 58' (first 2026-10-02T19:56:06Z, last 2026-10-02T20:21:50Z) | logpat-api-gateway-8a499a8e |
| 2026-10-02T20:00:00Z | CONFIRMED FACT | Reported symptom start |  |
| 2026-10-02T20:06:00Z | CONFIRMED FACT | Incident reported |  |

## Observed Symptoms
- **OBSERVED EVIDENCE:** user-service request_rate: baseline 500.78 -> window mean 1124.49 (max 1838.14, change 124.5%), onset 2026-10-02T19:55:00Z (met-user-service-request_rate-1930-2025)
- **OBSERVED EVIDENCE:** user-service p95_latency_ms: baseline 81.02 -> window mean 398.41 (max 746.4, change 391.7%), onset 2026-10-02T19:56:00Z (met-user-service-p95_latency_ms-1930-2025)
- **OBSERVED EVIDENCE:** api-gateway p95_latency_ms: baseline 120.83 -> window mean 617.62 (max 1250.29, change 411.2%), onset 2026-10-02T19:56:00Z (met-api-gateway-p95_latency_ms-1930-2025)
- **OBSERVED EVIDENCE:** api-gateway error_rate: baseline 0.51 -> window mean 3.86 (max 7.6, change 664.0%), onset 2026-10-02T19:56:00Z (met-api-gateway-error_rate-1930-2025)
- **OBSERVED EVIDENCE:** api-gateway request_rate: baseline 1195.01 -> window mean 2732.17 (max 4529.1, change 128.6%), onset 2026-10-02T19:55:00Z (met-api-gateway-request_rate-1930-2025)
- **OBSERVED EVIDENCE:** auth-service p95_latency_ms: baseline 45.08 -> window mean 327.57 (max 638.62, change 626.6%), onset 2026-10-02T19:56:00Z (met-auth-service-p95_latency_ms-1930-2025)
- **OBSERVED EVIDENCE:** auth-service request_rate: baseline 903.83 -> window mean 2016.93 (max 3257.22, change 123.2%), onset 2026-10-02T19:55:00Z (met-auth-service-request_rate-1930-2025)
- **OBSERVED EVIDENCE:** user-service cpu_pct: baseline 29.56 -> window mean 48.83 (max 71.04, change 65.2%), onset 2026-10-02T19:56:00Z (met-user-service-cpu_pct-1930-2025)
- **OBSERVED EVIDENCE:** auth-service cpu_pct: baseline 30.15 -> window mean 55.05 (max 86.3, change 82.6%), onset 2026-10-02T19:55:00Z (met-auth-service-cpu_pct-1930-2025)
- **OBSERVED EVIDENCE:** [dependency] Only deployment in the 18:00-20:10Z window: user-service 7.1.2 -> 7.1.3 at 19:48Z by ci-pipeline, SUCCEEDED, described as 'Copy changes on profile page'. No rate-limit, retry, or timeout change is described in the record. (dep-78c036fc)
- **OBSERVED EVIDENCE:** [dependency] Topology: notification-service -> user-service edge was added in topology-v2, effective 2026-09-15 (about 2.5 weeks before the incident), so it is not a recent topology change. user-service upstreams are postgres and redis; downstream dependents are api-gateway, notification-service, order-service. (topo-user-service-both-d2)
- **OBSERVED EVIDENCE:** [dependency] user-service request_rate rose from ~500 rps baseline to ~1,624-1,731 rps from 20:00Z (onset 19:55Z, +124.5% window mean). Error rate did not change (~0.4%) and timeout rate was flat (~0.05%). (met-user-service-request_rate-1930-2025, met-user-service-error_rate-1930-2025, met-user-service-timeout_rate-1930-2025)
- **OBSERVED EVIDENCE:** [dependency] user-service p95 latency rose from ~81 ms to ~680-726 ms from 20:00Z (onset 19:56Z). The request rate step (19:55Z) and latency step (19:56Z) occurred about 7-8 minutes after the 19:48Z deploy, with no latency change visible in the 19:50 sample. (met-user-service-p95_latency_ms-1930-2025, met-user-service-request_rate-1930-2025)
- **INFERENCE:** [dependency] The 7.1.3 release may have changed client-facing call behaviour (e.g. extra calls per request or a caller retry loop) causing the load step; or an upstream caller (notification-service, api-gateway) increased traffic to user-service. Not verified: the diff of 7.1.3 beyond the release note is not available. (dep-78c036fc, topo-user-service-both-d2)
- **OBSERVED EVIDENCE:** [observability] Postgres CPU, memory, DB connection utilisation, p95 latency and disk IO wait stayed at baseline levels across 19:30–20:25 (CPU mean 35.2% vs 34.9%; conn util 39.9% vs 40.2%; p95 11.9 ms vs 12.0 ms). No onset detected. timeout_rate is not collected for postgres. (met-postgres-cpu_pct-1930-2025, met-postgres-db_conn_util_pct-1930-2025, met-postgres-p95_latency_ms-1930-2025, met-postgres-disk_io_wait_ms-1930-2025, met-postgres-memory_pct-1930-2025)
- **OBSERVED EVIDENCE:** [observability] Redis CPU, memory, p95 latency (~1.5 ms), cache hit rate (~95%) and error rate were flat versus baseline across the window with no onset. No evictions metric is available in the tool set. timeout_rate not collected for redis. (met-redis-cpu_pct-1930-2025, met-redis-memory_pct-1930-2025, met-redis-p95_latency_ms-1930-2025, met-redis-cache_hit_rate-1930-2025, met-redis-error_rate-1930-2025)
- **OBSERVED EVIDENCE:** [observability] user-service CPU rose from 29.6% baseline to ~65–71% and p95 latency from 81 ms to ~700 ms; both detected onset at 19:56Z (CPU sample 19:55 at 38%, 20:00 at 65.6%). DB connection util, memory, error rate and timeout rate did not change. (met-user-service-cpu_pct-1930-2025, met-user-service-p95_latency_ms-1930-2025, met-user-service-db_conn_util_pct-1930-2025, met-user-service-timeout_rate-1930-2025)
- **OBSERVED EVIDENCE:** [observability] auth-service CPU rose from 30.2% to ~75–86% and p95 latency from 45 ms to ~550–640 ms, onset 19:55Z (CPU) / 19:56Z (p95). Its DB connection util, error rate and timeout rate were unchanged. (met-auth-service-cpu_pct-1930-2025, met-auth-service-p95_latency_ms-1930-2025, met-auth-service-db_conn_util_pct-1930-2025)
- **OBSERVED EVIDENCE:** [observability] Postgres logged 5 WARN slow-statement entries for SELECT report_rollup() (11–18 s durations), at 19:35:44, 19:42:52, 19:56:49, 20:21:05, 20:24:30. These are sporadic and began before the 19:56 onset; the postgres latency metrics did not reflect them. (logpat-postgres-44883ca5, log-2c74e237, log-325f90f1, log-3574f4d6, log-976540a6, log-a5065b53)
- **INFERENCE:** [observability] The CPU spike on user-service and auth-service starting ~19:55–19:56Z, with auth latency rising simultaneously, may reflect a compute-bound change in user-service (e.g. the release) affecting its callers, or a shared upstream issue; the recurring report_rollup() slow queries are a possible concurrent load source but their timing alone does not establish causation. (met-user-service-cpu_pct-1930-2025, met-auth-service-cpu_pct-1930-2025, logpat-postgres-44883ca5)
- **OBSERVED EVIDENCE:** [observability] api-gateway p95 latency rose from baseline mean 120.8 ms to window mean 617.6 ms (+411%), max 1250 ms. Detected onset 19:56Z; sampled series steps from ~121 ms (19:55) to ~1093 ms (20:00) and stays ~1080-1170 ms through 20:25. (met-api-gateway-p95_latency_ms-1930-2025)
- **OBSERVED EVIDENCE:** [observability] api-gateway error_rate rose from baseline mean 0.51% to window mean 3.86% (max 7.6%), onset 19:56Z; sampled ~0.5% at 19:55 then ~6.8-7.6% from 20:00 onward. (met-api-gateway-error_rate-1930-2025)
- **OBSERVED EVIDENCE:** [observability] api-gateway request_rate rose from baseline mean ~1195 to window mean ~2732 (+129%); onset 19:55Z, 1914 at 19:55 and ~4000-4300 from 20:00 onward. (met-api-gateway-request_rate-1930-2025)
- **OBSERVED EVIDENCE:** [observability] api-gateway p99 latency (~250 ms vs baseline ~248 ms) and timeout_rate (~0.10%) show no meaningful change in the window. (met-api-gateway-p99_latency_ms-1930-2025, met-api-gateway-timeout_rate-1930-2025)
- **OBSERVED EVIDENCE:** [observability] api-gateway logged 9 WARN '429 Too Many Requests returned to client' messages between 19:56:06Z and 20:21:50Z (roughly every 3 min). The log pattern summary does not break down by endpoint or caller; the logged client IDs are opaque numbers. (logpat-api-gateway-8a499a8e, log-6f435356, log-47a3817c)
- **ASSUMPTION:** [critic: unsupported assumption] That the 7.4.0 client population is a deliberate or external surge rather than a faulty client build. The logs show retry behaviour but not the reason for it. 
- **ASSUMPTION:** [critic: unsupported assumption] That the 429s account for all of the gateway error increase. 

## Investigation Performed
- Round 1 | dependency | completed | attempts 1 | 4 tool calls | Identify the user-service release shortly before 2026-10-02T20:00:00Z: what changed (code, config, rate limits, retry/timeout settings, feature flags). Also che
- Round 1 | observability | completed | attempts 1 | 5 tool calls | Characterize latency, error rate, and 429 volume for api-gateway, auth-service, and user-service from 2026-10-02T19:30Z onward, including the onset time relativ
- Round 1 | observability | completed | attempts 1 | 6 tool calls | Check shared dependencies postgres and redis for saturation or errors (connections, CPU, memory, latency, evictions, timeouts) over the same window.
- Round 1 | reasoning | completed | attempts 1 | 0 tool calls | Develop and rank competing hypotheses
- Round 1 | critic | completed | attempts 1 | 4 tool calls | Independently review hypotheses
- Round 1 | reporting | completed | attempts 2 | 0 tool calls | Write final report

## Root-Cause Hypotheses (ranked by evidence strength)
### 1. H1 - `traffic_surge` in `api-gateway` (confidence 0.88, critic: accept)
**INFERENCE:** An unidentified upstream caller or client population increased request volume into api-gateway at ~19:55Z (about 2.3x). The extra load propagated to auth-service and user-service, saturating their CPU and raising p95 latency. The gateway then rate-limited some clients, producing 429s and the error-rate rise. Mechanism: External or caller-side traffic increase at the ingress (api-gateway request_rate +129%, onset 19:55Z) -> auth-service and user-service request rates rise by a similar ~123-125% in the same bucket -> CPU rises to ~75-86% (auth) and ~65-71% (user) -> p95 latency rises 4-7x at 19:56Z -> gateway/upstream saturation and per-client rate limiting return 429s and push gateway error rate from ~0.5% to ~7%.

Confidence breakdown: base 0.10; +0.08 corroboration across >=2 independent source types; +0.78 supporting evidence (8 refs, reliability-weighted, capped); -0.05 contradicting evidence (1 refs, capped 0.45); +0.08 proposed cause (19:55) precedes/coincides with first observed anomaly (19:55); -0.08 5 acknowledged evidence gaps; +0.05 critic review adjustment; = 0.88 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [OBSERVED EVIDENCE] `met-api-gateway-request_rate-1930-2025` (strong): api-gateway request_rate: baseline 1195.01 -> window mean 2732.17 (max 4529.1, change 128.6%), onset 2026-10-02T19:55:00Z
- [OBSERVED EVIDENCE] `met-auth-service-request_rate-1930-2025` (strong): auth-service request_rate: baseline 903.83 -> window mean 2016.93 (max 3257.22, change 123.2%), onset 2026-10-02T19:55:00Z
- [OBSERVED EVIDENCE] `met-user-service-request_rate-1930-2025` (strong): user-service request_rate: baseline 500.78 -> window mean 1124.49 (max 1838.14, change 124.5%), onset 2026-10-02T19:55:00Z
- [OBSERVED EVIDENCE] `met-auth-service-cpu_pct-1930-2025` (moderate): auth-service cpu_pct: baseline 30.15 -> window mean 55.05 (max 86.3, change 82.6%), onset 2026-10-02T19:55:00Z
- [OBSERVED EVIDENCE] `met-user-service-cpu_pct-1930-2025` (moderate): user-service cpu_pct: baseline 29.56 -> window mean 48.83 (max 71.04, change 65.2%), onset 2026-10-02T19:56:00Z
- [OBSERVED EVIDENCE] `logpat-api-gateway-8a499a8e` (moderate): 9x WARN on api-gateway: '429 Too Many Requests returned to client 58' (first 2026-10-02T19:56:06Z, last 2026-10-02T20:21:50Z)
- [OBSERVED EVIDENCE] `met-api-gateway-error_rate-1930-2025` (moderate): api-gateway error_rate: baseline 0.51 -> window mean 3.86 (max 7.6, change 664.0%), onset 2026-10-02T19:56:00Z
- [OBSERVED EVIDENCE] `met-notification-service-request_rate-1930-2025` (weak): notification-service request_rate: baseline 148.16 -> window mean 149.34 (max 162.31, change 0.8%), onset none detected

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-user-service-error_rate-1930-2025` (weak): user-service error_rate: baseline 0.4 -> window mean 0.4 (max 0.43, change -0.5%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Caller-level breakdown of api-gateway traffic (order-service, payment-service, external clients).
- [UNKNOWN] Identity of the high-volume client IDs in the 429 logs.
- [UNKNOWN] Endpoint-level request breakdown.
- [UNKNOWN] Whether the traffic is organic (e.g. a campaign or batch job) or a retry storm.
- [UNKNOWN] Status-code breakdown of the gateway ~7% error rate.

### 2. H2 - `deployment_regression` in `user-service` (confidence 0.00, critic: reject)
**INFERENCE:** The user-service 7.1.3 release (19:48Z) changed client-facing call behaviour (extra calls per request or a retry loop) that roughly doubled user-service load, which then propagated CPU and latency pressure to callers. Mechanism: 7.1.3 deploy at 19:48Z -> user-service issues extra or retried calls -> user-service request rate doubles at 19:55Z -> user-service CPU and p95 latency rise at 19:56Z -> callers (api-gateway, auth-service) see higher latency and load -> gateway 429s and errors.

Confidence breakdown: base 0.10; +0.08 corroboration across >=2 independent source types; +0.40 supporting evidence (4 refs, reliability-weighted, capped); -0.45 contradicting evidence (4 refs, capped 0.45); +0.08 proposed cause (19:48) precedes/coincides with first observed anomaly (19:55); -0.06 3 acknowledged evidence gaps; -0.40 critic review adjustment; = 0.00 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [CONFIRMED FACT] `dep-78c036fc` (moderate): Deployment of user-service 7.1.2->7.1.3 at 2026-10-02T19:48:00Z (SUCCEEDED): Copy changes on profile page
- [OBSERVED EVIDENCE] `met-user-service-request_rate-1930-2025` (moderate): user-service request_rate: baseline 500.78 -> window mean 1124.49 (max 1838.14, change 124.5%), onset 2026-10-02T19:55:00Z
- [OBSERVED EVIDENCE] `met-user-service-p95_latency_ms-1930-2025` (weak): user-service p95_latency_ms: baseline 81.02 -> window mean 398.41 (max 746.4, change 391.7%), onset 2026-10-02T19:56:00Z
- [OBSERVED EVIDENCE] `met-user-service-cpu_pct-1930-2025` (weak): user-service cpu_pct: baseline 29.56 -> window mean 48.83 (max 71.04, change 65.2%), onset 2026-10-02T19:56:00Z

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-api-gateway-request_rate-1930-2025` (strong): api-gateway request_rate: baseline 1195.01 -> window mean 2732.17 (max 4529.1, change 128.6%), onset 2026-10-02T19:55:00Z
- [OBSERVED EVIDENCE] `met-auth-service-request_rate-1930-2025` (strong): auth-service request_rate: baseline 903.83 -> window mean 2016.93 (max 3257.22, change 123.2%), onset 2026-10-02T19:55:00Z
- [CONFIRMED FACT] `dep-78c036fc` (moderate): Deployment of user-service 7.1.2->7.1.3 at 2026-10-02T19:48:00Z (SUCCEEDED): Copy changes on profile page
- [CONFIRMED FACT] `topo-auth-service-both-d2` (moderate): auth-service depends on ['postgres', 'redis']; called by ['api-gateway', 'payment-service'] (graph topology-v2)

Remaining uncertainties / missing evidence:
- [UNKNOWN] 7.1.3 code diff and feature flags.
- [UNKNOWN] Per-endpoint call counts from user-service to its callers, before and after 19:48Z.
- [UNKNOWN] Whether notification-service or api-gateway changed call patterns to user-service.

### 3. H3 - `resource_saturation` in `postgres` (confidence 0.00, critic: reject)
**INFERENCE:** Sporadic long report_rollup() queries on postgres (11-18 s) consumed shared resources and slowed dependent services, with the traffic step arriving as a secondary effect. Mechanism: report_rollup() long-running statements (first 19:35Z) -> intermittent contention on postgres -> slower responses from user/auth -> callers retry, increasing load and latency.

Confidence breakdown: base 0.10; +0.12 supporting evidence (1 refs, reliability-weighted, capped); -0.45 contradicting evidence (5 refs, capped 0.45); +0.08 proposed cause (19:35) precedes/coincides with first observed anomaly (19:55); -0.04 2 acknowledged evidence gaps; -0.40 critic review adjustment; = 0.00 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-postgres-44883ca5` (moderate): 5x WARN on postgres: 'duration: 14702 ms statement: SELECT report_rollup()' (first 2026-10-02T19:35:44Z, last 2026-10-02T20:24:30Z)

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-postgres-cpu_pct-1930-2025` (strong): postgres cpu_pct: baseline 34.91 -> window mean 35.19 (max 39.9, change 0.8%), onset none detected
- [OBSERVED EVIDENCE] `met-postgres-db_conn_util_pct-1930-2025` (strong): postgres db_conn_util_pct: baseline 40.16 -> window mean 39.85 (max 44.41, change -0.8%), onset none detected
- [OBSERVED EVIDENCE] `met-postgres-p95_latency_ms-1930-2025` (strong): postgres p95_latency_ms: baseline 12.01 -> window mean 11.92 (max 13.01, change -0.8%), onset none detected
- [OBSERVED EVIDENCE] `met-user-service-db_conn_util_pct-1930-2025` (moderate): user-service db_conn_util_pct: baseline 30.04 -> window mean 30.17 (max 33.21, change 0.4%), onset none detected
- [OBSERVED EVIDENCE] `met-user-service-request_rate-1930-2025` (weak): user-service request_rate: baseline 500.78 -> window mean 1124.49 (max 1838.14, change 124.5%), onset 2026-10-02T19:55:00Z

Remaining uncertainties / missing evidence:
- [UNKNOWN] postgres timeouts and pool wait metrics.
- [UNKNOWN] Which callers invoke report_rollup() and at what frequency.

## Critic Review
- **Verdict:** `APPROVED` (rounds reviewed: 1)
- **Reasoning:** H1 (traffic surge entering api-gateway from 19:55Z, with gateway rate-limiting producing 429s) is well supported and the open question in its missing_evidence is now largely answered. Gateway logs identify the source: client_id=mobile-ios-7.4.0 is the top client, rising from ~1700 rps to ~9500 rps, and the rate limiter reports that 363-396% of its requests are retries with Retry-After ignored. This is a client-side retry storm that starts at 19:55:11Z, before the first 429 at 19:56:06Z. The gateway ingress, auth-service, and user-service steps all fall in the same 19:55Z bucket, which fits propagation from the ingress. Refinement: the culprit is the mobile-ios-7.4.0 client population's retry behaviour, not a service in the platform, so the culprit_service label 'api-gateway' should be read as the ingress where the surge lands. H2 is rejected: the 7.1.3 deploy at 19:48Z is the only deployment in the window and is a copy-only change. The gateway ingress rose by the same amount, and auth-service has no dependency on user-service, so user-service cannot be the source of the step. H3 is rejected: postgres CPU, connections, and p95 are flat, and payment and order request rates are flat, so they do not show the surge. Remaining limitations: what triggered the mobile-ios-7.4.0 retries (client release, upstream error, or other) is not established, and the 7% gateway error rate is not broken down by status code. Neither blocks the category or culprit conclusion.
- H1: **accept** - Gateway logs name the source of the step: client_id=mobile-ios-7.4.0, 1700 rps rising to 9500 rps, with 363-396% retries and Retry-After ignored, starting 19:55:11Z before the first 429 at 19:56:06Z. The ingress, auth, and user steps share the 19:55Z bucket. Notification and payment are flat, and postgres is flat. The surge is a client-side retry storm; the 'api-gateway' culprit label is the ingress where it lands.
- H2: **reject** - The 7.1.3 deploy at 19:48Z is copy-only and is the only deployment in the window. The ingress rate, which a user-service change cannot raise, steps up by the same amount. auth-service has no dependency on user-service, and its rise is unexplained by this hypothesis.
- H3: **reject** - postgres CPU, db connection utilisation, and p95 latency are all flat versus baseline. user-service DB connections are unchanged. The only support is a log pattern of long report_rollup statements, which does not match the metric picture. Payment and order traffic are also flat.
- pre-check warning `single_source` on H3: all support comes from one source type (log)
- alternative: What triggered the mobile-ios-7.4.0 retry storm (client release, upstream error, or other) is unestablished. This is a deeper trigger and does not change the category.
- alternative: The 7% gateway error rate may include non-429 errors; a status-code breakdown would confirm that 429s account for it.

## Probable Root Cause
ROOT CAUSE IDENTIFIED (critic-approved; still an INFERENCE from evidence): traffic_surge in api-gateway - An unidentified upstream caller or client population increased request volume into api-gateway at ~19:55Z (about 2.3x). The extra load propagated to auth-service and user-service, saturating their CPU and raising p95 latency. The gateway then rate-limited some clients, producing 429s and the error-rate rise.

## Corrective Actions
- Reduce the inbound retry load from the mobile-ios-7.4.0 client population: apply per-client throttling or temporary rate limits that honor Retry-After, and confirm 429 rates fall (logpat-api-gateway-8a499a8e).
- Engage the mobile team to identify whether a recent 7.4.0 client build or an upstream error is driving retries, and ship a fix or server-side override if one is found.
- Monitor auth-service and user-service CPU and p95 latency until they return to baseline (about 30% CPU and about 81 ms p95) after throttling takes effect.

## Preventive Actions
- Enforce client-side exponential backoff with jitter and Retry-After compliance in mobile SDKs, and verify compliance in pre-release testing for client versions.
- Add gateway-level retry budgets and per-client quotas so a single client population cannot saturate downstream auth and user services.
- Set capacity headroom or autoscaling for auth-service and user-service so a roughly 2.3x ingress increase does not drive CPU above about 85%.
- Add client_id and version as dimensions in gateway request metrics to speed up attribution in future incidents.

## Monitoring Recommendations
- Alert when api-gateway request_rate exceeds 1.5x its 7-day baseline for more than 2 minutes, and when any single client_id exceeds 2x its own baseline.
- Alert on the gateway 429 count and the ratio of retried requests (retries per original request above 1.5 with Retry-After ignored).
- Alert on gateway error_rate above 1% for 5 minutes, and break down errors by status code to confirm the 429 share of the 7% peak.
- Alert on auth-service and user-service CPU above 70% and p95 latency above 3x baseline, with dashboards that show the request rate step alongside them.
- Track postgres CPU, connection utilization, and p95 latency as a control signal to confirm the database is not contributing.

## Evidence Gaps
- none recorded

## Limitations
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: critic verdict APPROVED

## Final Status
`ROOT_CAUSE_IDENTIFIED`

The most probable root cause is a traffic surge at the api-gateway ingress, driven by retry behavior from the mobile-ios-7.4.0 client population beginning at 19:55Z. This surge saturated auth-service and user-service and led the gateway to return 429s. The user-service 7.1.3 deployment and the postgres report_rollup queries were ruled out. The trigger for the client retry storm is not established, and the status-code breakdown of the gateway error rate is still needed to fully confirm that 429s account for the increase. These gaps do not change the category or culprit conclusion, and follow-up work should focus on the client trigger and on preventing retry storms from saturating downstream services.

## Execution Statistics
```json
{
  "rounds": 1,
  "tool_calls": 22,
  "tool_failures": 0,
  "tool_retries": 0,
  "partial_results": 0,
  "agent_failures": 1,
  "agent_retries": 1,
  "invalid_llm_outputs": 3,
  "messages_exchanged": 17,
  "evidence_records": 70,
  "duration_s": 82.65,
  "tokens": {
    "input_tokens": 50,
    "output_tokens": 25700,
    "cache_read_tokens": 36087,
    "cache_write_tokens": 60447,
    "llm_calls": 16,
    "cost_usd": 0.020771744999999998
  },
  "tokens_by_agent": {
    "orchestrator": {
      "input_tokens": 6,
      "output_tokens": 1213,
      "cache_read_tokens": 1327,
      "cache_write_tokens": 2532,
      "llm_calls": 2,
      "cost_usd": 0.00093687
    },
    "dependency": {
      "input_tokens": 8,
      "output_tokens": 2527,
      "cache_read_tokens": 7254,
      "cache_write_tokens": 5564,
      "llm_calls": 3,
      "cost_usd": 0.0020323399999999997
    },
    "observability": {
      "input_tokens": 12,
      "output_tokens": 7736,
      "cache_read_tokens": 5768,
      "cache_write_tokens": 21100,
      "llm_calls": 4,
      "cost_usd": 0.00656438
    },
    "reasoning": {
      "input_tokens": 4,
      "output_tokens": 4610,
      "cache_read_tokens": 0,
      "cache_write_tokens": 11758,
      "llm_calls": 1,
      "cost_usd": 0.00377515
    },
    "critic": {
      "input_tokens": 6,
      "output_tokens": 2660,
      "cache_read_tokens": 8272,
      "cache_write_tokens": 11907,
      "llm_calls": 2,
      "cost_usd": 0.002901695
    },
    "reporting": {
      "input_tokens": 14,
      "output_tokens": 6954,
      "cache_read_tokens": 13466,
      "cache_write_tokens": 7586,
      "llm_calls": 4,
      "cost_usd": 0.00456131
    }
  }
}
```
