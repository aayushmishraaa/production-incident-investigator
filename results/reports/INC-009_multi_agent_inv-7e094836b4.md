# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-009
- **Title:** User API errors during morning peak
- **Severity:** SEV2
- **Affected services:** api-gateway, user-service
- **Start time:** 2026-09-26T08:00:00+00:00
- **Investigation ID:** inv-7e094836b4 (multi_agent)
- **Final status:** `ROOT_CAUSE_IDENTIFIED`

## Executive Summary
INC-009 (SEV2) caused elevated errors on user endpoints (GET /v1/users/{id}) affecting api-gateway and user-service, starting around 08:00Z on 2026-09-26. Final status is ROOT_CAUSE_IDENTIFIED with a leading hypothesis of a deployment regression, with confidence 0.68. The most probable explanation is that the user-service 7.2.0 release (ORM batch-loader switch, dep-c02e51b7), which completed at 07:56Z, introduced an application-level NullPointerException in ProfileBatchLoader.load. The first such error (logpat-user-service-2347725d) appeared at 07:57:17Z. user-service error rate rose from about 0.4% to about 23% and p95 latency rose from about 80 ms to about 670 ms (met-user-service-error_rate-0730-0825, met-user-service-p95_latency_ms-0730-0825). api-gateway forwarded these 500s to clients, with its error rate rising from about 0.5% to about 8% and the first gateway WARN at 08:00:08Z (logpat-api-gateway-c1d874f7). Database connection utilisation, CPU, and request rate stayed flat, which fits an exception-path fault rather than resource saturation. The postgres report_rollup slow-query hypothesis (H2) and the untracked-trigger hypothesis (H3) were both rejected.

## Incident Timeline
| Time (UTC) | Label | Event | Evidence |
|---|---|---|---|
| 2026-09-26T07:33:45Z | OBSERVED EVIDENCE | First log: 4x WARN on order-service: 'Inventory reservation retry for sku-69' (first 2026-09-26T07:33:45Z, last 2026-09-26T08:13:33Z) | logpat-order-service-95abd1bb |
| 2026-09-26T07:35:17Z | OBSERVED EVIDENCE | First log: 6x WARN on auth-service: 'Login rate limit hit for user id u-78' (first 2026-09-26T07:35:17Z, last 2026-09-26T08:23:33Z) | logpat-auth-service-cc8d3b87 |
| 2026-09-26T07:35:24Z | OBSERVED EVIDENCE | First log: 3x WARN on api-gateway: 'Slow client upload from 10.4.53.12 (1.9MB)' (first 2026-09-26T07:35:24Z, last 2026-09-26T08:17:53Z) | logpat-api-gateway-88b04940 |
| 2026-09-26T07:36:46Z | OBSERVED EVIDENCE | First log: 4x WARN on postgres: 'duration: 18302 ms statement: SELECT report_rollup()' (first 2026-09-26T07:36:46Z, last 2026-09-26T08:21:19Z) | logpat-postgres-44883ca5 |
| 2026-09-26T07:56:00Z | CONFIRMED FACT | Deployment of user-service 7.1.3->7.2.0 at 2026-09-26T07:56:00Z (SUCCEEDED): Switch ORM to batch loader | dep-c02e51b7 |
| 2026-09-26T07:57:00Z | OBSERVED EVIDENCE | Anomaly onset: user-service p95_latency_ms: baseline 80.09 -> window mean 383.28 (max 748.48, change 378.5%), onset 2026-09-26T07:57:00Z | met-user-service-p95_latency_ms-0730-0825 |
| 2026-09-26T07:57:00Z | OBSERVED EVIDENCE | Anomaly onset: user-service error_rate: baseline 0.41 -> window mean 12.5 (max 26.11, change 2984.9%), onset 2026-09-26T07:57:00Z | met-user-service-error_rate-0730-0825 |
| 2026-09-26T07:57:00Z | OBSERVED EVIDENCE | Anomaly onset: api-gateway error_rate: baseline 0.5 -> window mean 4.25 (max 8.65, change 747.7%), onset 2026-09-26T07:57:00Z | met-api-gateway-error_rate-0730-0825 |
| 2026-09-26T07:57:17Z | OBSERVED EVIDENCE | First log: 10x ERROR on user-service: 'NullPointerException in ProfileBatchLoader.load (user-service v7.2.0) req 18' (first 2026-09-26T07:57:17Z, last 2026-09-26T08:23:59Z) | logpat-user-service-2347725d |
| 2026-09-26T08:00:00Z | CONFIRMED FACT | Reported symptom start |  |
| 2026-09-26T08:00:08Z | OBSERVED EVIDENCE | First log: 3x WARN on api-gateway: 'user-service returned 500 for GET /v1/users/23' (first 2026-09-26T08:00:08Z, last 2026-09-26T08:22:09Z) | logpat-api-gateway-c1d874f7 |
| 2026-09-26T08:06:00Z | CONFIRMED FACT | Incident reported |  |
| 2026-09-26T08:11:08Z | OBSERVED EVIDENCE | First log: 3x WARN on user-service: 'Deprecated API /v1/users/legacy called by client web-54' (first 2026-09-26T08:11:08Z, last 2026-09-26T08:23:14Z) | logpat-user-service-742b555e |

## Observed Symptoms
- **OBSERVED EVIDENCE:** user-service p95_latency_ms: baseline 80.09 -> window mean 383.28 (max 748.48, change 378.5%), onset 2026-09-26T07:57:00Z (met-user-service-p95_latency_ms-0730-0825)
- **OBSERVED EVIDENCE:** user-service error_rate: baseline 0.41 -> window mean 12.5 (max 26.11, change 2984.9%), onset 2026-09-26T07:57:00Z (met-user-service-error_rate-0730-0825)
- **OBSERVED EVIDENCE:** api-gateway error_rate: baseline 0.5 -> window mean 4.25 (max 8.65, change 747.7%), onset 2026-09-26T07:57:00Z (met-api-gateway-error_rate-0730-0825)
- **OBSERVED EVIDENCE:** [dependency] user-service deployed 7.1.3 -> 7.2.0 (ci-pipeline, status SUCCEEDED, change: 'Switch ORM to batch loader') at 07:56Z, about 4 minutes before T0 and 1 minute before the metric onset. (dep-c02e51b7)
- **OBSERVED EVIDENCE:** [dependency] user-service p95 latency rose from ~80 ms baseline to ~383 ms window mean (max 748 ms), onset 07:57Z; sampled 07:55 = 72.6 ms, 08:00 = 668.8 ms. Step change aligned with the deployment. (met-user-service-p95_latency_ms-0730-0825)
- **OBSERVED EVIDENCE:** [dependency] user-service error_rate rose from ~0.41% baseline to ~12.5% window mean (max 26%), onset 07:57Z; sampled 07:55 = 0.41%, 08:00 = 22.8%. Error step is aligned with the deployment timing. (met-user-service-error_rate-0730-0825)
- **OBSERVED EVIDENCE:** [dependency] user-service db_conn_util_pct (~30% vs ~29.75% baseline) and request_rate (~499 vs ~494 rps, +1%) did not change materially; no onset detected. Latency/error change is not explained by load or DB connection pool saturation. (met-user-service-db_conn_util_pct-0730-0825, met-user-service-request_rate-0730-0825)
- **OBSERVED EVIDENCE:** [dependency] Topology topology-v2 (effective 2026-09-15) added edge notification-service -> user-service. user-service upstream = postgres, redis; downstream dependents = api-gateway, notification-service, order-service. The edge dates from 2026-09-15, so it does not coincide with the 07:56 change. (topo-user-service-both-d2)
- **OBSERVED EVIDENCE:** [observability] Postgres CPU, memory, DB connection utilisation, p95 latency, error rate and disk IO wait were flat across 07:30-08:25 versus the 07:00-07:30 baseline (CPU 34.9% vs 35.0%, conn util 40.0% vs 40.1%, p95 ~12 ms vs ~12 ms). No onset detected for any metric. (met-postgres-cpu_pct-0730-0825, met-postgres-memory_pct-0730-0825, met-postgres-db_conn_util_pct-0730-0825, met-postgres-p95_latency_ms-0730-0825, met-postgres-error_rate-0730-0825, met-postgres-disk_io_wait_ms-0730-0825)
- **OBSERVED EVIDENCE:** [observability] Postgres logged 4 slow-statement WARNs for SELECT report_rollup() (e.g. duration 18302 ms), first at 07:36:46Z and last at 08:21:19Z. (logpat-postgres-44883ca5, log-aac4fdaa)
- **OBSERVED EVIDENCE:** [observability] Redis CPU, memory, p95 latency, cache hit rate (~95%) and error rate were stable versus baseline across the window; no evictions metric was returned. timeout_rate is not collected for redis. (met-redis-cpu_pct-0730-0825, met-redis-memory_pct-0730-0825, met-redis-p95_latency_ms-0730-0825, met-redis-cache_hit_rate-0730-0825, met-redis-error_rate-0730-0825)
- **OBSERVED EVIDENCE:** [observability] notification-service request rate (~151 vs ~150 rps), error rate (0.2%), timeout rate (0.05%) and p95 latency (~90 ms) were unchanged versus baseline; no onset detected. (met-notification-service-request_rate-0730-0825, met-notification-service-error_rate-0730-0825, met-notification-service-timeout_rate-0730-0825, met-notification-service-p95_latency_ms-0730-0825)
- **OBSERVED EVIDENCE:** [observability] user-service ERROR pattern 'NullPointerException in ProfileBatchLoader.load' (v7.2.0) occurred 10 times between 07:57:17Z and 08:23:59Z. This is outside the dependency scope but is the only user-service ERROR pattern in the window. (logpat-user-service-2347725d, log-47ccff14, log-500260ae)
- **OBSERVED EVIDENCE:** [observability] api-gateway WARN 'user-service returned 500 for GET /v1/users/...' occurred 3 times, first at 08:00:08Z and last at 08:15:46Z, coinciding with the reported T0. (logpat-api-gateway-c1d874f7)
- **OBSERVED EVIDENCE:** [dependency] user-service error_rate rose from baseline mean 0.41% to window mean 12.5% (max 26.1%), with onset at 07:57Z; the 5-min series steps from 0.41% at 07:55 to 22.8% at 08:00 and stays 22-26% through 08:25. (met-user-service-error_rate-0730-0825)
- **OBSERVED EVIDENCE:** [dependency] api-gateway error_rate rose from baseline 0.5% to window mean 4.25% (max 8.65%), onset 07:57Z, step to ~7.8% at 08:00 and persisting. api-gateway p99 latency and timeout_rate were unchanged. (met-api-gateway-error_rate-0730-0825, met-api-gateway-p99_latency_ms-0730-0825, met-api-gateway-timeout_rate-0730-0825)
- **OBSERVED EVIDENCE:** [dependency] Deployment dep-c02e51b7 (user-service 7.1.3 -> 7.2.0, 'Switch ORM to batch loader', ci-pipeline, SUCCEEDED) completed at 07:56Z, about 1 minute before the error-rate onset at 07:57Z and 4 minutes before the T0 symptom time. (dep-c02e51b7)
- **OBSERVED EVIDENCE:** [dependency] user-service p99 latency (159.8 vs 158.7 ms), DB connection utilisation (30.2% vs 29.8%) and timeout_rate (0.05% flat) showed no change in the window, so the error increase is not accompanied by latency, DB pool saturation, or timeouts. (met-user-service-p99_latency_ms-0730-0825, met-user-service-db_conn_util_pct-0730-0825, met-user-service-timeout_rate-0730-0825)
- **OBSERVED EVIDENCE:** [dependency] order-service (a downstream dependent of user-service) showed no change: error_rate 0.6% vs 0.6%, p99 401 ms vs 402 ms, timeout 0.1% flat. (met-order-service-error_rate-0730-0825, met-order-service-p99_latency_ms-0730-0825, met-order-service-timeout_rate-0730-0825)
- **OBSERVED EVIDENCE:** [dependency] payment-service showed no change: error_rate 0.8% flat, p99 300 ms flat, timeout 0.1% flat. payment-service is not in user-service's dependency graph. (met-payment-service-error_rate-0730-0825, met-payment-service-p99_latency_ms-0730-0825, met-payment-service-timeout_rate-0730-0825)
- **OBSERVED EVIDENCE:** [dependency] auth-service showed no change: error_rate 0.3% (-0.9%), p99 90 ms (+1.6%), timeout 0.05% flat. auth-service is not in user-service's dependency graph. (met-auth-service-error_rate-0730-0825, met-auth-service-p99_latency_ms-0730-0825, met-auth-service-timeout_rate-0730-0825)
- **OBSERVED EVIDENCE:** [dependency] Dependency graph (topology-v2): user-service upstream = postgres, redis; downstream dependents = api-gateway, notification-service, order-service. The only topology change listed is notification-service -> user-service added effective 2026-09-15 (not recent). auth-service and payment-service do not appear in the user-service neighbourhood. (topo-user-service-both-d3)
- **OBSERVED EVIDENCE:** [dependency] No config changes matched the 07:00-08:30Z window for any service, and the only deployment in that window across services is dep-c02e51b7 (user-service). (dep-c02e51b7)
- **OBSERVED EVIDENCE:** [observability] user-service error_rate onset at 07:57Z (baseline mean 0.41% -> window mean 12.5%, max 26.11%); sampled series jumps from ~0.41% at 07:55 to ~22.8% at 08:00 and stays 22-26% through 08:25. (met-user-service-error_rate-0730-0825)
- **OBSERVED EVIDENCE:** [observability] user-service p95 latency onset 07:57Z: baseline mean 80ms -> window mean 383ms (max 748ms); sampled p95 ~73ms at 07:55 then ~669-727ms from 08:00 to 08:25. p99 is essentially unchanged (158.7ms -> 159.8ms). (met-user-service-p95_latency_ms-0730-0825, met-user-service-p99_latency_ms-0730-0825)
- **ASSUMPTION:** [critic: unsupported assumption] That the NPE count is zero before 07:57:17Z across all logs (log query was partial). 
- **ASSUMPTION:** [critic: unsupported assumption] That all user-service instances run 7.2.0 (no version breakdown was checked). 
- **ASSUMPTION:** [critic: unsupported assumption] That order-service avoids the failing path (not verified). 

## Investigation Performed
- Round 1 | observability | completed | attempts 1 | 6 tool calls | Characterize error rate, latency, and traffic for api-gateway and user-service from 07:30Z to present; identify when errors begin relative to 08:00Z and which u
- Round 1 | observability | completed | attempts 1 | 4 tool calls | Check health of user-service dependencies (postgres, redis) and the notification-service caller for CPU, memory, connections, slow queries, cache evictions, and
- Round 1 | dependency | completed | attempts 1 | 4 tool calls | Identify deployments, config changes, or feature flag changes in the 24 hours before 08:00Z for api-gateway, user-service, notification-service, postgres, and r
- Round 1 | dependency | completed | attempts 1 | 8 tool calls | Map the full downstream blast radius of user-service and api-gateway and confirm which dependent services (order-service, payment-service, auth-service) show co
- Round 1 | reasoning | completed | attempts 1 | 0 tool calls | Develop and rank competing hypotheses
- Round 1 | critic | completed | attempts 1 | 3 tool calls | Independently review hypotheses
- Round 1 | reporting | completed | attempts 1 | 0 tool calls | Write final report

## Root-Cause Hypotheses (ranked by evidence strength)
### 1. H1 - `deployment_regression` in `user-service` (confidence 0.68, critic: accept)
**INFERENCE:** The user-service 7.2.0 release (ORM batch-loader switch, dep-c02e51b7) introduced an application-level fault in ProfileBatchLoader.load that fails a subset of GET /v1/users/{id} requests with 500s, which api-gateway surfaces to clients. Mechanism: Deploy 7.1.3->7.2.0 completes at 07:56Z -> ProfileBatchLoader.load throws NullPointerException on affected requests from 07:57:17Z -> user-service error_rate steps from ~0.4% to ~23% and p95 rises ~80->~670 ms (retries/slow failing paths) -> api-gateway forwards user-service 500s (error_rate 0.5% -> ~8%, first gateway WARN 08:00:08Z) -> users see errors on user endpoints. DB connection utilisation, CPU, request rate and timeouts stay flat, consistent with an exception-path fault rather than resource saturation.

Confidence breakdown: base 0.10; +0.08 corroboration across >=2 independent source types; +0.78 supporting evidence (8 refs, reliability-weighted, capped); -0.20 contradicting evidence (2 refs, capped 0.45); +0.08 proposed cause (07:56) precedes/coincides with first observed anomaly (07:57); -0.05 tool failures/partial data for user-service; -0.08 5 acknowledged evidence gaps; (reliability discount already applied: 0.17); +0.05 critic review adjustment; = 0.68 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [CONFIRMED FACT] `dep-c02e51b7` (strong): Deployment of user-service 7.1.3->7.2.0 at 2026-09-26T07:56:00Z (SUCCEEDED): Switch ORM to batch loader
- [OBSERVED EVIDENCE] `logpat-user-service-2347725d` (strong): 10x ERROR on user-service: 'NullPointerException in ProfileBatchLoader.load (user-service v7.2.0) req 18' (first 2026-09-26T07:57:17Z, last 2026-09-26T08:23:59Z)
- [OBSERVED EVIDENCE] `met-user-service-error_rate-0730-0825` (strong): user-service error_rate: baseline 0.41 -> window mean 12.5 (max 26.11, change 2984.9%), onset 2026-09-26T07:57:00Z
- [OBSERVED EVIDENCE] `met-user-service-p95_latency_ms-0730-0825` (moderate): user-service p95_latency_ms: baseline 80.09 -> window mean 383.28 (max 748.48, change 378.5%), onset 2026-09-26T07:57:00Z
- [OBSERVED EVIDENCE] `met-api-gateway-error_rate-0730-0825` (moderate): api-gateway error_rate: baseline 0.5 -> window mean 4.25 (max 8.65, change 747.7%), onset 2026-09-26T07:57:00Z
- [OBSERVED EVIDENCE] `logpat-api-gateway-c1d874f7` (moderate): 3x WARN on api-gateway: 'user-service returned 500 for GET /v1/users/23' (first 2026-09-26T08:00:08Z, last 2026-09-26T08:22:09Z)
- [OBSERVED EVIDENCE] `met-user-service-db_conn_util_pct-0730-0825` (moderate): user-service db_conn_util_pct: baseline 29.75 -> window mean 30.18 (max 33.82, change 1.4%), onset none detected
- [OBSERVED EVIDENCE] `met-user-service-request_rate-0730-0825` (weak): user-service request_rate: baseline 494.44 -> window mean 499.34 (max 541.07, change 1.0%), onset none detected

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-order-service-error_rate-0730-0825` (moderate): order-service error_rate: baseline 0.6 -> window mean 0.6 (max 0.66, change -0.4%), onset none detected
- [OBSERVED EVIDENCE] `met-user-service-p99_latency_ms-0730-0825` (weak): user-service p99_latency_ms: baseline 158.68 -> window mean 159.8 (max 170.4, change 0.7%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Per-endpoint error breakdown for user-service (only sparse WARN logs for GET /v1/users/*).
- [UNKNOWN] Complete (non-partial) user-service error logs; 14 records were omitted.
- [UNKNOWN] Rollback or canary state of 7.2.0 and whether any instances still run 7.1.3.
- [UNKNOWN] Pre-07:55 baseline of the NPE pattern (confirm zero occurrences before 07:57:17Z).
- [UNKNOWN] Whether the NPE correlates with specific request data (e.g. users with batch-loaded profiles).

### 2. H2 - `upstream_dependency_degradation` in `postgres` (confidence 0.00, critic: reject)
**INFERENCE:** Recurring slow report_rollup() statements on postgres (18+ s) hold locks or connections that intermittently slow or fail user-service queries, producing the user-facing errors. Mechanism: Long-running report_rollup() queries from 07:36Z -> contention (locks / connection hold time) on tables used by user-service -> intermittent user-service request failures -> api-gateway 500s. Would need to explain the step at 07:57Z, which is not explained by this onset.

Confidence breakdown: base 0.10; +0.08 corroboration across >=2 independent source types; +0.18 supporting evidence (2 refs, reliability-weighted, capped); -0.45 contradicting evidence (4 refs, capped 0.45); +0.08 proposed cause (07:36) precedes/coincides with first observed anomaly (07:57); -0.06 3 acknowledged evidence gaps; (reliability discount already applied: 0.06); -0.40 critic review adjustment; = 0.00 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-postgres-44883ca5` (moderate): 4x WARN on postgres: 'duration: 18302 ms statement: SELECT report_rollup()' (first 2026-09-26T07:36:46Z, last 2026-09-26T08:21:19Z)
- [OBSERVED EVIDENCE] `met-postgres-db_conn_util_pct-0730-0825` (weak): postgres db_conn_util_pct: baseline 40.08 -> window mean 40.0 (max 42.77, change -0.2%), onset none detected

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-postgres-p95_latency_ms-0730-0825` (strong): postgres p95_latency_ms: baseline 11.98 -> window mean 12.01 (max 13.12, change 0.2%), onset none detected
- [OBSERVED EVIDENCE] `met-user-service-db_conn_util_pct-0730-0825` (moderate): user-service db_conn_util_pct: baseline 29.75 -> window mean 30.18 (max 33.82, change 1.4%), onset none detected
- [OBSERVED EVIDENCE] `met-user-service-p99_latency_ms-0730-0825` (weak): user-service p99_latency_ms: baseline 158.68 -> window mean 159.8 (max 170.4, change 0.7%), onset none detected
- [OBSERVED EVIDENCE] `met-user-service-error_rate-0730-0825` (moderate): user-service error_rate: baseline 0.41 -> window mean 12.5 (max 26.11, change 2984.9%), onset 2026-09-26T07:57:00Z

Remaining uncertainties / missing evidence:
- [UNKNOWN] Whether report_rollup() touches tables used by user-service paths.
- [UNKNOWN] pg_locks / lock wait data and pg_stat_activity during 07:36-08:25.
- [UNKNOWN] Whether slow statements recur at a frequency that matches user error timing.

### 3. H3 - `unknown` in `user-service` (confidence 0.00, critic: reject)
**INFERENCE:** An untracked configuration, feature-flag, or data-driven trigger in user-service (or a dependency it reads) started near 07:57Z and causes the failures; the 7.2.0 deploy is coincident rather than causal. Mechanism: Untracked flag/config or data change -> user-service requests on a code path fail -> user-service 500s -> api-gateway 500s. Would explain the step at 07:57Z and the lack of order-service impact if only specific endpoints/data are affected.

Confidence breakdown: base 0.10; +0.16 supporting evidence (2 refs, reliability-weighted, capped); -0.12 contradicting evidence (2 refs, capped 0.45); +0.08 proposed cause (07:57) precedes/coincides with first observed anomaly (07:57); -0.05 tool failures/partial data for user-service; -0.06 3 acknowledged evidence gaps; -0.40 critic review adjustment; = 0.00 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [OBSERVED EVIDENCE] `met-user-service-error_rate-0730-0825` (moderate): user-service error_rate: baseline 0.41 -> window mean 12.5 (max 26.11, change 2984.9%), onset 2026-09-26T07:57:00Z
- [OBSERVED EVIDENCE] `met-order-service-error_rate-0730-0825` (weak): order-service error_rate: baseline 0.6 -> window mean 0.6 (max 0.66, change -0.4%), onset none detected

Contradicting evidence:
- [OBSERVED EVIDENCE] `logpat-user-service-2347725d` (moderate): 10x ERROR on user-service: 'NullPointerException in ProfileBatchLoader.load (user-service v7.2.0) req 18' (first 2026-09-26T07:57:17Z, last 2026-09-26T08:23:59Z)
- [CONFIRMED FACT] `dep-c02e51b7` (weak): Deployment of user-service 7.1.3->7.2.0 at 2026-09-26T07:56:00Z (SUCCEEDED): Switch ORM to batch loader

Remaining uncertainties / missing evidence:
- [UNKNOWN] Feature flag and runtime config state for user-service (config query may not track these).
- [UNKNOWN] Data-level changes (profile data, batch sizes) around 07:57Z.
- [UNKNOWN] Instance-level restarts or infrastructure events.

## Critic Review
- **Verdict:** `APPROVED` (rounds reviewed: 1)
- **Reasoning:** H1 (user-service 7.2.0 application fault in ProfileBatchLoader.load) is supported by independent sources that agree on timing. The deploy completed at 07:56Z. The first NPE (tagged v7.2.0) is at 07:57:17Z, and no earlier NPE appears in the 07:30-08:30 query. The user-service error_rate steps from about 0.41% (07:55 sample) to 22.8% (08:00 sample) and p95 steps from about 72-86 ms to about 670 ms. Gateway 500s for user-service start at 08:00:08Z. Metrics for postgres (p95, connections), user-service DB connections, CPU/request rate, and p99 stay flat, which fits an exception-path fault rather than resource saturation. Caveats: the log query was PARTIAL, so the "no NPE before 07:57" claim rests on the records returned, not on complete coverage. There is no per-version or per-endpoint breakdown and no rollback/canary check yet. These are limitations, not blockers. The order-service flatness is unexplained but is consistent with a path-specific fault. H2 is rejected: postgres p95 and connection utilisation are flat, and the step at 07:57 is about 21 minutes after the first slow report_rollup, with no matching change in the error pattern. H3 is rejected: the config-change query for 07:00-08:30 returned no changes, and the NPE is explicitly tagged to v7.2.0. Feature flags are not visible to the tools, so that gap is noted.
- H1: **accept** - Deploy at 07:56Z, NPE tagged v7.2.0 from 07:57:17Z with no earlier occurrences in the returned data, and a metric step at 07:57 (error_rate 0.41 to 22.8, p95 80 to 670 ms) that matches. Gateway 500s follow at 08:00:08Z. Resource metrics are flat, consistent with an application fault. Limitation: logs are partial; a rollback or per-version breakdown would strengthen this further.
- H2: **reject** - Postgres p95 (~12 ms) and connection utilisation are flat across the window, and user-service DB connection utilisation is flat too. The first slow report_rollup (07:36Z) precedes the abrupt error step at 07:57 by about 21 minutes with no intervening change. No evidence links report_rollup to user-service tables.
- H3: **reject** - Config-change query for 07:00-08:30 returned no changes. The NPE is explicitly tagged to v7.2.0 in ProfileBatchLoader, so the deploy is the better-supported cause. The only support is a flat order-service metric, which H1 also has to explain. Untracked feature flags remain possible but have no positive evidence.
- pre-check warning `single_source` on H3: all support comes from one source type (metric)
- alternative: Untracked feature-flag or data-driven trigger coinciding with the deploy (not visible to config tools; no positive evidence).
- alternative: report_rollup lock contention (H2), but timing and resource metrics argue against it.

## Probable Root Cause
ROOT CAUSE IDENTIFIED (critic-approved; still an INFERENCE from evidence): deployment_regression in user-service - The user-service 7.2.0 release (ORM batch-loader switch, dep-c02e51b7) introduced an application-level fault in ProfileBatchLoader.load that fails a subset of GET /v1/users/{id} requests with 500s, which api-gateway surfaces to clients.

## Corrective Actions
- Roll back user-service from 7.2.0 to 7.1.3 (the last known-good release) to restore user endpoint availability, then confirm error_rate returns to baseline (~0.4%).
- Verify the rollback by checking that the NullPointerException in ProfileBatchLoader.load (logpat-user-service-2347725d) stops appearing in logs after the rollback time.
- Confirm rollback scope: check that all user-service instances are running 7.1.3, since no per-version breakdown has been checked yet.
- Check api-gateway retry and timeout behaviour during the incident and reduce client-facing 500s if the gateway amplifies failures.

## Preventive Actions
- Fix the null-handling defect in ProfileBatchLoader.load introduced by the batch-loader switch, and add a unit or integration test covering the failing path before re-releasing 7.2.0.
- Gate future releases of user-service with a canary or staged rollout and automated error-rate/p95 comparison against the baseline, so a regression like this is halted before full rollout.
- Add a pre-deploy check for ORM or data-access changes that exercises GET /v1/users/{id} with representative data, including profiles that may produce null batch results.
- Investigate why order-service error rate stayed flat during the incident, to understand whether the failing path is endpoint-specific and whether similar batch-loader code exists elsewhere.

## Monitoring Recommendations
- Alert on user-service error_rate exceeding a threshold above the ~0.4% baseline (for example, >2% over 5 minutes), and on p95 latency above ~200 ms.
- Alert on any new ERROR log pattern containing NullPointerException with ProfileBatchLoader.load, tagged with service version, to detect recurrence immediately after a deploy.
- Add a per-version breakdown (service version tag) for user-service error_rate and latency, so deploy-correlated regressions are visible quickly.
- Monitor api-gateway upstream 500 counts by upstream service and route, with an alert on the first WARN for user-service 500s.
- Keep postgres report_rollup slow-query logging and p95 monitoring in place, to track the separate slow-query observation (logpat-postgres-44883ca5) even though it was rejected as the cause.
- Fix log query coverage gaps for api-gateway and user-service, and ensure metric queries stay within the tool's six-metric limit, so future investigations have complete evidence.

## Evidence Gaps
- [UNKNOWN] query_logs returned incomplete data for all (PARTIAL_DATA)
- [UNKNOWN] query_logs returned incomplete data for service=api-gateway (PARTIAL_DATA)
- [UNKNOWN] query_logs returned incomplete data for service=user-service (PARTIAL_DATA)
- [UNKNOWN] query_metrics failed for service=user-service, metrics=['error_rate', 'p95_latency_ms', 'p99_latency_ms', 'request_rate', 'timeout_rate', 'db_conn_util_pct', 'cache_hit_rate']: metrics: List should have at most 6 items after validation, not 7 (INVALID_QUERY)

## Limitations
- 1 tool calls failed and 4 returned partial data; affected areas are treated as unknown, not healthy.
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: critic verdict APPROVED

## Final Status
`ROOT_CAUSE_IDENTIFIED`

The most probable root cause of INC-009 is the user-service 7.2.0 deployment, which introduced a NullPointerException in ProfileBatchLoader.load. This caused user-facing 500s on GET /v1/users/{id}, which api-gateway surfaced to clients. The timing across the deploy, the first error, the metric step changes, and the gateway errors all agree, and resource metrics stayed flat. This is the most probable explanation, not a fully confirmed one: the log query was partial, no per-version or per-endpoint breakdown was checked, and no rollback or canary test has yet been run. Rolling back to 7.1.3 and confirming recovery is the priority action. The postgres report_rollup and untracked-trigger hypotheses were rejected on timing and evidence.

## Execution Statistics
```json
{
  "rounds": 1,
  "tool_calls": 29,
  "tool_failures": 3,
  "tool_retries": 3,
  "partial_results": 4,
  "agent_failures": 0,
  "agent_retries": 0,
  "invalid_llm_outputs": 2,
  "messages_exchanged": 20,
  "evidence_records": 94,
  "duration_s": 72.9,
  "tokens": {
    "input_tokens": 52,
    "output_tokens": 29224,
    "cache_read_tokens": 53367,
    "cache_write_tokens": 74241,
    "llm_calls": 18,
    "cost_usd": 0.024430995
  },
  "tokens_by_agent": {
    "orchestrator": {
      "input_tokens": 6,
      "output_tokens": 1190,
      "cache_read_tokens": 1318,
      "cache_write_tokens": 2210,
      "llm_calls": 2,
      "cost_usd": 0.00088503
    },
    "dependency": {
      "input_tokens": 16,
      "output_tokens": 10141,
      "cache_read_tokens": 20033,
      "cache_write_tokens": 18302,
      "llm_calls": 6,
      "cost_usd": 0.0075601800000000005
    },
    "observability": {
      "input_tokens": 16,
      "output_tokens": 9838,
      "cache_read_tokens": 23873,
      "cache_write_tokens": 24092,
      "llm_calls": 6,
      "cost_usd": 0.00817083
    },
    "reasoning": {
      "input_tokens": 4,
      "output_tokens": 4175,
      "cache_read_tokens": 0,
      "cache_write_tokens": 14839,
      "llm_calls": 1,
      "cost_usd": 0.003942775
    },
    "critic": {
      "input_tokens": 6,
      "output_tokens": 2202,
      "cache_read_tokens": 8143,
      "cache_write_tokens": 10772,
      "llm_calls": 2,
      "cost_usd": 0.0025295300000000003
    },
    "reporting": {
      "input_tokens": 4,
      "output_tokens": 1678,
      "cache_read_tokens": 0,
      "cache_write_tokens": 4026,
      "llm_calls": 1,
      "cost_usd": 0.0013426500000000001
    }
  }
}
```
