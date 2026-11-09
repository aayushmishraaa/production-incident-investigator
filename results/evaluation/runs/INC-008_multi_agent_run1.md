# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-008
- **Title:** Database CPU high and slow user pages
- **Severity:** SEV2
- **Affected services:** postgres, user-service
- **Start time:** 2026-09-23T12:50:00+00:00
- **Investigation ID:** inv-324079714a (multi_agent)
- **Final status:** `ROOT_CAUSE_IDENTIFIED`

## Executive Summary
INC-008 (SEV2): Postgres CPU alarm and slow user profile pages starting 12:50Z. Final status is ROOT_CAUSE_IDENTIFIED, with Redis as the culprit service (leading hypothesis H1, confidence 0.83). Redis reached its 8G maxmemory limit (allkeys-lru) at 12:43:15Z and began evicting keys (~1.87M) (critic summary). The profile cache hit rate fell from ~95% to a window mean of ~47% (trough ~38%) with onset at 12:46Z (met-redis-cache_hit_rate-1240-1315). Redis request rate stayed flat (-0.2%), so the drop is not driven by caller volume. Cache misses pushed user lookups onto the Postgres users table: Postgres request rate rose 138% (baseline ~2497 to mean ~5961, max ~10219) and CPU rose to a mean of ~64% with peaks near 96% (met-postgres-request_rate-1220-1315, met-postgres-cpu_pct-1220-1315). Slow 'SELECT * FROM users WHERE id = $1' statements took 22-30 s from 12:46:04Z (logpat-postgres-cee9c952). user-service logged cache-miss WARNs from 12:45:15Z (logpat-user-service-481445ce) and 2000 ms query timeouts from 12:47:12Z (logpat-user-service-f882ebef). The 'DBA suspects a bad query' hypothesis was rejected (H4), and the feature-flag change was rejected (H2). The root cause of the initial memory growth is not yet identified, so the explanation is the most probable one rather than a confirmed fact.

## Incident Timeline
| Time (UTC) | Label | Event | Evidence |
|---|---|---|---|
| 2026-09-23T12:10:00Z | CONFIRMED FACT | Config change on user-service: feature.profile_v2_cache false -> true at 2026-09-23T12:10:00Z (OPS-2229) | cfg-b6fe4aaf |
| 2026-09-23T12:40:20Z | OBSERVED EVIDENCE | First log: 4x WARN on user-service: 'Deprecated API /v1/users/legacy called by client web-34' (first 2026-09-23T12:40:20Z, last 2026-09-23T13:12:10Z) | logpat-user-service-742b555e |
| 2026-09-23T12:43:15Z | OBSERVED EVIDENCE | First log: 3x WARN on redis: 'Evicting keys: used_memory 7.970G reached maxmemory 8G (policy allkeys-lru), evicted_keys=1870233' (first 2026-09-23T12:43:15Z, last 2026-09-23T12:48:57Z) | logpat-redis-4b4f360d |
| 2026-09-23T12:45:00Z | OBSERVED EVIDENCE | Anomaly onset: postgres cpu_pct: baseline 35.46 -> window mean 64.02 (max 96.23, change 80.5%), onset 2026-09-23T12:45:00Z | met-postgres-cpu_pct-1220-1315 |
| 2026-09-23T12:45:00Z | OBSERVED EVIDENCE | Anomaly onset: postgres request_rate: baseline 2496.81 -> window mean 5960.78 (max 10219.4, change 138.7%), onset 2026-09-23T12:45:00Z | met-postgres-request_rate-1220-1315 |
| 2026-09-23T12:45:15Z | OBSERVED EVIDENCE | First log: 24x WARN on user-service: 'Cache miss for user profile u-79, falling back to DB' (first 2026-09-23T12:45:15Z, last 2026-09-23T13:13:55Z) | logpat-user-service-481445ce |
| 2026-09-23T12:46:00Z | OBSERVED EVIDENCE | Anomaly onset: postgres db_conn_util_pct: baseline 39.95 -> window mean 63.43 (max 96.15, change 58.8%), onset 2026-09-23T12:46:00Z | met-postgres-db_conn_util_pct-1220-1315 |
| 2026-09-23T12:46:00Z | OBSERVED EVIDENCE | Anomaly onset: user-service p95_latency_ms: baseline 79.7 -> window mean 939.95 (max 1972.06, change 1079.3%), onset 2026-09-23T12:46:00Z | met-user-service-p95_latency_ms-1220-1315 |
| 2026-09-23T12:46:00Z | OBSERVED EVIDENCE | Anomaly onset: user-service p95_latency_ms: baseline 79.7 -> window mean 1417.74 (max 1972.06, change 1678.8%), onset 2026-09-23T12:46:00Z | met-user-service-p95_latency_ms-1240-1315 |
| 2026-09-23T12:46:00Z | OBSERVED EVIDENCE | Anomaly onset: redis cache_hit_rate: baseline 95.0 -> window mean 47.49 (max 95.82, change -50.0%), onset 2026-09-23T12:46:00Z | met-redis-cache_hit_rate-1240-1315 |
| 2026-09-23T12:46:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service p95_latency_ms: baseline 151.47 -> window mean 525.1 (max 973.35, change 246.7%), onset 2026-09-23T12:46:00Z | met-payment-service-p95_latency_ms-1220-1315 |
| 2026-09-23T12:46:04Z | OBSERVED EVIDENCE | First log: 9x WARN on postgres: 'duration: 26410 ms statement: SELECT * FROM users WHERE id = $1' (first 2026-09-23T12:46:04Z, last 2026-09-23T13:12:00Z) | logpat-postgres-cee9c952 |
| 2026-09-23T12:47:00Z | OBSERVED EVIDENCE | Anomaly onset: user-service error_rate: baseline 0.4 -> window mean 2.6 (max 5.36, change 558.3%), onset 2026-09-23T12:47:00Z | met-user-service-error_rate-1220-1315 |
| 2026-09-23T12:47:00Z | OBSERVED EVIDENCE | Anomaly onset: user-service error_rate: baseline 0.4 -> window mean 3.83 (max 5.36, change 867.7%), onset 2026-09-23T12:47:00Z | met-user-service-error_rate-1240-1315 |
| 2026-09-23T12:47:12Z | OBSERVED EVIDENCE | First log: 7x ERROR on user-service: 'Query timeout on users table after 2000ms (req 89)' (first 2026-09-23T12:47:12Z, last 2026-09-23T13:11:20Z) | logpat-user-service-f882ebef |
| 2026-09-23T12:50:00Z | CONFIRMED FACT | Reported symptom start |  |
| 2026-09-23T12:56:00Z | CONFIRMED FACT | Incident reported |  |

## Observed Symptoms
- **OBSERVED EVIDENCE:** postgres cpu_pct: baseline 35.46 -> window mean 64.02 (max 96.23, change 80.5%), onset 2026-09-23T12:45:00Z (met-postgres-cpu_pct-1220-1315)
- **OBSERVED EVIDENCE:** postgres db_conn_util_pct: baseline 39.95 -> window mean 63.43 (max 96.15, change 58.8%), onset 2026-09-23T12:46:00Z (met-postgres-db_conn_util_pct-1220-1315)
- **OBSERVED EVIDENCE:** postgres request_rate: baseline 2496.81 -> window mean 5960.78 (max 10219.4, change 138.7%), onset 2026-09-23T12:45:00Z (met-postgres-request_rate-1220-1315)
- **OBSERVED EVIDENCE:** user-service error_rate: baseline 0.4 -> window mean 2.6 (max 5.36, change 558.3%), onset 2026-09-23T12:47:00Z (met-user-service-error_rate-1220-1315)
- **OBSERVED EVIDENCE:** user-service p95_latency_ms: baseline 79.7 -> window mean 939.95 (max 1972.06, change 1079.3%), onset 2026-09-23T12:46:00Z (met-user-service-p95_latency_ms-1220-1315)
- **OBSERVED EVIDENCE:** user-service p95_latency_ms: baseline 79.7 -> window mean 1417.74 (max 1972.06, change 1678.8%), onset 2026-09-23T12:46:00Z (met-user-service-p95_latency_ms-1240-1315)
- **OBSERVED EVIDENCE:** user-service error_rate: baseline 0.4 -> window mean 3.83 (max 5.36, change 867.7%), onset 2026-09-23T12:47:00Z (met-user-service-error_rate-1240-1315)
- **OBSERVED EVIDENCE:** redis cache_hit_rate: baseline 95.0 -> window mean 47.49 (max 95.82, change -50.0%), onset 2026-09-23T12:46:00Z (met-redis-cache_hit_rate-1240-1315)
- **OBSERVED EVIDENCE:** payment-service p95_latency_ms: baseline 151.47 -> window mean 525.1 (max 973.35, change 246.7%), onset 2026-09-23T12:46:00Z (met-payment-service-p95_latency_ms-1220-1315)
- **OBSERVED EVIDENCE:** [dependency] Only one change found in the window: config key feature.profile_v2_cache changed false -> true at 12:10Z by config-bot (ticket OPS-2229). Numeric ratio not applicable (boolean). (cfg-b6fe4aaf)
- **OBSERVED EVIDENCE:** [dependency] Dependency graph (topology-v2, effective from 2026-09-15): user-service upstream = postgres, redis; downstream = api-gateway, notification-service, order-service. The added edge is notification-service -> user-service (notification-service calls user-service); no new edge touches postgres directly from user-service. (topo-user-service-both-d2)
- **OBSERVED EVIDENCE:** [dependency] user-service error_rate and p95 latency moved sharply: p95 baseline ~80 ms rose to ~1970 ms at 12:50 sample (onset 12:46Z by detector); error rate rose from ~0.4% to ~3.9-5% at 12:50 (onset 12:47Z). db_conn_util_pct stayed flat (~30%), with no onset detected. (met-user-service-p95_latency_ms-1220-1315, met-user-service-error_rate-1220-1315, met-user-service-db_conn_util_pct-1220-1315)
- **INFERENCE:** [dependency] The feature.profile_v2_cache=true change (12:10Z) could have altered profile query patterns or cache behaviour, and a delayed effect (e.g. cache warm-up or traffic-dependent) could explain the 12:46-12:50 onset. Needs confirmation via postgres query/CPU metrics and cache hit data (cache_hit_rate not collected for user-service). (cfg-b6fe4aaf)
- **OBSERVED EVIDENCE:** [observability] Postgres cpu_pct rose from baseline mean 35.46% to window mean 64.02% (max 96.23%). Onset detected at 12:45Z; sampled series 34.4% at 12:40, 48.9% at 12:45, 88.5% at 12:50, 95-91% through 13:10, 88% at 13:15. (met-postgres-cpu_pct-1220-1315)
- **OBSERVED EVIDENCE:** [observability] db_conn_util_pct rose from baseline mean 39.95% to window mean 63.43% (max 96.15%); onset 12:46Z, 41.9% at 12:40, 49.1% at 12:45, 82.1% at 12:50, ~87-92% through 13:15. (met-postgres-db_conn_util_pct-1220-1315)
- **OBSERVED EVIDENCE:** [observability] request_rate (postgres) rose from baseline mean ~2497 to window mean ~5961 (+138.7%, max ~10219); onset 12:45Z, ~2570 at 12:40 then ~9171 at 12:50 and ~8500-9300 through 13:15. Load step is concurrent with CPU onset. (met-postgres-request_rate-1220-1315)
- **OBSERVED EVIDENCE:** [observability] p95 latency (12.13 ms window vs 11.97 baseline, +1.3%) and p99 latency (25.18 vs 25.10 ms, +0.3%) show no meaningful change in the window, and disk_io_wait_ms is flat (~1.99 ms). No onset detected for these metrics. (met-postgres-p95_latency_ms-1220-1315, met-postgres-p99_latency_ms-1220-1315, met-postgres-disk_io_wait_ms-1220-1315)
- **OBSERVED EVIDENCE:** [observability] WARN log pattern 'duration: <n> ms statement: SELECT * FROM users WHERE id = $1' appeared 9 times between 12:46:04Z and 13:12:00Z, with durations ~22.5–29.9 s (e.g., 26410 ms at 12:46:04, 29910 ms at 12:49:28, 23710 ms at 13:12:00). First slow user lookup occurs at the same minute as the CPU/connection/request-rate onset. (logpat-postgres-cee9c952, log-d5a950f3, log-b2ef86dd, log-6f48070e)
- **OBSERVED EVIDENCE:** [observability] Earlier WARN pattern 'SELECT report_rollup()' logged 2 times (12:32:44Z 15902 ms, 12:35:26Z 18802 ms). These occurred ~10–15 min before CPU onset and are not part of the 12:45 step; they do not recur after 12:35 in the matched logs. (logpat-postgres-44883ca5, log-321d6d3d, log-ae4471cf)
- **OBSERVED EVIDENCE:** [observability] No ERROR/FATAL logs in window; no lock-related log records matched the 'lock' keyword in 12:20–13:15Z. (logpat-postgres-cee9c952)
- **OBSERVED EVIDENCE:** [observability] user-service p95 latency rose from baseline mean 79.7 ms to window mean 1417.7 ms (+1679%), max 1972 ms; detected onset 12:46Z, with 12:50 sample at 1972 ms and still ~1790 ms at 13:15. (met-user-service-p95_latency_ms-1240-1315)
- **OBSERVED EVIDENCE:** [observability] user-service error_rate rose from baseline 0.4% to window mean 3.83% (max 5.36%), onset 12:47Z. (met-user-service-error_rate-1240-1315)
- **OBSERVED EVIDENCE:** [observability] user-service p99 latency essentially unchanged (baseline 160.8 ms vs window 158.8 ms); request_rate flat (495.6 vs 494.4 rps, -0.2%); timeout_rate flat at ~0.05%; db_conn_util_pct flat (30.2% vs 30.1%). (met-user-service-p99_latency_ms-1240-1315, met-user-service-request_rate-1240-1315, met-user-service-timeout_rate-1240-1315, met-user-service-db_conn_util_pct-1240-1315)
- **OBSERVED EVIDENCE:** [observability] user-service logged 7 ERROR 'Query timeout on users table after 2000ms' between 12:47:12Z and 13:11:20Z (about every 4 minutes); 24 WARN 'Cache miss for user profile, falling back to DB' first seen 12:45:15Z. (logpat-user-service-f882ebef, logpat-user-service-481445ce)
- **OBSERVED EVIDENCE:** [observability] redis cache_hit_rate fell from baseline 95.0% to window mean 47.5% (min 37.5%), onset 12:46Z, and stayed ~38% from 12:50 through 13:15. redis error_rate flat at 0.01%; redis request_rate flat (6008 vs 5995/s). redis timeout_rate not collected. (met-redis-cache_hit_rate-1240-1315, met-redis-error_rate-1240-1315, met-redis-request_rate-1240-1315)
- **ASSUMPTION:** [critic: unsupported assumption] That the 12:43 maxmemory eviction is the sole cause of the hit-rate drop, since the source of the memory growth is not shown. 
- **ASSUMPTION:** [critic: unsupported assumption] That Postgres saturation is entirely from user lookups; the request-rate breakdown by client is not available. 

## Investigation Performed
- Round 1 | observability | completed | attempts 1 | 3 tool calls | Characterize Postgres CPU spike and slow queries starting around 2026-09-23T12:50:00Z: CPU, active connections, query latency, lock waits, top query patterns/ti
- Round 1 | observability | completed | attempts 1 | 6 tool calls | Measure user-service latency, error rate, traffic and DB/cache call behavior from 2026-09-23T12:40Z onward, and check whether callers (notification-service, ord
- Round 1 | dependency | completed | attempts 1 | 4 tool calls | Identify deployments, config changes, or schema/migration changes to postgres, user-service, and notification-service in the window 2026-09-22T12:50Z to 2026-09
- Round 1 | dependency | completed | attempts 1 | 8 tool calls | Map downstream services that consume postgres and user-service to scope impact and check for shared-resource coupling.
- Round 1 | reasoning | completed | attempts 1 | 0 tool calls | Develop and rank competing hypotheses
- Round 1 | critic | completed | attempts 1 | 4 tool calls | Independently review hypotheses
- Round 1 | reporting | completed | attempts 1 | 0 tool calls | Write final report

## Root-Cause Hypotheses (ranked by evidence strength)
### 1. H1 - `cache_degradation` in `redis` (confidence 0.83, critic: accept)
**INFERENCE:** Redis profile cache hit-rate collapse (95% to ~38%) at 12:46Z pushes user profile reads onto the Postgres users table, saturating Postgres CPU and connections, which causes slow user lookups and user-service query timeouts. Mechanism: Cache hit rate falls from 95% to ~38% -> cache misses increase roughly 12x -> user-service issues many more 'SELECT * FROM users WHERE id=$1' queries to Postgres -> Postgres request rate steps +138% and CPU/connection utilisation saturate (~90%+) -> user lookups queue and run 22-30 s -> user-service hits 2000 ms query timeouts and p95 rises ~17x. Root cause of the hit-rate drop itself (eviction, flush, restart, key change) is not yet known.

Confidence breakdown: base 0.10; +0.08 corroboration across >=2 independent source types; +0.78 supporting evidence (7 refs, reliability-weighted, capped); -0.10 contradicting evidence (2 refs, capped 0.45); +0.08 proposed cause (12:45) precedes/coincides with first observed anomaly (12:45); -0.08 4 acknowledged evidence gaps; +0.05 critic review adjustment; = 0.83 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [OBSERVED EVIDENCE] `met-redis-cache_hit_rate-1240-1315` (strong): redis cache_hit_rate: baseline 95.0 -> window mean 47.49 (max 95.82, change -50.0%), onset 2026-09-23T12:46:00Z
- [OBSERVED EVIDENCE] `logpat-user-service-481445ce` (moderate): 24x WARN on user-service: 'Cache miss for user profile u-79, falling back to DB' (first 2026-09-23T12:45:15Z, last 2026-09-23T13:13:55Z)
- [OBSERVED EVIDENCE] `logpat-user-service-f882ebef` (moderate): 7x ERROR on user-service: 'Query timeout on users table after 2000ms (req 89)' (first 2026-09-23T12:47:12Z, last 2026-09-23T13:11:20Z)
- [OBSERVED EVIDENCE] `met-postgres-request_rate-1220-1315` (moderate): postgres request_rate: baseline 2496.81 -> window mean 5960.78 (max 10219.4, change 138.7%), onset 2026-09-23T12:45:00Z
- [OBSERVED EVIDENCE] `met-postgres-cpu_pct-1220-1315` (moderate): postgres cpu_pct: baseline 35.46 -> window mean 64.02 (max 96.23, change 80.5%), onset 2026-09-23T12:45:00Z
- [OBSERVED EVIDENCE] `logpat-postgres-cee9c952` (moderate): 9x WARN on postgres: 'duration: 26410 ms statement: SELECT * FROM users WHERE id = $1' (first 2026-09-23T12:46:04Z, last 2026-09-23T13:12:00Z)
- [OBSERVED EVIDENCE] `met-redis-request_rate-1240-1315` (weak): redis request_rate: baseline 6007.51 -> window mean 5994.53 (max 6495.82, change -0.2%), onset none detected

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-user-service-db_conn_util_pct-1240-1315` (weak): user-service db_conn_util_pct: baseline 30.22 -> window mean 30.13 (max 32.03, change -0.3%), onset none detected
- [OBSERVED EVIDENCE] `met-postgres-p95_latency_ms-1220-1315` (weak): postgres p95_latency_ms: baseline 11.97 -> window mean 12.13 (max 13.2, change 1.3%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Why the hit rate dropped (redis evictions, restarts, flush, key/format change)
- [UNKNOWN] Redis timeout_rate and WARN/ERROR logs
- [UNKNOWN] Cache-miss source breakdown: whether misses are from user-service profile reads only
- [UNKNOWN] pg_stat_statements / active query counts showing user lookup volume rise

### 2. H2 - `configuration_regression` in `user-service` (confidence 0.00, critic: reject)
**INFERENCE:** The feature flag feature.profile_v2_cache flipped false->true at 12:10Z (OPS-2229) changed the profile read/cache path, driving cache misses and DB load with a delayed onset. Mechanism: Flag enabled at 12:10Z -> altered profile cache behaviour (key or read path) -> cache hit rate collapse and extra DB reads -> Postgres saturation and user-service timeouts from 12:45-12:47Z. Delay would need a traffic- or warm-up-dependent trigger.

Confidence breakdown: base 0.10; +0.08 corroboration across >=2 independent source types; +0.24 supporting evidence (2 refs, reliability-weighted, capped); -0.20 contradicting evidence (2 refs, capped 0.45); +0.08 proposed cause (12:10) precedes/coincides with first observed anomaly (12:45); -0.06 3 acknowledged evidence gaps; -0.40 critic review adjustment; = 0.00 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [CONFIRMED FACT] `cfg-b6fe4aaf` (moderate): Config change on user-service: feature.profile_v2_cache false -> true at 2026-09-23T12:10:00Z (OPS-2229)
- [OBSERVED EVIDENCE] `met-redis-cache_hit_rate-1240-1315` (weak): redis cache_hit_rate: baseline 95.0 -> window mean 47.49 (max 95.82, change -50.0%), onset 2026-09-23T12:46:00Z

Contradicting evidence:
- [CONFIRMED FACT] `cfg-b6fe4aaf` (moderate): Config change on user-service: feature.profile_v2_cache false -> true at 2026-09-23T12:10:00Z (OPS-2229)
- [OBSERVED EVIDENCE] `met-user-service-request_rate-1240-1315` (weak): user-service request_rate: baseline 495.63 -> window mean 494.43 (max 541.15, change -0.2%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Flag evaluation rollout percentage / time-of-ramp data
- [UNKNOWN] Cache key or code path diff for profile_v2_cache
- [UNKNOWN] Evidence that the flag was actually evaluated for traffic after 12:45

### 3. H3 - `traffic_surge` in `postgres` (confidence 0.00, critic: reject)
**INFERENCE:** An unidentified client (not user-service) starts issuing a large additional load to Postgres at 12:45Z, saturating CPU and connections; user-service slowness is a secondary effect of shared-DB contention. Mechanism: New or increased Postgres client load at 12:45Z (+138% request rate) -> CPU and connection saturation -> queuing of all statements including user lookups -> user-service timeouts. Payment-service shows a latency step at 12:46Z, which would fit a shared-DB contention pattern.

Confidence breakdown: base 0.10; +0.38 supporting evidence (3 refs, reliability-weighted, capped); -0.25 contradicting evidence (3 refs, capped 0.45); +0.08 proposed cause (12:45) precedes/coincides with first observed anomaly (12:45); -0.04 2 acknowledged evidence gaps; -0.40 critic review adjustment; = 0.00 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [OBSERVED EVIDENCE] `met-postgres-request_rate-1220-1315` (strong): postgres request_rate: baseline 2496.81 -> window mean 5960.78 (max 10219.4, change 138.7%), onset 2026-09-23T12:45:00Z
- [OBSERVED EVIDENCE] `met-postgres-cpu_pct-1220-1315` (moderate): postgres cpu_pct: baseline 35.46 -> window mean 64.02 (max 96.23, change 80.5%), onset 2026-09-23T12:45:00Z
- [OBSERVED EVIDENCE] `met-payment-service-p95_latency_ms-1220-1315` (weak): payment-service p95_latency_ms: baseline 151.47 -> window mean 525.1 (max 973.35, change 246.7%), onset 2026-09-23T12:46:00Z

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-user-service-request_rate-1240-1315` (moderate): user-service request_rate: baseline 495.63 -> window mean 494.43 (max 541.15, change -0.2%), onset none detected
- [OBSERVED EVIDENCE] `met-order-service-p95_latency_ms-1220-1315` (weak): order-service p95_latency_ms: baseline 198.32 -> window mean 201.57 (max 218.68, change 1.6%), onset none detected
- [OBSERVED EVIDENCE] `met-auth-service-p95_latency_ms-1220-1315` (weak): auth-service p95_latency_ms: baseline 44.63 -> window mean 44.9 (max 48.97, change 0.6%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Breakdown of Postgres request rate by client/application or source host
- [UNKNOWN] Payment-service request rate and DB query profile

### 4. H4 - `unknown` in `postgres` (confidence 0.00, critic: reject)
**INFERENCE:** Query-level regression on the users table lookup (plan or index/statistics change not captured by change records) makes SELECT * FROM users WHERE id=$1 slow under load. Mechanism: Plan or statistics change on users table -> point lookup becomes expensive -> CPU saturates as request volume rises -> user lookups time out.

Confidence breakdown: base 0.10; +0.08 corroboration across >=2 independent source types; +0.24 supporting evidence (2 refs, reliability-weighted, capped); -0.25 contradicting evidence (3 refs, capped 0.45); +0.08 proposed cause (12:45) precedes/coincides with first observed anomaly (12:45); -0.04 2 acknowledged evidence gaps; -0.40 critic review adjustment; = 0.00 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-postgres-cee9c952` (moderate): 9x WARN on postgres: 'duration: 26410 ms statement: SELECT * FROM users WHERE id = $1' (first 2026-09-23T12:46:04Z, last 2026-09-23T13:12:00Z)
- [OBSERVED EVIDENCE] `met-postgres-cpu_pct-1220-1315` (weak): postgres cpu_pct: baseline 35.46 -> window mean 64.02 (max 96.23, change 80.5%), onset 2026-09-23T12:45:00Z

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-postgres-disk_io_wait_ms-1220-1315` (moderate): postgres disk_io_wait_ms: baseline 1.99 -> window mean 1.99 (max 2.18, change -0.3%), onset none detected
- [OBSERVED EVIDENCE] `met-postgres-p95_latency_ms-1220-1315` (weak): postgres p95_latency_ms: baseline 11.97 -> window mean 12.13 (max 13.2, change 1.3%), onset none detected
- [OBSERVED EVIDENCE] `logpat-postgres-44883ca5` (weak): 2x WARN on postgres: 'duration: 15902 ms statement: SELECT report_rollup()' (first 2026-09-23T12:32:44Z, last 2026-09-23T12:35:26Z)

Remaining uncertainties / missing evidence:
- [UNKNOWN] Query plan (EXPLAIN) for the user lookup and users table stats / index DDL history
- [UNKNOWN] pg_stat_statements mean_exec_time before and after 12:45

## Critic Review
- **Verdict:** `APPROVED` (rounds reviewed: 1)
- **Reasoning:** H1 is the leading hypothesis and is supported by independent sources. Redis logs show maxmemory (8G, allkeys-lru) reached at 12:43:15Z with evictions (~1.87M keys) starting before the hit-rate drop (onset 12:46Z) and before the user-service cache-miss WARNs (12:45:15Z). Postgres request rate and CPU step at 12:45Z, the slow users-table lookups start at 12:46:04Z, and user-service timeouts follow at 12:47:12Z. Redis request rate is flat, so the miss shift is not driven by caller volume. No redis config change or deployment explains the memory pressure. H2 is rejected: the flag flipped at 12:10Z with no effect for 35 minutes, and no user-service logs or metrics link it to the cache path. Its only remaining value is as a possible contributor to memory growth, which is unverified. H3 is rejected: no caller shows a load step, and the Postgres request increase is the user-lookup read amplification from cache misses. H4 is rejected: disk IO is flat, Postgres p95 is flat, and the 22-30 s durations are consistent with queueing behind saturated CPU rather than a plan regression. Culprit: redis (cache memory exhaustion and LRU eviction), with Postgres saturation as the downstream effect.
- H1: **accept** - Redis evictions at maxmemory begin 12:43:15Z, before the 12:45:15Z cache-miss WARNs and the 12:46Z hit-rate drop. Postgres request and CPU steps at 12:45Z and users-table slow statements from 12:46:04Z follow in order. Redis request rate is flat, so the drop is not driven by caller volume. The residual gap is that Postgres p95 is flat despite 22-30 s statements, which may reflect queueing and is a minor unresolved detail.
- H2: **reject** - The flag flipped at 12:10Z, but user-service latency, error rate, Postgres CPU, and hit rate were flat for 35 minutes. No log or metric from user-service ties the flag to the cache path. The pre-check flagged the culprit symptom with no evidence. The flag could only matter if it drove memory growth in redis, and nothing shows that.
- H3: **reject** - No caller shows a load step: user-service, order, api-gateway, and notification traffic are flat. The Postgres request step matches the miss-driven user-lookup volume from H1. Order and auth Postgres-dependent services show no latency change, which argues against general shared-DB contention. Payment's p95 step is weak evidence.
- H4: **reject** - Disk IO wait is flat, and Postgres p95 is flat. The slow statement is a single-row lookup whose long durations fit queueing behind CPU saturation from H1's extra load. No plan or stats change is evidenced. The 12:32 report_rollup slowness predates onset and is a separate pattern.
- pre-check warning `culprit_symptom` on H2: no log/metric evidence cited for culprit user-service
- pre-check warning `single_source` on H3: all support comes from one source type (metric)
- alternative: Redis memory growth from an unidentified source (for example larger values or more keys) pushed the instance to maxmemory; the source is not identified, and H2's flag change is one untested candidate.
- alternative: Shared-DB contention from payment-service's latency step at 12:46Z, which is weakly supported and not the primary driver.

## Probable Root Cause
ROOT CAUSE IDENTIFIED (critic-approved; still an INFERENCE from evidence): cache_degradation in redis - Redis profile cache hit-rate collapse (95% to ~38%) at 12:46Z pushes user profile reads onto the Postgres users table, saturating Postgres CPU and connections, which causes slow user lookups and user-service query timeouts.

## Corrective Actions
- Restore cache headroom immediately: increase Redis maxmemory or scale the instance, or flush/evict non-essential keys, so the profile hit rate recovers toward 95%.
- Reduce Postgres load while the cache recovers: shed or rate-limit non-critical user-lookup traffic, and monitor connection pool saturation.
- Confirm recovery by checking that the Redis hit rate returns to baseline and that Postgres CPU and request rate return to ~35% and ~2500 req/s respectively.
- Check user-service timeout errors and the p95 latency trend after the cache is restored.

## Preventive Actions
- Identify the source of Redis memory growth (key count, value size, or key-pattern change) since the 12:43Z maxmemory event; this is an open evidence gap.
- Set Redis memory capacity planning and right-size maxmemory with headroom above peak working set.
- Review the eviction policy (allkeys-lru) for the profile cache, and consider a dedicated cache instance or key TTL/namespace controls to protect profile data.
- Add a read-through safeguard so cache misses do not create unbounded load on the users table (e.g., request coalescing, circuit breaker, or a per-service DB concurrency limit).
- Keep the feature-flag change OPS-2229 (profile_v2_cache) under review to rule out its contribution to memory growth, since this is currently unverified.

## Monitoring Recommendations
- Alert on Redis used_memory above 80% of maxmemory and on evicted_keys rate greater than zero.
- Alert on the profile cache hit rate dropping below 80% for more than 2 minutes.
- Alert on Postgres CPU above 80% and on request rate more than 50% above its baseline.
- Track Postgres statement durations above 2000 ms for the users table and user-service 'Query timeout on users table' error counts.
- Monitor Redis request rate and per-client key-count growth to identify any future memory-growth source.

## Evidence Gaps
- none recorded

## Limitations
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: critic verdict APPROVED

## Final Status
`ROOT_CAUSE_IDENTIFIED`

The most probable explanation for INC-008 is that Redis memory exhaustion and LRU eviction at 12:43Z collapsed the profile cache hit rate at 12:46Z. This drove a large increase in user lookups to Postgres, which saturated CPU and connections and caused slow queries and user-service timeouts. The Redis component is the culprit, with Postgres saturation as the downstream effect. The source of the initial memory growth and the exact trigger remain unconfirmed and should be closed as follow-up evidence gaps.

## Execution Statistics
```json
{
  "rounds": 1,
  "tool_calls": 27,
  "tool_failures": 0,
  "tool_retries": 0,
  "partial_results": 0,
  "agent_failures": 0,
  "agent_retries": 0,
  "invalid_llm_outputs": 0,
  "messages_exchanged": 20,
  "evidence_records": 82,
  "duration_s": 66.45,
  "tokens": {
    "input_tokens": 50,
    "output_tokens": 24034,
    "cache_read_tokens": 43153,
    "cache_write_tokens": 60672,
    "llm_calls": 17,
    "cost_usd": 0.020037529999999998
  },
  "tokens_by_agent": {
    "orchestrator": {
      "input_tokens": 6,
      "output_tokens": 1150,
      "cache_read_tokens": 3325,
      "cache_write_tokens": 0,
      "llm_calls": 2,
      "cost_usd": 0.0006088500000000001
    },
    "dependency": {
      "input_tokens": 16,
      "output_tokens": 6457,
      "cache_read_tokens": 14246,
      "cache_write_tokens": 13984,
      "llm_calls": 6,
      "cost_usd": 0.00512056
    },
    "observability": {
      "input_tokens": 12,
      "output_tokens": 6889,
      "cache_read_tokens": 5749,
      "cache_write_tokens": 16761,
      "llm_calls": 4,
      "cost_usd": 0.005598315
    },
    "reasoning": {
      "input_tokens": 4,
      "output_tokens": 5397,
      "cache_read_tokens": 0,
      "cache_write_tokens": 14103,
      "llm_calls": 1,
      "cost_usd": 0.004461774999999999
    },
    "critic": {
      "input_tokens": 8,
      "output_tokens": 2601,
      "cache_read_tokens": 19833,
      "cache_write_tokens": 12012,
      "llm_calls": 3,
      "cost_usd": 0.0030011300000000003
    },
    "reporting": {
      "input_tokens": 4,
      "output_tokens": 1540,
      "cache_read_tokens": 0,
      "cache_write_tokens": 3812,
      "llm_calls": 1,
      "cost_usd": 0.0012469
    }
  }
}
```
