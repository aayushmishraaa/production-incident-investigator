# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-008
- **Title:** Database CPU high and slow user pages
- **Severity:** SEV2
- **Affected services:** postgres, user-service
- **Start time:** 2026-09-23T12:50:00+00:00
- **Investigation ID:** inv-0d1656e910 (single_agent)
- **Final status:** `PROBABLE_ROOT_CAUSE`

## Executive Summary
Postgres CPU rose from ~35% to ~64% mean (max 96%) starting 12:45-12:50Z, and user-service p95 rose from ~80ms to ~1900ms with error rate up from 0.4% to ~5%. Request rate was flat, so this is not a traffic surge. The dominant slow statement is 'SELECT * FROM users WHERE id = $1' at 22-30 seconds each, which the DBA's bad-query theory points to. A config change enabled feature.profile_v2_cache at 12:10Z (4.1x larger cached payloads). Cache-miss fallbacks to the DB began at 12:45Z, the same minute the DB load shift began. The most likely chain is that the flag change caused cache misses and DB fallback load, but cache hit rate is not collected, so this is not confirmed. Final status: PROBABLE_ROOT_CAUSE.

## Incident Timeline
| Time (UTC) | Label | Event | Evidence |
|---|---|---|---|
| 2026-09-23T12:10:00Z | CONFIRMED FACT | Config change on user-service: feature.profile_v2_cache false -> true at 2026-09-23T12:10:00Z (OPS-2229) | cfg-b6fe4aaf |
| 2026-09-23T12:16:45Z | OBSERVED EVIDENCE | First log: 8x WARN on user-service: 'Deprecated API /v1/users/legacy called by client web-97' (first 2026-09-23T12:16:45Z, last 2026-09-23T13:12:10Z) | logpat-user-service-742b555e |
| 2026-09-23T12:45:00Z | OBSERVED EVIDENCE | Anomaly onset: postgres cpu_pct: baseline 35.46 -> window mean 64.02 (max 96.23, change 80.5%), onset 2026-09-23T12:45:00Z | met-postgres-cpu_pct-1220-1315 |
| 2026-09-23T12:45:15Z | OBSERVED EVIDENCE | First log: 24x WARN on user-service: 'Cache miss for user profile u-79, falling back to DB' (first 2026-09-23T12:45:15Z, last 2026-09-23T13:13:55Z) | logpat-user-service-481445ce |
| 2026-09-23T12:46:00Z | OBSERVED EVIDENCE | Anomaly onset: postgres db_conn_util_pct: baseline 39.95 -> window mean 63.43 (max 96.15, change 58.8%), onset 2026-09-23T12:46:00Z | met-postgres-db_conn_util_pct-1220-1315 |
| 2026-09-23T12:46:00Z | OBSERVED EVIDENCE | Anomaly onset: user-service p95_latency_ms: baseline 79.7 -> window mean 939.95 (max 1972.06, change 1079.3%), onset 2026-09-23T12:46:00Z | met-user-service-p95_latency_ms-1220-1315 |
| 2026-09-23T12:46:04Z | OBSERVED EVIDENCE | First log: 9x WARN on postgres: 'duration: 26410 ms statement: SELECT * FROM users WHERE id = $1' (first 2026-09-23T12:46:04Z, last 2026-09-23T13:12:00Z) | logpat-postgres-cee9c952 |
| 2026-09-23T12:47:00Z | OBSERVED EVIDENCE | Anomaly onset: user-service error_rate: baseline 0.4 -> window mean 2.6 (max 5.36, change 558.3%), onset 2026-09-23T12:47:00Z | met-user-service-error_rate-1220-1315 |
| 2026-09-23T12:47:12Z | OBSERVED EVIDENCE | First log: 7x ERROR on user-service: 'Query timeout on users table after 2000ms (req 89)' (first 2026-09-23T12:47:12Z, last 2026-09-23T13:11:20Z) | logpat-user-service-f882ebef |
| 2026-09-23T12:50:00Z | CONFIRMED FACT | Reported symptom start |  |
| 2026-09-23T12:56:00Z | CONFIRMED FACT | Incident reported |  |

## Observed Symptoms
- **OBSERVED EVIDENCE:** postgres cpu_pct: baseline 35.46 -> window mean 64.02 (max 96.23, change 80.5%), onset 2026-09-23T12:45:00Z (met-postgres-cpu_pct-1220-1315)
- **OBSERVED EVIDENCE:** postgres db_conn_util_pct: baseline 39.95 -> window mean 63.43 (max 96.15, change 58.8%), onset 2026-09-23T12:46:00Z (met-postgres-db_conn_util_pct-1220-1315)
- **OBSERVED EVIDENCE:** user-service p95_latency_ms: baseline 79.7 -> window mean 939.95 (max 1972.06, change 1079.3%), onset 2026-09-23T12:46:00Z (met-user-service-p95_latency_ms-1220-1315)
- **OBSERVED EVIDENCE:** user-service error_rate: baseline 0.4 -> window mean 2.6 (max 5.36, change 558.3%), onset 2026-09-23T12:47:00Z (met-user-service-error_rate-1220-1315)

## Investigation Performed

## Root-Cause Hypotheses (ranked by evidence strength)
### 1. H1 - `configuration_regression` in `user-service` (confidence 0.60, critic: n/a)
**INFERENCE:** Enabling feature.profile_v2_cache (12:10Z, OPS-2229) produced 4.1x larger cached payloads, which led to cache misses and DB fallback load on the users table, saturating Postgres CPU and slowing profile reads. Mechanism: After the flag change, profile cache entries became much larger, plausibly causing evictions or capacity pressure. Cache-miss fallbacks to 'SELECT * FROM users WHERE id=$1' rose from 12:45Z, coinciding with the Postgres CPU onset (12:45-12:50Z) and the user-service latency onset (12:46Z). Slow queries and timeouts then followed.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [CONFIRMED FACT] `cfg-b6fe4aaf` (strong): Config change on user-service: feature.profile_v2_cache false -> true at 2026-09-23T12:10:00Z (OPS-2229)
- [OBSERVED EVIDENCE] `logpat-user-service-9d44e354` (moderate): 1x INFO on user-service: 'Feature flag profile_v2_cache enabled (avg cached payload 4.1x larger)' (first 2026-09-23T12:10:00Z, last 2026-09-23T12:10:00Z)
- [OBSERVED EVIDENCE] `logpat-user-service-481445ce` (moderate): 24x WARN on user-service: 'Cache miss for user profile u-79, falling back to DB' (first 2026-09-23T12:45:15Z, last 2026-09-23T13:13:55Z)
- [OBSERVED EVIDENCE] `met-postgres-cpu_pct-1220-1315` (strong): postgres cpu_pct: baseline 35.46 -> window mean 64.02 (max 96.23, change 80.5%), onset 2026-09-23T12:45:00Z
- [OBSERVED EVIDENCE] `met-user-service-p95_latency_ms-1220-1315` (strong): user-service p95_latency_ms: baseline 79.7 -> window mean 939.95 (max 1972.06, change 1079.3%), onset 2026-09-23T12:46:00Z

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-postgres-db_conn_util_pct-1220-1315` (weak): postgres db_conn_util_pct: baseline 39.95 -> window mean 63.43 (max 96.15, change 58.8%), onset 2026-09-23T12:46:00Z
- [OBSERVED EVIDENCE] `met-user-service-request_rate-1220-1315` (moderate): user-service request_rate: baseline 495.63 -> window mean 497.98 (max 542.57, change 0.5%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] cache_hit_rate for user-service or Redis (not collected)
- [UNKNOWN] Redis memory and eviction metrics
- [UNKNOWN] Count of DB queries from the cache-fallback path versus other callers

### 2. H2 - `db_connection_pool_exhaustion` in `postgres` (confidence 0.30, critic: n/a)
**INFERENCE:** A query plan or lock regression on users (DBA's bad-query theory) causes the simple PK lookup to take 22-30s, saturating CPU and connections. Mechanism: A PK lookup normally takes milliseconds. Taking 20+ seconds suggests a plan regression, missing index, bloat, or lock contention. Those queries consume CPU and connections, which blocks other requests.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-postgres-cee9c952` (strong): 9x WARN on postgres: 'duration: 26410 ms statement: SELECT * FROM users WHERE id = $1' (first 2026-09-23T12:46:04Z, last 2026-09-23T13:12:00Z)
- [OBSERVED EVIDENCE] `logpat-user-service-f882ebef` (moderate): 7x ERROR on user-service: 'Query timeout on users table after 2000ms (req 89)' (first 2026-09-23T12:47:12Z, last 2026-09-23T13:11:20Z)

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-postgres-disk_io_wait_ms-1220-1315` (moderate): postgres disk_io_wait_ms: baseline 1.99 -> window mean 1.99 (max 2.18, change -0.3%), onset none detected
- [UNKNOWN] `get_deployments` (moderate): NOT FOUND in collected evidence

Remaining uncertainties / missing evidence:
- [UNKNOWN] EXPLAIN plan or pg_stat_activity snapshot during the incident
- [UNKNOWN] Lock wait data
- [UNKNOWN] Table bloat or statistics age for users

### 3. H3 - `resource_saturation` in `postgres` (confidence 0.15, critic: n/a)
**INFERENCE:** Background maintenance (report_rollup and autovacuum on orders) produced contention that was partly responsible for the CPU rise. Mechanism: report_rollup ran slowly (15-19s) at 12:32-12:35Z and autovacuum ran repeatedly on orders through 12:48Z. These could contend for CPU and I/O. However, they do not line up with the sustained step change at 12:45-12:50Z.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-postgres-44883ca5` (moderate): 2x WARN on postgres: 'duration: 15902 ms statement: SELECT report_rollup()' (first 2026-09-23T12:32:44Z, last 2026-09-23T12:35:26Z)
- [OBSERVED EVIDENCE] `logpat-postgres-24aa0214` (weak): 3x INFO on postgres: 'autovacuum: processing table public.orders' (first 2026-09-23T12:29:09Z, last 2026-09-23T12:48:19Z)

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-postgres-cpu_pct-1220-1315` (moderate): postgres cpu_pct: baseline 35.46 -> window mean 64.02 (max 96.23, change 80.5%), onset 2026-09-23T12:45:00Z

Remaining uncertainties / missing evidence:
- [UNKNOWN] Scheduling details for report_rollup
- [UNKNOWN] Autovacuum resource usage

## Critic Review
- **Verdict:** `NOT_RUN` (rounds reviewed: 0)
- **Reasoning:** 

## Probable Root Cause
MOST PROBABLE EXPLANATION (INFERENCE, not confirmed): configuration_regression in user-service - Enabling feature.profile_v2_cache (12:10Z, OPS-2229) produced 4.1x larger cached payloads, which led to cache misses and DB fallback load on the users table, saturating Postgres CPU and slowing profile reads.

## Corrective Actions
- Roll back feature.profile_v2_cache to false (cfg-b6fe4aaf) and verify Postgres CPU and user-service p95 recover.
- Capture EXPLAIN ANALYZE and pg_stat_activity for 'SELECT * FROM users WHERE id=$1' during the next occurrence, and check for missing indexes or plan regression.
- Kill or throttle long-running queries if they are still blocking.

## Preventive Actions
- Require canary rollout and load testing for feature flags that change payload size.
- Add cache-size and payload-size guardrails for cached profile data.
- Add alerts on user-service cache-miss rate and on DB queries that exceed 1s.

## Monitoring Recommendations
- Add cache_hit_rate and Redis eviction metrics for user-service.
- Track p95 duration of the users PK lookup in Postgres.
- Track the count of cache-miss fallbacks per minute.

## Evidence Gaps
- none recorded

## Limitations
- Tool results are correlational only.
- Counts of cache misses are sampled log patterns, not full counts.
- The deployment query returned no results, which was treated as no deployment in the window and not as proof of absence of other changes.
- [agent-reported gap] No cache_hit_rate for user-service or Redis telemetry, so the cache-miss mechanism is unverified.
- [agent-reported gap] No EXPLAIN or pg_stat_activity or lock data for the slow users query.
- [agent-reported gap] No causal link between the flag and the DB query path has been tested.
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: agent submitted

## Final Status
`PROBABLE_ROOT_CAUSE`

The sustained Postgres CPU and user-service latency incident began at about 12:45-12:50Z. The strongest correlated change is the profile_v2_cache flag enabled at 12:10Z, which is followed by cache-miss fallbacks and very slow 'SELECT * FROM users WHERE id=$1' statements. The DBA's bad-query hypothesis is a real symptom, but a PK lookup taking 25s points to contention or a secondary cause rather than the query text alone. Status is PROBABLE_ROOT_CAUSE. Confirmation requires cache hit and Redis metrics, or a rollback test of the flag.

## Execution Statistics
```json
{
  "rounds": 1,
  "tool_calls": 8,
  "tool_failures": 0,
  "tool_retries": 0,
  "partial_results": 0,
  "agent_failures": 0,
  "agent_retries": 0,
  "invalid_llm_outputs": 0,
  "messages_exchanged": 0,
  "evidence_records": 63,
  "duration_s": 22.88,
  "tokens": {
    "input_tokens": 8,
    "output_tokens": 5194,
    "cache_read_tokens": 14847,
    "cache_write_tokens": 14731,
    "llm_calls": 3,
    "cost_usd": 0.004587645
  },
  "tokens_by_agent": {
    "single_agent": {
      "input_tokens": 8,
      "output_tokens": 5194,
      "cache_read_tokens": 14847,
      "cache_write_tokens": 14731,
      "llm_calls": 3,
      "cost_usd": 0.004587645
    }
  }
}
```
