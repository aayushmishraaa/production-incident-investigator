# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-008
- **Title:** Database CPU high and slow user pages
- **Severity:** SEV2
- **Affected services:** postgres, user-service
- **Start time:** 2026-09-23T12:50:00+00:00
- **Investigation ID:** inv-2434a3e056 (multi_agent)
- **Final status:** `INCONCLUSIVE`

## Executive Summary
INC-008 (SEV2) was reported at 12:56Z after a Postgres CPU alarm and slow user profile pages starting around 12:50Z. The investigation is INCONCLUSIVE: the root cause could not be established. No hypothesis reached adequate support. The leading hypothesis is null.

What is established: Redis memory reached its 8G maxmemory limit (allkeys-lru). Memory onset was 12:36Z (met-redis-memory_pct-1225-1250), eviction WARNs began at 12:43:15Z and continued to 12:48:57Z (logpat-redis-4b4f360d), and Redis p95 latency rose from onset 12:44Z (met-redis-p95_latency_ms-1225-1250). Postgres request rate and CPU stepped up at 12:45Z (met-postgres-request_rate-1240-1252, met-postgres-cpu_pct-1240-1250). Redis cache hit rate fell from 12:46Z (met-redis-cache_hit_rate-1225-1250). User-service p95 rose from 12:46Z (met-user-service-p95_latency_ms-1240-1250), with cache-miss fallback WARNs from 12:45:15Z (logpat-user-service-481445ce). Slow users-table SELECTs appeared on Postgres from 12:46:04Z (logpat-postgres-cee9c952).

Competing explanations each have unresolved conflicts. H1 (Redis eviction driving DB load) has a timing problem: the Postgres load step precedes the hit-rate collapse, and the request-rate increase (about 2,400 to 4,000 rps) is far larger than the observed fallback WARNs can explain. H3 (an unidentified independent Postgres client) fits the 12:45 load step but no client was identified, and its premise conflicts with the earlier Redis eviction. H2 (the OPS-2229 profile_v2_cache flag change at 12:10Z) is weakened because Redis memory stayed flat for about 25 minutes after the change and user-service latency was normal until 12:45Z (cfg-b6fe4aaf).

Note on the Postgres request-rate series: the critic flagged that it may be a measurement or aggregation artefact, so the 12:45Z step should be treated as unconfirmed until verified.

## Incident Timeline
| Time (UTC) | Label | Event | Evidence |
|---|---|---|---|
| 2026-09-23T12:10:00Z | CONFIRMED FACT | Config change on user-service: feature.profile_v2_cache false -> true at 2026-09-23T12:10:00Z (OPS-2229) | cfg-b6fe4aaf |
| 2026-09-23T12:23:40Z | OBSERVED EVIDENCE | First log: 7x WARN on user-service: 'Deprecated API /v1/users/legacy called by client web-96' (first 2026-09-23T12:23:40Z, last 2026-09-23T13:12:10Z) | logpat-user-service-742b555e |
| 2026-09-23T12:43:15Z | OBSERVED EVIDENCE | First log: 3x WARN on redis: 'Evicting keys: used_memory 7.970G reached maxmemory 8G (policy allkeys-lru), evicted_keys=1870233' (first 2026-09-23T12:43:15Z, last 2026-09-23T12:48:57Z) | logpat-redis-4b4f360d |
| 2026-09-23T12:44:00Z | OBSERVED EVIDENCE | Anomaly onset: redis p95_latency_ms: baseline 1.49 -> window mean 14.19 (max 27.89, change 851.8%), onset 2026-09-23T12:44:00Z | met-redis-p95_latency_ms-1220-1315 |
| 2026-09-23T12:44:00Z | OBSERVED EVIDENCE | Anomaly onset: redis p95_latency_ms: baseline 1.49 -> window mean 5.94 (max 24.42, change 298.3%), onset 2026-09-23T12:44:00Z | met-redis-p95_latency_ms-1225-1250 |
| 2026-09-23T12:45:00Z | OBSERVED EVIDENCE | Anomaly onset: postgres cpu_pct: baseline 35.46 -> window mean 70.41 (max 96.23, change 98.6%), onset 2026-09-23T12:45:00Z | met-postgres-cpu_pct-1230-1315 |
| 2026-09-23T12:45:00Z | OBSERVED EVIDENCE | Anomaly onset: postgres request_rate: baseline 2496.81 -> window mean 6719.89 (max 10219.4, change 169.1%), onset 2026-09-23T12:45:00Z | met-postgres-request_rate-1230-1315 |
| 2026-09-23T12:45:00Z | OBSERVED EVIDENCE | Anomaly onset: postgres request_rate: baseline 2483.37 -> window mean 4909.69 (max 9171.15, change 97.7%), onset 2026-09-23T12:45:00Z | met-postgres-request_rate-1240-1250 |
| 2026-09-23T12:45:00Z | OBSERVED EVIDENCE | Anomaly onset: postgres cpu_pct: baseline 35.25 -> window mean 55.67 (max 89.58, change 57.9%), onset 2026-09-23T12:45:00Z | met-postgres-cpu_pct-1240-1250 |
| 2026-09-23T12:45:00Z | OBSERVED EVIDENCE | Anomaly onset: postgres request_rate: baseline 2496.81 -> window mean 5599.0 (max 9405.06, change 124.2%), onset 2026-09-23T12:45:00Z | met-postgres-request_rate-1240-1252 |
| 2026-09-23T12:45:00Z | OBSERVED EVIDENCE | Anomaly onset: postgres cpu_pct: baseline 35.46 -> window mean 60.55 (max 90.94, change 70.8%), onset 2026-09-23T12:45:00Z | met-postgres-cpu_pct-1240-1252 |
| 2026-09-23T12:45:15Z | OBSERVED EVIDENCE | First log: 24x WARN on user-service: 'Cache miss for user profile u-79, falling back to DB' (first 2026-09-23T12:45:15Z, last 2026-09-23T13:13:55Z) | logpat-user-service-481445ce |
| 2026-09-23T12:46:00Z | OBSERVED EVIDENCE | Anomaly onset: user-service p95_latency_ms: baseline 79.7 -> window mean 939.95 (max 1972.06, change 1079.3%), onset 2026-09-23T12:46:00Z | met-user-service-p95_latency_ms-1220-1315 |
| 2026-09-23T12:46:00Z | OBSERVED EVIDENCE | Anomaly onset: postgres db_conn_util_pct: baseline 39.95 -> window mean 68.46 (max 96.15, change 71.4%), onset 2026-09-23T12:46:00Z | met-postgres-db_conn_util_pct-1230-1315 |
| 2026-09-23T12:46:00Z | OBSERVED EVIDENCE | Anomaly onset: user-service p95_latency_ms: baseline 79.93 -> window mean 565.42 (max 1972.06, change 607.4%), onset 2026-09-23T12:46:00Z | met-user-service-p95_latency_ms-1240-1250 |
| 2026-09-23T12:46:04Z | OBSERVED EVIDENCE | First log: 9x WARN on postgres: 'duration: 26410 ms statement: SELECT * FROM users WHERE id = $1' (first 2026-09-23T12:46:04Z, last 2026-09-23T13:12:00Z) | logpat-postgres-cee9c952 |
| 2026-09-23T12:47:00Z | OBSERVED EVIDENCE | Anomaly onset: user-service error_rate: baseline 0.4 -> window mean 2.6 (max 5.36, change 558.3%), onset 2026-09-23T12:47:00Z | met-user-service-error_rate-1220-1315 |
| 2026-09-23T12:47:00Z | OBSERVED EVIDENCE | Anomaly onset: user-service error_rate: baseline 0.4 -> window mean 1.22 (max 3.94, change 204.2%), onset 2026-09-23T12:47:00Z | met-user-service-error_rate-1240-1250 |
| 2026-09-23T12:47:12Z | OBSERVED EVIDENCE | First log: 7x ERROR on user-service: 'Query timeout on users table after 2000ms (req 89)' (first 2026-09-23T12:47:12Z, last 2026-09-23T13:11:20Z) | logpat-user-service-f882ebef |
| 2026-09-23T12:50:00Z | CONFIRMED FACT | Reported symptom start |  |
| 2026-09-23T12:56:00Z | CONFIRMED FACT | Incident reported |  |

## Observed Symptoms
- **OBSERVED EVIDENCE:** user-service p95_latency_ms: baseline 79.7 -> window mean 939.95 (max 1972.06, change 1079.3%), onset 2026-09-23T12:46:00Z (met-user-service-p95_latency_ms-1220-1315)
- **OBSERVED EVIDENCE:** user-service error_rate: baseline 0.4 -> window mean 2.6 (max 5.36, change 558.3%), onset 2026-09-23T12:47:00Z (met-user-service-error_rate-1220-1315)
- **OBSERVED EVIDENCE:** postgres cpu_pct: baseline 35.46 -> window mean 70.41 (max 96.23, change 98.6%), onset 2026-09-23T12:45:00Z (met-postgres-cpu_pct-1230-1315)
- **OBSERVED EVIDENCE:** postgres db_conn_util_pct: baseline 39.95 -> window mean 68.46 (max 96.15, change 71.4%), onset 2026-09-23T12:46:00Z (met-postgres-db_conn_util_pct-1230-1315)
- **OBSERVED EVIDENCE:** postgres request_rate: baseline 2496.81 -> window mean 6719.89 (max 10219.4, change 169.1%), onset 2026-09-23T12:45:00Z (met-postgres-request_rate-1230-1315)
- **OBSERVED EVIDENCE:** redis p95_latency_ms: baseline 1.49 -> window mean 14.19 (max 27.89, change 851.8%), onset 2026-09-23T12:44:00Z (met-redis-p95_latency_ms-1220-1315)
- **OBSERVED EVIDENCE:** user-service p95_latency_ms: baseline 79.93 -> window mean 565.42 (max 1972.06, change 607.4%), onset 2026-09-23T12:46:00Z (met-user-service-p95_latency_ms-1240-1250)
- **OBSERVED EVIDENCE:** user-service error_rate: baseline 0.4 -> window mean 1.22 (max 3.94, change 204.2%), onset 2026-09-23T12:47:00Z (met-user-service-error_rate-1240-1250)
- **OBSERVED EVIDENCE:** postgres request_rate: baseline 2483.37 -> window mean 4909.69 (max 9171.15, change 97.7%), onset 2026-09-23T12:45:00Z (met-postgres-request_rate-1240-1250)
- **OBSERVED EVIDENCE:** postgres cpu_pct: baseline 35.25 -> window mean 55.67 (max 89.58, change 57.9%), onset 2026-09-23T12:45:00Z (met-postgres-cpu_pct-1240-1250)
- **OBSERVED EVIDENCE:** redis p95_latency_ms: baseline 1.49 -> window mean 5.94 (max 24.42, change 298.3%), onset 2026-09-23T12:44:00Z (met-redis-p95_latency_ms-1225-1250)
- **OBSERVED EVIDENCE:** postgres request_rate: baseline 2496.81 -> window mean 5599.0 (max 9405.06, change 124.2%), onset 2026-09-23T12:45:00Z (met-postgres-request_rate-1240-1252)
- **OBSERVED EVIDENCE:** postgres cpu_pct: baseline 35.46 -> window mean 60.55 (max 90.94, change 70.8%), onset 2026-09-23T12:45:00Z (met-postgres-cpu_pct-1240-1252)
- **OBSERVED EVIDENCE:** [dependency] Only config change in the 11:00-13:15Z window across all services: user-service feature.profile_v2_cache changed false -> true at 12:10Z (author config-bot, ticket OPS-2229). (cfg-b6fe4aaf)
- **OBSERVED EVIDENCE:** [dependency] Dependency graph (topology-v2): postgres downstream dependents are auth-service, order-service, payment-service, user-service; potentially impacted also api-gateway and notification-service. No topology changes listed. (topo-postgres-downstream-d2)
- **OBSERVED EVIDENCE:** [dependency] user-service p95 latency was ~72-83ms from 11:50-12:45Z, then jumped to ~1972ms at 12:50Z (1962ms at 12:55Z, 1758ms at 13:00Z). Error rate rose from ~0.4% to 3.9% at 12:50Z, 4.8% at 12:55Z, 5.0% at 13:00Z. (met-user-service-p95_latency_ms-1150-1300, met-user-service-error_rate-1150-1300)
- **OBSERVED EVIDENCE:** [dependency] user-service db_conn_util_pct stayed flat at ~28-32% across the whole window, including after the 12:10Z flag flip and at T0; no visible connection-pool change. (met-user-service-db_conn_util_pct-1150-1300)
- **INFERENCE:** [dependency] The OPS-2229 profile_v2_cache enablement at 12:10Z may introduce a new query path or cache-miss pattern that only manifests under load at 12:50Z; needs confirmation via postgres query metrics and user-service cache behaviour (cache_hit_rate not collected for user-service). (cfg-b6fe4aaf)
- **OBSERVED EVIDENCE:** [dependency] Dependency graph (topology-v2) confirms the added edge notification-service -> user-service, effective 2026-09-15T00:00:00Z. user-service's downstream dependents are api-gateway, notification-service and order-service; upstream dependencies are postgres and redis. (topo-user-service-both-d2)
- **OBSERVED EVIDENCE:** [dependency] user-service request_rate was flat across the incident: baseline mean 495.6 rps vs window mean 498.0 rps (+0.5%), with no onset detected. (met-user-service-request_rate-1220-1315)
- **OBSERVED EVIDENCE:** [dependency] notification-service request_rate was flat: baseline mean 149.4 rps vs window mean 149.3 rps (0%). Its p95 latency (+1.3%), error rate and timeout rate also showed no change and no onset. (met-notification-service-request_rate-1220-1315, met-notification-service-p95_latency_ms-1220-1315, met-notification-service-error_rate-1220-1315, met-notification-service-timeout_rate-1220-1315)
- **OBSERVED EVIDENCE:** [dependency] user-service p95 latency jumped from baseline mean 79.7 ms to 940 ms in the window (+1079%); detected onset 2026-09-23T12:46Z (sample 12:50 at 1972 ms). Error rate rose from 0.4% to 2.6% with onset 12:47Z. (met-user-service-p95_latency_ms-1220-1315, met-user-service-error_rate-1220-1315)
- **OBSERVED EVIDENCE:** [dependency] user-service db_conn_util_pct did not change (baseline 30.2% vs window 30.1%), so no connection-pool saturation is visible on the user-service side during the latency rise. (met-user-service-db_conn_util_pct-1220-1315)
- **INFERENCE:** [dependency] The notification->user-service edge could still carry a small, targeted burst (e.g. a specific expensive call pattern) that is hidden in aggregate request rates; aggregate metrics cannot rule this out. (met-notification-service-request_rate-1220-1315, met-user-service-request_rate-1220-1315)
- **OBSERVED EVIDENCE:** [observability] Postgres cpu_pct rose from a baseline mean of 35.46% to a window mean of 70.41% (max 96.23%). Onset detected at 12:45Z; samples were 48.9% at 12:45, 88.5% at 12:50, and 88–95% through 13:15. (met-postgres-cpu_pct-1230-1315)
- **ASSUMPTION:** [critic: unsupported assumption] That cache-miss fallbacks alone generate the 12:45 Postgres load (contradicted by volume) 
- **ASSUMPTION:** [critic: unsupported assumption] That the flag change causes the Redis memory growth (memory flat for ~25 min after the change) 
- **ASSUMPTION:** [critic: unsupported assumption] That an unidentified client exists (no client attribution in logs or topology) 
- **ASSUMPTION:** [critic: unsupported assumption] That the Postgres request_rate series is a valid measure of query volume 

## Investigation Performed
- Round 1 | observability | completed | attempts 1 | 4 tool calls | Characterize Postgres CPU and query behavior from ~12:30Z to now: CPU, active connections, lock waits, slow query volume, and which callers/clients drive the lo
- Round 1 | observability | completed | attempts 1 | 5 tool calls | Measure user-service and redis latency, error rates, and traffic around the symptom start, and check downstream effects on api-gateway and notification-service.
- Round 1 | dependency | completed | attempts 1 | 4 tool calls | Identify deployments, config changes, or feature flags in the window before 12:50Z for postgres and the services that query it.
- Round 1 | dependency | completed | attempts 1 | 3 tool calls | Confirm the notification-service -> user-service edge (added 2026-09-15) and whether new call traffic along it coincides with the incident.
- Round 1 | reasoning | completed | attempts 1 | 0 tool calls | Develop and rank competing hypotheses
- Round 1 | critic | completed | attempts 1 | 5 tool calls | Independently review hypotheses
- Round 2 | observability | completed | attempts 1 | 3 tool calls | FOLLOW-UP requested by critic: Query redis memory_pct, request_rate and key-count/evictions trend for 12:00-12:45Z in finer resolution, and redis logs for any k
- Round 2 | observability | completed | attempts 1 | 4 tool calls | FOLLOW-UP requested by critic: Query user-service and postgres logs/metrics for 12:40-12:50Z to attribute SELECT volume: count cache-miss fallbacks per minute a
- Round 2 | reasoning | completed | attempts 1 | 0 tool calls | Develop and rank competing hypotheses
- Round 2 | critic | completed | attempts 1 | 0 tool calls | Independently review hypotheses
- Round 3 | observability | completed | attempts 1 | 4 tool calls | FOLLOW-UP requested by critic: Per-minute user-service cache-miss WARN counts and user-service users-table query/timeout counts for 12:40-12:52, to compare the 
- Round 3 | observability | completed | attempts 1 | 3 tool calls | FOLLOW-UP requested by critic: Redis memory and eviction timeline at 1-minute resolution from 12:25 to 12:50 (used_memory, maxmemory, evicted_keys, key count if
- Round 3 | dependency | completed | attempts 1 | 9 tool calls | FOLLOW-UP requested by critic: Identify all services with a dependency on postgres users-table reads and check for any other client, job, or batch process that 
- Round 3 | reasoning | completed | attempts 1 | 0 tool calls | Develop and rank competing hypotheses
- Round 3 | critic | completed | attempts 1 | 2 tool calls | Independently review hypotheses
- Round 3 | reporting | completed | attempts 1 | 0 tool calls | Write final report

## Root-Cause Hypotheses (ranked by evidence strength)
### 1. H1 - `cache_degradation` in `redis` (confidence 0.38, critic: needs_evidence)
**INFERENCE:** Redis hit at maxmemory (8G, allkeys-lru) evicted user-profile cache entries, collapsing the cache hit rate and pushing user-profile reads onto the Postgres users table, which saturated Postgres and drove user-service latency and errors. Mechanism: Redis memory climbs from ~60% to 100% of maxmemory (12:30-12:45) with flat request rate -> allkeys-lru eviction starts (12:43:15) -> redis p95 rises (12:44) -> hit rate falls 95% -> 72% (12:45 sample) -> 38% (12:50) -> user-service cache-miss fallbacks and SELECT users by id load on Postgres -> Postgres CPU/connection saturation and 22-30 s single-row lookups -> user-service p95 (12:46) and errors (12:47), DB timeouts (12:47:12).

Confidence breakdown: base 0.10; +0.08 corroboration across >=2 independent source types; +0.78 supporting evidence (7 refs, reliability-weighted, capped); -0.45 contradicting evidence (3 refs, capped 0.45); +0.08 proposed cause (12:36) precedes/coincides with first observed anomaly (12:44); -0.08 4 acknowledged evidence gaps; -0.05 critic review adjustment; = 0.38 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [OBSERVED EVIDENCE] `met-redis-memory_pct-1225-1250` (strong): redis memory_pct: baseline 59.84 -> window mean 83.4 (max 100.0, change 39.4%), onset 2026-09-23T12:36:00Z
- [OBSERVED EVIDENCE] `logpat-redis-4b4f360d` (strong): 3x WARN on redis: 'Evicting keys: used_memory 7.970G reached maxmemory 8G (policy allkeys-lru), evicted_keys=1870233' (first 2026-09-23T12:43:15Z, last 2026-09-23T12:48:57Z)
- [OBSERVED EVIDENCE] `met-redis-p95_latency_ms-1225-1250` (moderate): redis p95_latency_ms: baseline 1.49 -> window mean 5.94 (max 24.42, change 298.3%), onset 2026-09-23T12:44:00Z
- [OBSERVED EVIDENCE] `met-redis-cache_hit_rate-1225-1250` (moderate): redis cache_hit_rate: baseline 95.0 -> window mean 84.07 (max 95.86, change -11.5%), onset 2026-09-23T12:46:00Z
- [OBSERVED EVIDENCE] `logpat-user-service-481445ce` (weak): 24x WARN on user-service: 'Cache miss for user profile u-79, falling back to DB' (first 2026-09-23T12:45:15Z, last 2026-09-23T13:13:55Z)
- [OBSERVED EVIDENCE] `met-redis-request_rate-1225-1250` (moderate): redis request_rate: baseline 6007.51 -> window mean 5950.14 (max 6421.15, change -1.0%), onset none detected
- [OBSERVED EVIDENCE] `met-user-service-p95_latency_ms-1240-1250` (moderate): user-service p95_latency_ms: baseline 79.93 -> window mean 565.42 (max 1972.06, change 607.4%), onset 2026-09-23T12:46:00Z

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-postgres-request_rate-1240-1250` (strong): postgres request_rate: baseline 2483.37 -> window mean 4909.69 (max 9171.15, change 97.7%), onset 2026-09-23T12:45:00Z
- [OBSERVED EVIDENCE] `met-user-service-request_rate-1240-1252` (moderate): user-service request_rate: baseline 495.63 -> window mean 494.91 (max 518.35, change -0.1%), onset none detected
- [OBSERVED EVIDENCE] `met-redis-cache_hit_rate-1220-1315` (weak): redis cache_hit_rate: baseline 95.0 -> window mean 64.46 (max 95.86, change -32.1%), onset 2026-09-23T12:46:00Z

Remaining uncertainties / missing evidence:
- [UNKNOWN] Attribution of extra users-table SELECTs to a caller (pg_stat_statements, application_name)
- [UNKNOWN] user-service cache_hit_rate and per-minute miss counter
- [UNKNOWN] redis key count, used_memory vs maxmemory series at 1-minute resolution, evicted_keys counter
- [UNKNOWN] Redis timeout_rate

### 2. H3 - `resource_saturation` in `postgres` (confidence 0.34, critic: needs_evidence)
**INFERENCE:** An independent Postgres client, not in the dependency graph or not yet identified, began issuing high-volume users-table SELECTs at ~12:45, saturating Postgres CPU and connections. The redis and user-service degradation is a downstream effect. Mechanism: unidentified client (batch, ad-hoc, or retry storm) issues ~2400-4000 extra rps of SELECT * FROM users WHERE id=$1 from 12:45 -> Postgres CPU 35->90% and connection use 40->90% -> 22-30 s lookups -> user-service DB timeouts (12:47) and latency/errors (12:46-12:47); redis fill and hit-rate loss follow as side effects.

Confidence breakdown: base 0.10; +0.08 corroboration across >=2 independent source types; +0.62 supporting evidence (5 refs, reliability-weighted, capped); -0.35 contradicting evidence (3 refs, capped 0.45); +0.08 proposed cause (12:45) precedes/coincides with first observed anomaly (12:44); -0.06 3 acknowledged evidence gaps; -0.05 critic review adjustment; = 0.34 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [OBSERVED EVIDENCE] `met-postgres-request_rate-1240-1252` (strong): postgres request_rate: baseline 2496.81 -> window mean 5599.0 (max 9405.06, change 124.2%), onset 2026-09-23T12:45:00Z
- [OBSERVED EVIDENCE] `met-postgres-cpu_pct-1240-1250` (moderate): postgres cpu_pct: baseline 35.25 -> window mean 55.67 (max 89.58, change 57.9%), onset 2026-09-23T12:45:00Z
- [OBSERVED EVIDENCE] `logpat-postgres-cee9c952` (moderate): 9x WARN on postgres: 'duration: 26410 ms statement: SELECT * FROM users WHERE id = $1' (first 2026-09-23T12:46:04Z, last 2026-09-23T13:12:00Z)
- [OBSERVED EVIDENCE] `met-auth-service-request_rate-1240-1250` (weak): auth-service request_rate: baseline 903.39 -> window mean 906.56 (max 987.02, change 0.4%), onset none detected
- [OBSERVED EVIDENCE] `met-user-service-request_rate-1240-1252` (weak): user-service request_rate: baseline 495.63 -> window mean 494.91 (max 518.35, change -0.1%), onset none detected

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-redis-p95_latency_ms-1225-1250` (moderate): redis p95_latency_ms: baseline 1.49 -> window mean 5.94 (max 24.42, change 298.3%), onset 2026-09-23T12:44:00Z
- [OBSERVED EVIDENCE] `met-postgres-p95_latency_ms-1240-1250` (moderate): postgres p95_latency_ms: baseline 12.02 -> window mean 12.06 (max 13.2, change 0.3%), onset none detected
- [CONFIRMED FACT] `topo-postgres-downstream-d3` (weak): postgres depends on ?; called by ['auth-service', 'order-service', 'payment-service', 'user-service'] (graph topology-v2)

Remaining uncertainties / missing evidence:
- [UNKNOWN] Per-client or per-application breakdown of Postgres connections and queries
- [UNKNOWN] Batch/cron/ad-hoc client inventory for 12:40-12:50
- [UNKNOWN] Lock and wait-event data (pg_locks) for the users table

### 3. H2 - `configuration_regression` in `user-service` (confidence 0.12, critic: needs_evidence)
**INFERENCE:** The OPS-2229 flag profile_v2_cache enabled at 12:10Z stored ~4.1x larger profile payloads in redis. Memory grew slowly until it hit maxmemory around 12:40, triggering eviction and the H1 cascade. Mechanism: profile_v2_cache=true (12:10) -> cached payloads 4.1x larger -> redis key-space bytes grow -> memory crosses ~90% around 12:35-12:40 and reaches maxmemory -> allkeys-lru evicts profile keys -> hit rate collapses -> DB read fallbacks -> Postgres saturation -> user-service latency/errors.

Confidence breakdown: base 0.10; +0.08 corroboration across >=2 independent source types; +0.40 supporting evidence (4 refs, reliability-weighted, capped); -0.35 contradicting evidence (3 refs, capped 0.45); +0.08 proposed cause (12:10) precedes/coincides with first observed anomaly (12:44); -0.06 3 acknowledged evidence gaps; -0.05 critic review adjustment; = 0.12 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [CONFIRMED FACT] `cfg-b6fe4aaf` (moderate): Config change on user-service: feature.profile_v2_cache false -> true at 2026-09-23T12:10:00Z (OPS-2229)
- [OBSERVED EVIDENCE] `logpat-user-service-9d44e354` (moderate): 1x INFO on user-service: 'Feature flag profile_v2_cache enabled (avg cached payload 4.1x larger)' (first 2026-09-23T12:10:00Z, last 2026-09-23T12:10:00Z)
- [OBSERVED EVIDENCE] `met-redis-memory_pct-1150-1225` (weak): redis memory_pct: baseline None -> window mean 59.63 (max 65.88, change None%), onset none detected
- [OBSERVED EVIDENCE] `met-redis-memory_pct-1225-1250` (weak): redis memory_pct: baseline 59.84 -> window mean 83.4 (max 100.0, change 39.4%), onset 2026-09-23T12:36:00Z

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-redis-memory_pct-1150-1225` (moderate): redis memory_pct: baseline None -> window mean 59.63 (max 65.88, change None%), onset none detected
- [OBSERVED EVIDENCE] `met-user-service-p95_latency_ms-1150-1300` (moderate): user-service p95_latency_ms: baseline None -> window mean 395.49 (max 1972.06, change None%), onset none detected
- [OBSERVED EVIDENCE] `met-redis-request_rate-1200-1245` (weak): redis request_rate: baseline 6142.18 -> window mean 5988.78 (max 6758.56, change -2.5%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Key count and bytes by keyspace prefix showing v2 keys dominate memory growth
- [UNKNOWN] redis write counters from user-service
- [UNKNOWN] evicted_keys trend at 1-minute resolution

## Critic Review
- **Verdict:** `INCONCLUSIVE` (rounds reviewed: 3)
- **Reasoning:** No hypothesis is adequately supported. The earliest anomalies are Redis memory reaching maxmemory (onset 12:36), eviction WARNs from 12:43:15, and Redis p95 onset 12:44. Postgres request rate and CPU step up at 12:45, and Redis hit-rate loss (onset 12:46) and user-service p95 (12:46) follow. H1 therefore has a real timing problem: the Postgres load step precedes the hit-rate collapse it is said to cause, and the Postgres request-rate increase (~2400-4000 rps) is far larger than cache-miss fallbacks (about 6 WARNs in 7 minutes) could produce. H2 is weakened by memory staying flat for about 25 minutes after the 12:10 flag change and by user-service latency staying normal until 12:45. H3 explains the 12:45 DB load step but has no identified client: topology lists only four Postgres callers, none of which shows increased traffic, and the Postgres logs show only the slow SELECTs, a checkpoint and an autovacuum on orders, with no client attribution. Its premise also conflicts with the Redis eviction starting earlier. The remaining gap is attribution of the 12:45 surge to a specific client or query source, which the team's tools (logs, metrics, deployments, config, topology) cannot expose. Further queries are unlikely to resolve this within the remaining round.
- H1: **needs_evidence** - Eviction and memory saturation are real and precede the DB surge, but the Postgres request-rate step at 12:45 precedes the hit-rate drop at 12:46 and is far larger than cache-miss volume. The cascade as described cannot account for the DB load.
- H2: **needs_evidence** - The flag change at 12:10 is the only config change, but memory stayed flat for ~25 minutes afterward and user-service latency was normal until 12:45. No key-prefix breakdown links memory growth to v2 keys. Not supported as the leading cause.
- H3: **needs_evidence** - The 12:45 Postgres request surge is the largest unexplained step, and no known caller accounts for it. However, no client is identified, topology does not support an independent client, and the Redis eviction onset precedes it. Unresolved as a candidate.
- alternative: A retry or amplification storm from an existing Postgres client (for example user-service retries on timeouts) that did not increase its primary request rate, so it does not appear in user-service traffic metrics
- alternative: Redis eviction and Postgres load both driven by a common upstream trigger not captured in the collected evidence
- alternative: Measurement or aggregation artefact in the Postgres request_rate series at 12:45

## Probable Root Cause
Root cause could not be conclusively established with the available evidence.

## Corrective Actions
- Immediately relieve Postgres load: identify and throttle or cap the top query sources touching the users table, and consider temporarily raising the Redis maxmemory limit or reducing user-profile cache TTL/payload size to lower eviction pressure (met-redis-memory_pct-1225-1250, logpat-redis-4b4f360d).
- Restore user-profile cache effectiveness: check whether the profile_v2_cache flag (OPS-2229) should be rolled back as a precaution, weighing that H2 is weakly supported (cfg-b6fe4aaf).
- Mitigate the slow SELECT * FROM users WHERE id = $1 pattern (logpat-postgres-cee9c952) with an index check and a temporary query-level timeout, without treating it as the confirmed cause.
- Confirm user-service and Postgres connection pool limits to prevent retry amplification while the source is unknown.

## Preventive Actions
- Capacity-plan Redis maxmemory against the working set of user-profile entries and alert before reaching the limit, not at it.
- Add per-client and per-application attribution for Postgres connections and queries (for example application_name tagging and pg_stat_statements) so an unidentified caller can be identified in future incidents.
- Review the dependency topology to confirm the full list of Postgres clients, since the current topology lists only four callers and none shows increased traffic.
- Establish a staged rollout and payload-size check for cache-affecting feature flags such as profile_v2_cache, including memory-growth monitoring after rollout.

## Monitoring Recommendations
- Alert on Redis used_memory_pct above 80% sustained for 5 minutes, and on evicted_keys rate greater than zero (logpat-redis-4b4f360d).
- Alert on Redis cache_hit_rate dropping more than 5 points below a 95% baseline, and on Redis p95 latency above 3 ms (met-redis-cache_hit_rate-1225-1250, met-redis-p95_latency_ms-1225-1250).
- Track Postgres request rate per client and per query fingerprint, and alert on a step increase over 50% against baseline; validate the request_rate series against pg_stat_statements calls to rule out an artefact (met-postgres-request_rate-1240-1252).
- Alert on Postgres CPU above 70% sustained and on statements exceeding 1000 ms duration (logpat-postgres-cee9c952).
- Alert on user-service p95 latency above 200 ms and on the cache-miss fallback WARN rate (logpat-user-service-481445ce).
- Log the flag state and cache payload size per profile write to test H2 directly (cfg-b6fe4aaf).

## Evidence Gaps
- none recorded

## Limitations
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: critic verdict INCONCLUSIVE

## Final Status
`INCONCLUSIVE`

Root cause could not be conclusively established with the available evidence. The root cause of INC-008 could not be established; the investigation status is INCONCLUSIVE and no leading hypothesis is confirmed. The evidence shows a sequence of Redis memory saturation and eviction (from 12:36Z to 12:43Z), a Postgres load step at 12:45Z, and user-service and Postgres latency increases from 12:46Z. However, the link between these events is not established. Remaining work is to attribute the 12:45Z Postgres surge to a specific client or query source, verify the Postgres request-rate series, and test the flag-driven memory hypothesis directly. Mitigation and evidence-gathering should proceed in parallel.

## Execution Statistics
```json
{
  "rounds": 3,
  "tool_calls": 48,
  "tool_failures": 0,
  "tool_retries": 0,
  "partial_results": 0,
  "agent_failures": 0,
  "agent_retries": 0,
  "invalid_llm_outputs": 2,
  "messages_exchanged": 52,
  "evidence_records": 120,
  "duration_s": 191.27,
  "tokens": {
    "input_tokens": 104,
    "output_tokens": 62395,
    "cache_read_tokens": 88675,
    "cache_write_tokens": 168288,
    "llm_calls": 35,
    "cost_usd": 0.05313065
  },
  "tokens_by_agent": {
    "orchestrator": {
      "input_tokens": 6,
      "output_tokens": 1046,
      "cache_read_tokens": 1322,
      "cache_write_tokens": 2003,
      "llm_calls": 2,
      "cost_usd": 0.0007871949999999999
    },
    "dependency": {
      "input_tokens": 24,
      "output_tokens": 12958,
      "cache_read_tokens": 28132,
      "cache_write_tokens": 23440,
      "llm_calls": 9,
      "cost_usd": 0.009692720000000002
    },
    "observability": {
      "input_tokens": 40,
      "output_tokens": 22502,
      "cache_read_tokens": 31058,
      "cache_write_tokens": 47128,
      "llm_calls": 14,
      "cost_usd": 0.01745658
    },
    "reasoning": {
      "input_tokens": 12,
      "output_tokens": 14926,
      "cache_read_tokens": 0,
      "cache_write_tokens": 59678,
      "llm_calls": 3,
      "cost_usd": 0.01492395
    },
    "critic": {
      "input_tokens": 18,
      "output_tokens": 8937,
      "cache_read_tokens": 28163,
      "cache_write_tokens": 32185,
      "llm_calls": 6,
      "cost_usd": 0.008775055
    },
    "reporting": {
      "input_tokens": 4,
      "output_tokens": 2026,
      "cache_read_tokens": 0,
      "cache_write_tokens": 3854,
      "llm_calls": 1,
      "cost_usd": 0.00149515
    }
  }
}
```
