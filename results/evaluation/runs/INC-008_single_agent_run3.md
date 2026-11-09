# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-008
- **Title:** Database CPU high and slow user pages
- **Severity:** SEV2
- **Affected services:** postgres, user-service
- **Start time:** 2026-09-23T12:50:00+00:00
- **Investigation ID:** inv-30628f49aa (single_agent)
- **Final status:** `PROBABLE_ROOT_CAUSE`

## Executive Summary
Postgres CPU saturation (35% to ~92%) and user-service p95 latency (80ms to ~1.9s) with errors (0.4% to ~5%) began around 12:45-12:47Z. The most likely trigger is feature flag feature.profile_v2_cache, enabled at 12:10Z (OPS-2229), whose 4.1x larger cached payloads coincide with a rise in cache misses falling back to Postgres from 12:45Z. The DBA's bad-query theory is weakly supported: the slow statement is a routine PK lookup, and the earlier report_rollup() slow queries ended before onset. Confidence is moderate; the cache-to-DB causal link is inferred and cache hit rate is not collected.

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
**INFERENCE:** Enabling feature.profile_v2_cache (4.1x larger cached payloads) caused a cache-miss storm that overloaded Postgres CPU and connections. Mechanism: Config change at 12:10Z enabled larger cached payloads. From about 12:45Z, cache misses rose (logpat-user-service-481445ce) and user lookups fell back to Postgres. Postgres CPU rose from about 35% to 88-95% and db_conn_util from about 40% to 82-92% starting 12:45-12:46Z. user-service p95 rose from 76ms to about 1972ms and errors from 0.4% to 4-5% from 12:47Z. Repeated 22-30s SELECT * FROM users statements followed. The 35-minute gap suggests a capacity or eviction threshold was crossed rather than an immediate effect.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [CONFIRMED FACT] `cfg-b6fe4aaf` (strong): Config change on user-service: feature.profile_v2_cache false -> true at 2026-09-23T12:10:00Z (OPS-2229)
- [OBSERVED EVIDENCE] `logpat-user-service-9d44e354` (moderate): 1x INFO on user-service: 'Feature flag profile_v2_cache enabled (avg cached payload 4.1x larger)' (first 2026-09-23T12:10:00Z, last 2026-09-23T12:10:00Z)
- [OBSERVED EVIDENCE] `logpat-user-service-481445ce` (moderate): 24x WARN on user-service: 'Cache miss for user profile u-79, falling back to DB' (first 2026-09-23T12:45:15Z, last 2026-09-23T13:13:55Z)
- [OBSERVED EVIDENCE] `met-postgres-cpu_pct-1220-1315` (strong): postgres cpu_pct: baseline 35.46 -> window mean 64.02 (max 96.23, change 80.5%), onset 2026-09-23T12:45:00Z
- [OBSERVED EVIDENCE] `met-user-service-p95_latency_ms-1220-1315` (strong): user-service p95_latency_ms: baseline 79.7 -> window mean 939.95 (max 1972.06, change 1079.3%), onset 2026-09-23T12:46:00Z
- [OBSERVED EVIDENCE] `logpat-postgres-cee9c952` (strong): 9x WARN on postgres: 'duration: 26410 ms statement: SELECT * FROM users WHERE id = $1' (first 2026-09-23T12:46:04Z, last 2026-09-23T13:12:00Z)
- [INFERENCE] `hist-HIST-2025-061` (weak): Past incident HIST-2025-061 'Redis evictions overloaded database' (similarity 0.317): Redis reached maxmemory; LRU eviction caused cache misses and DB load.

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-user-service-request_rate-1220-1315` (moderate): user-service request_rate: baseline 495.63 -> window mean 497.98 (max 542.57, change 0.5%), onset none detected
- [OBSERVED EVIDENCE] `met-user-service-cpu_pct-1200-1315` (weak): user-service cpu_pct: baseline 29.54 -> window mean 30.03 (max 33.34, change 1.7%), onset none detected
- [OBSERVED EVIDENCE] `met-postgres-disk_io_wait_ms-1220-1315` (moderate): postgres disk_io_wait_ms: baseline 1.99 -> window mean 1.99 (max 2.18, change -0.3%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] user-service cache_hit_rate (not collected)
- [UNKNOWN] Redis metrics and evictions 12:10-12:50Z
- [UNKNOWN] Query plans, pg_stat_activity, lock state
- [UNKNOWN] Explanation of why a PK lookup takes 25s

### 2. H2 - `db_connection_pool_exhaustion` in `postgres` (confidence 0.25, critic: n/a)
**INFERENCE:** A DB-side issue (bad query plan, lock contention, or report_rollup()) caused CPU saturation independent of the flag. Mechanism: Long-running DB statements consume CPU and connections, slowing all user lookups. This is the DBA's bad-query theory.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-postgres-44883ca5` (moderate): 2x WARN on postgres: 'duration: 15902 ms statement: SELECT report_rollup()' (first 2026-09-23T12:32:44Z, last 2026-09-23T12:35:26Z)
- [OBSERVED EVIDENCE] `met-postgres-db_conn_util_pct-1220-1315` (moderate): postgres db_conn_util_pct: baseline 39.95 -> window mean 63.43 (max 96.15, change 58.8%), onset 2026-09-23T12:46:00Z

Contradicting evidence:
- [OBSERVED EVIDENCE] `logpat-postgres-44883ca5` (moderate): 2x WARN on postgres: 'duration: 15902 ms statement: SELECT report_rollup()' (first 2026-09-23T12:32:44Z, last 2026-09-23T12:35:26Z)
- [OBSERVED EVIDENCE] `logpat-postgres-24aa0214` (weak): 3x INFO on postgres: 'autovacuum: processing table public.orders' (first 2026-09-23T12:29:09Z, last 2026-09-23T12:48:19Z)
- [OBSERVED EVIDENCE] `log-d5a950f3` (moderate): WARN postgres: duration: 26410 ms statement: SELECT * FROM users WHERE id = $1

Remaining uncertainties / missing evidence:
- [UNKNOWN] pg_stat_statements top-query breakdown
- [UNKNOWN] Lock wait data (lock keyword search returned no records)
- [UNKNOWN] Query plan for the slow statement

### 3. H3 - `infrastructure_degradation` in `postgres` (confidence 0.10, critic: n/a)
**INFERENCE:** Storage or network degradation on the DB host or its path caused slow statements. Mechanism: Degraded IO or network path slows queries and causes CPU and connection pileup.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [INFERENCE] `hist-HIST-2025-047` (weak): Past incident HIST-2025-047 'Database storage latency degradation' (similarity 0.149): Cloud block storage volume degraded.

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-postgres-disk_io_wait_ms-1220-1315` (strong): postgres disk_io_wait_ms: baseline 1.99 -> window mean 1.99 (max 2.18, change -0.3%), onset none detected
- [OBSERVED EVIDENCE] `met-postgres-p95_latency_ms-1220-1315` (moderate): postgres p95_latency_ms: baseline 11.97 -> window mean 12.13 (max 13.2, change 1.3%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Host network and conntrack metrics

## Critic Review
- **Verdict:** `NOT_RUN` (rounds reviewed: 0)
- **Reasoning:** 

## Probable Root Cause
MOST PROBABLE EXPLANATION (INFERENCE, not confirmed): configuration_regression in user-service - Enabling feature.profile_v2_cache (4.1x larger cached payloads) caused a cache-miss storm that overloaded Postgres CPU and connections.

## Corrective Actions
- Roll back feature.profile_v2_cache to false (OPS-2229) as immediate mitigation, then confirm Postgres CPU and user-service p95 recover.
- Confirm cache-miss rate and DB connection utilisation recover after rollback.
- Have the DBA capture pg_stat_statements and EXPLAIN ANALYZE for the users lookup to rule out a DB-side contributor.

## Preventive Actions
- Require load testing and a staged canary rollout for cache-payload feature flags.
- Add a review gate for automated config changes that alter cache payload size.
- Document cache sizing against payload size before enabling larger payloads.

## Monitoring Recommendations
- Collect and alert on user-service cache_hit_rate (currently not collected) and Redis evictions and memory.
- Alert on cache-miss log rate and on users-table statement duration above 1s in Postgres.
- Alert on Postgres CPU and connection utilisation, correlated with user-service p95.

## Evidence Gaps
- none recorded

## Limitations
- Temporal correlation between the flag change (12:10Z) and onset (12:45Z) does not prove causation.
- Log pattern counts are sampled summaries.
- [agent-reported gap] No cache_hit_rate for user-service.
- [agent-reported gap] No Redis telemetry for 12:10-12:50Z.
- [agent-reported gap] No pg_stat_statements, lock, or query-plan evidence.
- [agent-reported gap] Mechanism for a PK lookup taking 25s is unexplained.
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: agent submitted

## Final Status
`PROBABLE_ROOT_CAUSE`

The DB CPU saturation and slow user pages most likely stem from the feature flag feature.profile_v2_cache being enabled at 12:10Z (OPS-2229). Cache misses from 12:45Z pushed user lookups to Postgres, where the SELECT * FROM users WHERE id=$1 statement took 22-30 s. The mechanism linking cache misses to DB saturation, and the 35-minute delay after the flag change, are inferred rather than proven. The DBA's bad-query hypothesis is not supported by the evidence.

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
  "invalid_llm_outputs": 1,
  "messages_exchanged": 0,
  "evidence_records": 66,
  "duration_s": 35.71,
  "tokens": {
    "input_tokens": 12,
    "output_tokens": 8868,
    "cache_read_tokens": 51750,
    "cache_write_tokens": 15514,
    "llm_calls": 5,
    "cost_usd": 0.00689195
  },
  "tokens_by_agent": {
    "single_agent": {
      "input_tokens": 12,
      "output_tokens": 8868,
      "cache_read_tokens": 51750,
      "cache_write_tokens": 15514,
      "llm_calls": 5,
      "cost_usd": 0.00689195
    }
  }
}
```
