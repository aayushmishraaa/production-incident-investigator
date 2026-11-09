# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-012
- **Title:** Payment connection pool timeouts
- **Severity:** SEV2
- **Affected services:** payment-service
- **Start time:** 2026-10-05T10:10:00+00:00
- **Investigation ID:** inv-b8db097790 (multi_agent)
- **Final status:** `ROOT_CAUSE_IDENTIFIED`

## Executive Summary
INC-012 (SEV2): Payment API latency and errors on payment-service starting around 10:05-10:06Z on 2026-10-05, with logs dominated by connection pool acquisition timeouts. The investigation status is ROOT_CAUSE_IDENTIFIED. The most probable explanation (confidence 0.83) is configuration regression: config change cfg-56d39584 (OPS-2669, applied by config-bot) reduced payment-service db.pool.max_size from 50 to 10 at 10:04:00Z (cfg-56d39584; logpat-payment-service-e8818e6d). With the smaller pool, the payment-db-pool was saturated at normal load, producing queued requests and 5000ms acquisition timeouts from 10:06:13Z (logpat-payment-service-7d1739af, 29 errors, active=10, idle=0). Timeout rate rose from a baseline of 0.1 to a window mean of 6.3 (met-payment-service-timeout_rate-0940-1035), and pool utilisation rose from ~35% to ~69% mean with a peak of 100% (met-payment-service-db_conn_util_pct-0940-1035). Request rate was flat (-0.4%), so the change was not load-driven. This is not a confirmed fact; the saturation at 10 connections is inferred from log counts and utilisation rather than measured directly.

Alternative explanations were examined and rejected: client-side leak or long hold times (H2), contradicted by falling Postgres connection utilisation (met-postgres-db_conn_util_pct-0940-1035), and Postgres-side lock or slow-query degradation (H3), contradicted by flat Postgres p95/p99 latency, CPU and error rate. The Postgres report_rollup() slow statements (logpat-postgres-44883ca5, 14s) are noted but do not explain the onset.

Note that the payment p99 latency series is flat while p95 rose roughly 16x (met-payment-service-p99_latency_ms-0940-1035). This is physically inconsistent and should be checked for a metric labelling problem; it does not overturn the timing and error evidence.

## Incident Timeline
| Time (UTC) | Label | Event | Evidence |
|---|---|---|---|
| 2026-10-05T09:41:44Z | OBSERVED EVIDENCE | First log: 5x WARN on postgres: 'duration: 14102 ms statement: SELECT report_rollup()' (first 2026-10-05T09:41:44Z, last 2026-10-05T10:24:50Z) | logpat-postgres-44883ca5 |
| 2026-10-05T09:43:29Z | OBSERVED EVIDENCE | First log: 5x WARN on notification-service: 'SMTP provider throttled 1 message' (first 2026-10-05T09:43:29Z, last 2026-10-05T10:31:49Z) | logpat-notification-service-54b86179 |
| 2026-10-05T09:44:02Z | OBSERVED EVIDENCE | First log: 5x WARN on api-gateway: 'Slow client upload from 10.4.85.12 (1.9MB)' (first 2026-10-05T09:44:02Z, last 2026-10-05T10:28:03Z) | logpat-api-gateway-88b04940 |
| 2026-10-05T09:45:26Z | OBSERVED EVIDENCE | First log: 7x WARN on payment-service: 'Card network soft decline (code 05) for charge ch_98' (first 2026-10-05T09:45:26Z, last 2026-10-05T10:22:54Z) | logpat-payment-service-7e9bf84f |
| 2026-10-05T09:46:51Z | OBSERVED EVIDENCE | First log: 6x WARN on user-service: 'Deprecated API /v1/users/legacy called by client web-22' (first 2026-10-05T09:46:51Z, last 2026-10-05T10:27:52Z) | logpat-user-service-742b555e |
| 2026-10-05T10:04:00Z | CONFIRMED FACT | Config change on payment-service: db.pool.max_size 50 -> 10 at 2026-10-05T10:04:00Z (OPS-2669) | cfg-56d39584 |
| 2026-10-05T10:05:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service db_conn_util_pct: baseline 34.95 -> window mean 69.43 (max 100.0, change 98.7%), onset 2026-10-05T10:05:00Z | met-payment-service-db_conn_util_pct-0940-1035 |
| 2026-10-05T10:05:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service db_conn_util_pct: baseline 34.95 -> window mean 54.19 (max 100.0, change 55.1%), onset 2026-10-05T10:05:00Z | met-payment-service-db_conn_util_pct-0940-1016 |
| 2026-10-05T10:06:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service error_rate: baseline 0.8 -> window mean 9.17 (max 18.85, change 1040.5%), onset 2026-10-05T10:06:00Z | met-payment-service-error_rate-0940-1035 |
| 2026-10-05T10:06:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service timeout_rate: baseline 0.1 -> window mean 6.3 (max 13.3, change 6147.1%), onset 2026-10-05T10:06:00Z | met-payment-service-timeout_rate-0940-1035 |
| 2026-10-05T10:06:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service p95_latency_ms: baseline 148.77 -> window mean 1326.87 (max 2591.54, change 791.9%), onset 2026-10-05T10:06:00Z | met-payment-service-p95_latency_ms-0940-1035 |
| 2026-10-05T10:06:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service timeout_rate: baseline 0.1 -> window mean 3.28 (max 12.97, change 3151.4%), onset 2026-10-05T10:06:00Z | met-payment-service-timeout_rate-0940-1016 |
| 2026-10-05T10:06:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service error_rate: baseline 0.8 -> window mean 5.25 (max 18.85, change 552.9%), onset 2026-10-05T10:06:00Z | met-payment-service-error_rate-0940-1016 |
| 2026-10-05T10:06:13Z | OBSERVED EVIDENCE | First log: 29x ERROR on payment-service: 'Timeout acquiring connection from pool payment-db-pool after 5000ms (active=10, idle=0, waiting=29)' (first 2026-10-05T10:06:13Z, last 2026-10-05T10:34:18Z) | logpat-payment-service-7d1739af |
| 2026-10-05T10:09:15Z | OBSERVED EVIDENCE | First log: 4x WARN on auth-service: 'Login rate limit hit for user id u-45' (first 2026-10-05T10:09:15Z, last 2026-10-05T10:29:41Z) | logpat-auth-service-cc8d3b87 |
| 2026-10-05T10:10:00Z | CONFIRMED FACT | Reported symptom start |  |
| 2026-10-05T10:16:00Z | CONFIRMED FACT | Incident reported |  |

## Observed Symptoms
- **OBSERVED EVIDENCE:** payment-service error_rate: baseline 0.8 -> window mean 9.17 (max 18.85, change 1040.5%), onset 2026-10-05T10:06:00Z (met-payment-service-error_rate-0940-1035)
- **OBSERVED EVIDENCE:** payment-service timeout_rate: baseline 0.1 -> window mean 6.3 (max 13.3, change 6147.1%), onset 2026-10-05T10:06:00Z (met-payment-service-timeout_rate-0940-1035)
- **OBSERVED EVIDENCE:** payment-service db_conn_util_pct: baseline 34.95 -> window mean 69.43 (max 100.0, change 98.7%), onset 2026-10-05T10:05:00Z (met-payment-service-db_conn_util_pct-0940-1035)
- **OBSERVED EVIDENCE:** payment-service p95_latency_ms: baseline 148.77 -> window mean 1326.87 (max 2591.54, change 791.9%), onset 2026-10-05T10:06:00Z (met-payment-service-p95_latency_ms-0940-1035)
- **OBSERVED EVIDENCE:** payment-service db_conn_util_pct: baseline 34.95 -> window mean 54.19 (max 100.0, change 55.1%), onset 2026-10-05T10:05:00Z (met-payment-service-db_conn_util_pct-0940-1016)
- **OBSERVED EVIDENCE:** payment-service timeout_rate: baseline 0.1 -> window mean 3.28 (max 12.97, change 3151.4%), onset 2026-10-05T10:06:00Z (met-payment-service-timeout_rate-0940-1016)
- **OBSERVED EVIDENCE:** payment-service error_rate: baseline 0.8 -> window mean 5.25 (max 18.85, change 552.9%), onset 2026-10-05T10:06:00Z (met-payment-service-error_rate-0940-1016)
- **OBSERVED EVIDENCE:** [dependency] Config change cfg-56d39584 by config-bot (ticket OPS-2669) reduced payment-service db.pool.max_size from 50 to 10 (ratio 0.2) at 10:04Z, about 6 minutes before T0 (10:10Z). (cfg-56d39584)
- **OBSERVED EVIDENCE:** [dependency] payment-service db_conn_util_pct rose from baseline mean ~35% to 63% at 10:05 and 94% at 10:10 (window max 100%), onset detected 10:05Z, i.e. starting about 1 minute after the pool change. (met-payment-service-db_conn_util_pct-0940-1016)
- **OBSERVED EVIDENCE:** [dependency] payment-service timeout_rate (baseline 0.1% -> ~11-13% at 10:10+) and error_rate (baseline 0.8% -> ~17% at 10:10) both show onset at 10:06Z, before the reported T0 of 10:10Z. (met-payment-service-timeout_rate-0940-1016, met-payment-service-error_rate-0940-1016)
- **OBSERVED EVIDENCE:** [dependency] p99 latency did not materially change (baseline ~299ms vs window ~302ms), so the symptom is timeouts/errors rather than latency growth in the sampled window. (met-payment-service-p99_latency_ms-0940-1016)
- **OBSERVED EVIDENCE:** [dependency] Only one config change in the window: cfg-56d39584. No config changes were returned for auth-service, postgres, redis, api-gateway or order-service in the window (query was not key-filtered beyond time range; absence is per this query only). (cfg-56d39584)
- **OBSERVED EVIDENCE:** [dependency] Dependency graph (topology-v2): payment-service upstream = auth-service, postgres, redis; downstream = api-gateway, order-service. No topology changes recorded. (topo-payment-service-both-d2)
- **OBSERVED EVIDENCE:** [observability] INFO log: 'Configuration reloaded: db.pool.max_size=10 (version 77)' at 10:04:00Z, the only config/change event in the window. (logpat-payment-service-e8818e6d)
- **OBSERVED EVIDENCE:** [observability] db_conn_util_pct rose from baseline mean 34.95% to 63.3% at 10:05 and reached 93.9% at 10:10 and 100% at 10:20 and 10:30. Onset detected at 10:05Z. (met-payment-service-db_conn_util_pct-0940-1035)
- **OBSERVED EVIDENCE:** [observability] First 'Timeout acquiring connection from pool payment-db-pool after 5000ms' ERROR at 10:06:13Z (active=10, idle=0, waiting up to 92). 29 such errors through 10:34:18Z. (logpat-payment-service-7d1739af, log-945fe4b3)
- **OBSERVED EVIDENCE:** [observability] error_rate onset at 10:06Z: baseline 0.8% to window mean 9.17% (max 18.85%); sampled 0.78% at 10:05 then 17.2% at 10:10 and ~16-18% through 10:35. timeout_rate baseline 0.1% rose to 6.3% mean (max 13.3%), onset 10:06Z. (met-payment-service-error_rate-0940-1035, met-payment-service-timeout_rate-0940-1035)
- **OBSERVED EVIDENCE:** [observability] p95 latency jumped from baseline ~149ms to ~2,360-2,530ms from 10:10 sampled points (window mean 1,327ms), onset 10:06Z. p99 latency did NOT change materially (baseline 299ms, window mean 301ms, max 326ms), which is inconsistent with the p95 shift and should be reconciled. (met-payment-service-p95_latency_ms-0940-1035, met-payment-service-p99_latency_ms-0940-1035)
- **OBSERVED EVIDENCE:** [observability] request_rate flat: baseline mean 300.2 vs window mean 299.2 (-0.4%), no traffic surge preceding onset. (met-payment-service-request_rate-0940-1035)
- **INFERENCE:** [observability] The 10:04 config reload setting db.pool.max_size=10 may have reduced effective pool capacity, causing exhaustion beginning 10:05-10:06. This is a hypothesis only; the prior pool size and the reload's content are not verified here. Traffic was flat, so the cause is not load-driven at the payment-service level. (logpat-payment-service-e8818e6d, met-payment-service-request_rate-0940-1035)
- **OBSERVED EVIDENCE:** [observability] First payment-db-pool timeout ERROR in window: 'Timeout acquiring connection from pool payment-db-pool after 5000ms (active=10, idle=0, waiting=29)'. 29 such errors between 10:06:13Z and 10:34:18Z; waiting queue reached up to 92 in sampled records, active pinned at 10 (pool max), idle 0. (logpat-payment-service-7d1739af, log-945fe4b3, log-eaa111fa)
- **OBSERVED EVIDENCE:** [observability] Postgres db_conn_util_pct did NOT rise. Baseline mean 39.83%, window mean 30.56% (-23.3%); it fell from ~34.6% at 10:05 to ~22% from 10:10 onward. No onset detected for an increase. (met-postgres-db_conn_util_pct-0940-1035)
- **OBSERVED EVIDENCE:** [observability] Postgres p95/p99 latency, CPU and error rate are flat versus baseline (p95 -0.9%, p99 -0.1%, CPU +0.3%, error rate ~0.05% unchanged). No onset detected. (met-postgres-p95_latency_ms-0940-1035, met-postgres-p99_latency_ms-0940-1035, met-postgres-cpu_pct-0940-1035, met-postgres-error_rate-0940-1035)
- **OBSERVED EVIDENCE:** [observability] Postgres WARN slow statement 'SELECT report_rollup()' logged 5 times (durations seen e.g. 14102 ms), first 09:41:44Z, last 10:24:50Z. Not in the payment-service window onset, but a long-running query pattern exists. (logpat-postgres-44883ca5)
- **OBSERVED EVIDENCE:** [observability] Redis p95 (1.5ms) and p99 (3.0ms) latency and error rate (0.01%) are unchanged vs baseline with no onset. timeout_rate is not collected for redis (missing). (met-redis-p95_latency_ms-0940-1035, met-redis-p99_latency_ms-0940-1035, met-redis-error_rate-0940-1035)
- **ASSUMPTION:** [critic: unsupported assumption] That 10 connections saturate at ~300 rps depends on hold-time estimates not directly measured 
- **ASSUMPTION:** [critic: unsupported assumption] Payment p99 latency being flat while p95 rose ~16x is unexplained and may indicate a metric labelling problem 
- **ASSUMPTION:** [critic: unsupported assumption] That 50 was the intended long-term pool size and that OPS-2669 was meant for production 

## Investigation Performed
- Round 1 | observability | completed | attempts 1 | 3 tool calls | Analyze payment-service logs and metrics from 2026-10-05T09:40Z onward: connection pool timeout errors, pool active/idle/wait counts, request latency and error 
- Round 1 | observability | completed | attempts 1 | 6 tool calls | Check upstream dependencies for saturation or errors around the symptom start: postgres connection counts, query latency, lock waits; redis latency and connecti
- Round 1 | dependency | completed | attempts 1 | 4 tool calls | Identify deployments, configuration changes (especially pool size, timeout, or connection settings) and infrastructure changes to payment-service and its upstre
- Round 1 | reasoning | completed | attempts 1 | 0 tool calls | Develop and rank competing hypotheses
- Round 1 | critic | completed | attempts 1 | 4 tool calls | Independently review hypotheses
- Round 1 | reporting | completed | attempts 1 | 0 tool calls | Write final report

## Root-Cause Hypotheses (ranked by evidence strength)
### 1. H1 - `configuration_regression` in `payment-service` (confidence 0.83, critic: accept)
**INFERENCE:** Config change cfg-56d39584 (OPS-2669) reduced payment-service db.pool.max_size from 50 to 10 at 10:04Z, shrinking the payment-db-pool and causing client-side pool exhaustion, timeouts and errors from 10:05-10:06Z. Mechanism: config-bot applied db.pool.max_size=10 (version 77) at 10:04:00Z -> effective pool capacity drops 5x -> at ~300 rps with normal DB hold times, the 10 connections are saturated -> requests queue for connections (waiting up to 92) -> 5000ms acquisition timeouts from 10:06:13Z -> timeout_rate and error_rate rise and p95 latency rises (~149ms to ~2.4s).

Confidence breakdown: base 0.10; +0.08 corroboration across >=2 independent source types; +0.78 supporting evidence (6 refs, reliability-weighted, capped); -0.10 contradicting evidence (2 refs, capped 0.45); +0.08 proposed cause (10:04) precedes/coincides with first observed anomaly (10:05); -0.08 4 acknowledged evidence gaps; +0.05 critic review adjustment; = 0.83 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [CONFIRMED FACT] `cfg-56d39584` (strong): Config change on payment-service: db.pool.max_size 50 -> 10 at 2026-10-05T10:04:00Z (OPS-2669)
- [OBSERVED EVIDENCE] `logpat-payment-service-e8818e6d` (strong): 1x INFO on payment-service: 'Configuration reloaded: db.pool.max_size=10 (version 77)' (first 2026-10-05T10:04:00Z, last 2026-10-05T10:04:00Z)
- [OBSERVED EVIDENCE] `logpat-payment-service-7d1739af` (strong): 29x ERROR on payment-service: 'Timeout acquiring connection from pool payment-db-pool after 5000ms (active=10, idle=0, waiting=29)' (first 2026-10-05T10:06:13Z, last 2026-10-05T10:34:18Z)
- [OBSERVED EVIDENCE] `met-payment-service-db_conn_util_pct-0940-1035` (moderate): payment-service db_conn_util_pct: baseline 34.95 -> window mean 69.43 (max 100.0, change 98.7%), onset 2026-10-05T10:05:00Z
- [OBSERVED EVIDENCE] `met-payment-service-timeout_rate-0940-1035` (moderate): payment-service timeout_rate: baseline 0.1 -> window mean 6.3 (max 13.3, change 6147.1%), onset 2026-10-05T10:06:00Z
- [OBSERVED EVIDENCE] `met-payment-service-request_rate-0940-1035` (moderate): payment-service request_rate: baseline 300.21 -> window mean 299.16 (max 325.13, change -0.4%), onset none detected

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-postgres-db_conn_util_pct-0940-1035` (weak): postgres db_conn_util_pct: baseline 39.83 -> window mean 30.56 (max 43.9, change -23.3%), onset 2026-10-05T10:07:00Z
- [OBSERVED EVIDENCE] `met-payment-service-p99_latency_ms-0940-1035` (weak): payment-service p99_latency_ms: baseline 299.15 -> window mean 300.84 (max 325.6, change 0.6%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Pool wait-time and active/idle time series (not just log-embedded counts).
- [UNKNOWN] Prior db.pool.max_size history and whether 50 was the intended long-term value.
- [UNKNOWN] Approval and intent of OPS-2669 and whether it was meant for another environment.
- [UNKNOWN] Config version 77 full diff to confirm no other pool settings changed.

### 2. H2 - `db_connection_pool_exhaustion` in `payment-service` (confidence 0.00, critic: reject)
**INFERENCE:** Independent of the pool size setting, payment-service connections are being held or leaked client-side (for example by long-running report_rollup() calls, an app-level lock, or a connection leak), starving payment-db-pool. Mechanism: Connections checked out by payment-service are not returned promptly (leak, long-held transactions or lock waits) -> the pool's 10 active slots are pinned -> new requests queue and time out at 5000ms -> timeouts and errors. The config change may be coincident rather than causal.

Confidence breakdown: base 0.10; +0.16 supporting evidence (2 refs, reliability-weighted, capped); -0.45 contradicting evidence (4 refs, capped 0.45); +0.00 no cause time given; temporal precedence unverified; -0.06 3 acknowledged evidence gaps; -0.40 critic review adjustment; = 0.00 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-payment-service-7d1739af` (moderate): 29x ERROR on payment-service: 'Timeout acquiring connection from pool payment-db-pool after 5000ms (active=10, idle=0, waiting=29)' (first 2026-10-05T10:06:13Z, last 2026-10-05T10:34:18Z)
- [OBSERVED EVIDENCE] `logpat-postgres-44883ca5` (weak): 5x WARN on postgres: 'duration: 14102 ms statement: SELECT report_rollup()' (first 2026-10-05T09:41:44Z, last 2026-10-05T10:24:50Z)

Contradicting evidence:
- [CONFIRMED FACT] `cfg-56d39584` (moderate): Config change on payment-service: db.pool.max_size 50 -> 10 at 2026-10-05T10:04:00Z (OPS-2669)
- [OBSERVED EVIDENCE] `logpat-payment-service-e8818e6d` (moderate): 1x INFO on payment-service: 'Configuration reloaded: db.pool.max_size=10 (version 77)' (first 2026-10-05T10:04:00Z, last 2026-10-05T10:04:00Z)
- [OBSERVED EVIDENCE] `logpat-postgres-44883ca5` (weak): 5x WARN on postgres: 'duration: 14102 ms statement: SELECT report_rollup()' (first 2026-10-05T09:41:44Z, last 2026-10-05T10:24:50Z)
- [OBSERVED EVIDENCE] `met-postgres-db_conn_util_pct-0940-1035` (moderate): postgres db_conn_util_pct: baseline 39.83 -> window mean 30.56 (max 43.9, change -23.3%), onset 2026-10-05T10:07:00Z

Remaining uncertainties / missing evidence:
- [UNKNOWN] Postgres pg_stat_activity per application_name and state (idle in transaction, lock waits).
- [UNKNOWN] Payment-service connection checkout/return metrics or leak traces.
- [UNKNOWN] Whether report_rollup() connections belong to payment-service or another client.

### 3. H3 - `upstream_dependency_degradation` in `postgres` (confidence 0.00, critic: reject)
**INFERENCE:** A postgres-side issue (locking or slow queries) increased connection hold time for payment-service, saturating its pool. Mechanism: Slow or locked postgres queries -> payment-service connections are held longer -> the pool exhausts -> timeouts. This is the alternative that the dependency-side symptoms would need to show.

Confidence breakdown: base 0.10; +0.04 supporting evidence (1 refs, reliability-weighted, capped); -0.45 contradicting evidence (4 refs, capped 0.45); +0.00 no cause time given; temporal precedence unverified; -0.04 2 acknowledged evidence gaps; -0.40 critic review adjustment; = 0.00 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-postgres-44883ca5` (weak): 5x WARN on postgres: 'duration: 14102 ms statement: SELECT report_rollup()' (first 2026-10-05T09:41:44Z, last 2026-10-05T10:24:50Z)

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-postgres-p95_latency_ms-0940-1035` (strong): postgres p95_latency_ms: baseline 12.07 -> window mean 11.96 (max 12.88, change -0.9%), onset none detected
- [OBSERVED EVIDENCE] `met-postgres-p99_latency_ms-0940-1035` (strong): postgres p99_latency_ms: baseline 25.15 -> window mean 25.13 (max 27.03, change -0.1%), onset none detected
- [OBSERVED EVIDENCE] `met-postgres-cpu_pct-0940-1035` (moderate): postgres cpu_pct: baseline 35.02 -> window mean 35.11 (max 37.77, change 0.3%), onset none detected
- [OBSERVED EVIDENCE] `met-postgres-error_rate-0940-1035` (moderate): postgres error_rate: baseline 0.05 -> window mean 0.05 (max 0.05, change -1.5%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Postgres lock-wait metrics.
- [UNKNOWN] Per-application connection hold-time data.

## Critic Review
- **Verdict:** `APPROVED` (rounds reviewed: 1)
- **Reasoning:** H1 is the leading hypothesis and is well supported. The only pool-related config change (db.pool.max_size 50 -> 10, OPS-2669, config-bot) is recorded at 10:04:00Z, and the service logged the reload at the same instant. Pool utilisation rises at 10:05, the first pool-timeout error is at 10:06:13Z (logged active=10, idle=0, which matches the new max), and the timeout_rate, error_rate (0.8% -> ~17%) and p95 (~149ms -> ~2.4s) onsets all fall at 10:06Z. Request rate is flat (-0.4%), so the change is not load-driven. No deployments occurred in the window. Postgres p95/p99/CPU/error rate are flat, which rules out H3. Postgres connection utilisation fell rather than rose, and the pool is client-side, so H2 (DB-side hold or leak) is contradicted. H2 and H3 are rejected. Caveats: no direct pool wait-time or hold-time series were available, so saturation at 10 is inferred from the log counts and utilisation rather than measured. The payment p99 latency being flat while p95 rose ~16x is physically inconsistent (p99 should be >= p95), so the latency percentile series should be checked for mislabelling; this does not overturn the timing and error evidence. Recommended action: roll back db.pool.max_size to 50 after confirming OPS-2669 was not intended for another environment, then confirm recovery.
- H1: **accept** - Config change at 10:04:00Z precedes the 10:05 utilisation rise, the 10:06:13 first timeout, and the 10:06 error/timeout onsets. Logs show active=10, idle=0 matching the new max. Traffic is flat, and no deployments occurred. Caveat: pool wait metrics are missing and the p95/p99 relationship is inconsistent, so impact sizing is uncertain.
- H2: **reject** - Postgres db_conn_util fell after 10:05Z, which is inconsistent with connections held on the DB side. The report_rollup WARNs started at 09:41Z with no alignment to the 10:05-10:06 onset. The config change explains the pinned pool more simply. No pg_stat_activity evidence supports a leak.
- H3: **reject** - Postgres p95 (-0.9%), p99 (-0.1%), CPU (+0.3%) and error rate are all flat across the window. No lock-wait evidence exists, and the report_rollup slow statements predate onset.
- pre-check warning `cause_time` on H2: no cause time given; temporal precedence cannot be verified
- pre-check warning `single_source` on H2: all support comes from one source type (log)
- pre-check warning `cause_time` on H3: no cause time given; temporal precedence cannot be verified
- pre-check warning `single_source` on H3: all support comes from one source type (log)
- alternative: Client-side leak or long hold times in payment-service (H2), not ruled out at the application level but contradicted by postgres-side connection metrics
- alternative: Postgres lock contention (H3), contradicted by flat postgres latency and CPU

## Probable Root Cause
ROOT CAUSE IDENTIFIED (critic-approved; still an INFERENCE from evidence): configuration_regression in payment-service - Config change cfg-56d39584 (OPS-2669) reduced payment-service db.pool.max_size from 50 to 10 at 10:04Z, shrinking the payment-db-pool and causing client-side pool exhaustion, timeouts and errors from 10:05-10:06Z.

## Corrective Actions
- Confirm with the change owner (OPS-2669) that db.pool.max_size=10 was not intended for production, then roll back payment-service db.pool.max_size to 50 (the prior value).
- Verify recovery after rollback: timeout_rate and error_rate return to baseline (~0.1% timeouts, ~0.8% errors) and p95 latency returns to ~150ms.
- Monitor pool wait and active connection counts during the rollback to confirm the 'waiting' queue drains.

## Preventive Actions
- Add validation to config-bot or the config pipeline that rejects or requires approval for changes to db.pool.max_size that reduce it by more than a set percentage, and enforce per-environment config scoping.
- Review pool sizing against peak rps and Postgres hold times so the pool capacity is set from measured requirements, not inherited defaults.
- Require change review and a canary or staged rollout for database pool configuration changes in payment-service.
- Investigate and fix the long-running report_rollup() query on Postgres (up to 14s) to reduce any risk of connection hold-time pressure, separately from this incident.

## Monitoring Recommendations
- Alert when payment-db-pool active connections reach the configured max for more than 1 minute, and when acquisition wait time or waiting count is above zero.
- Export direct pool metrics (acquisition wait time, connection hold time, pool max_size) so saturation can be measured rather than inferred.
- Alert on config reload events that change db.pool.max_size or other pool settings, with the version and author logged.
- Alert on payment-service timeout_rate above baseline and on p95 latency above ~500ms; fix the p99 latency series labelling and add a consistency check that p99 >= p95.
- Track Postgres duration of report_rollup() statements over 5s to detect hold-time regressions.

## Evidence Gaps
- none recorded

## Limitations
- No direct pool wait-time or connection hold-time metrics were available; saturation at 10 connections is inferred from log counts and utilisation.
- Payment p99 latency is flat while p95 rose ~16x, which is physically inconsistent and may indicate a metric labelling problem.
- Whether OPS-2669 was intended for production, and whether 50 is the correct long-term pool size, has not been confirmed.
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: critic verdict APPROVED

## Final Status
`ROOT_CAUSE_IDENTIFIED`

The incident is most probably caused by the reduction of payment-service db.pool.max_size from 50 to 10 via config change cfg-56d39584 (OPS-2669) at 10:04Z, which saturated the client-side connection pool and produced timeouts and errors from 10:06Z. The root cause is identified with confidence 0.83 but the saturation threshold is inferred rather than directly measured. Rolling back the pool size to 50 after confirming intent is the recommended immediate action, followed by recovery verification and the preventive controls on pool configuration changes.

## Execution Statistics
```json
{
  "rounds": 1,
  "tool_calls": 18,
  "tool_failures": 0,
  "tool_retries": 0,
  "partial_results": 0,
  "agent_failures": 0,
  "agent_retries": 0,
  "invalid_llm_outputs": 0,
  "messages_exchanged": 17,
  "evidence_records": 81,
  "duration_s": 61.37,
  "tokens": {
    "input_tokens": 40,
    "output_tokens": 19724,
    "cache_read_tokens": 23674,
    "cache_write_tokens": 57500,
    "llm_calls": 13,
    "cost_usd": 0.01729024
  },
  "tokens_by_agent": {
    "orchestrator": {
      "input_tokens": 6,
      "output_tokens": 903,
      "cache_read_tokens": 2989,
      "cache_write_tokens": 0,
      "llm_calls": 2,
      "cost_usd": 0.00048198999999999996
    },
    "dependency": {
      "input_tokens": 8,
      "output_tokens": 2545,
      "cache_read_tokens": 7195,
      "cache_write_tokens": 5306,
      "llm_calls": 3,
      "cost_usd": 0.0020085
    },
    "observability": {
      "input_tokens": 12,
      "output_tokens": 7559,
      "cache_read_tokens": 5763,
      "cache_write_tokens": 24917,
      "llm_calls": 4,
      "cost_usd": 0.006952955
    },
    "reasoning": {
      "input_tokens": 4,
      "output_tokens": 4271,
      "cache_read_tokens": 0,
      "cache_write_tokens": 12524,
      "llm_calls": 1,
      "cost_usd": 0.0037014
    },
    "critic": {
      "input_tokens": 6,
      "output_tokens": 2645,
      "cache_read_tokens": 7727,
      "cache_write_tokens": 11178,
      "llm_calls": 2,
      "cost_usd": 0.00279762
    },
    "reporting": {
      "input_tokens": 4,
      "output_tokens": 1801,
      "cache_read_tokens": 0,
      "cache_write_tokens": 3575,
      "llm_calls": 1,
      "cost_usd": 0.001347775
    }
  }
}
```
