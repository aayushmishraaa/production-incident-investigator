# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-008
- **Title:** Database CPU high and slow user pages
- **Severity:** SEV2
- **Affected services:** postgres, user-service
- **Start time:** 2026-09-23T12:50:00+00:00
- **Investigation ID:** inv-a636636a64 (single_agent)
- **Final status:** `PROBABLE_ROOT_CAUSE`

## Executive Summary
Postgres CPU rose from ~35% to ~64% mean (max 96%) starting 12:45, and user-service p95 latency went from ~80ms to ~1.9s with error rate rising from 0.4% to ~5% from 12:46-12:47. Request rate was flat (~496 rps), so this is not a traffic surge. One change preceded the incident: feature flag feature.profile_v2_cache was enabled on user-service at 12:10 (OPS-2229), which the service logs describe as producing cached payloads ~4.1x larger. Cache-miss fallbacks to the DB begin at 12:45, coinciding with the CPU onset, and the slow statements are the user-profile lookup SELECT * FROM users WHERE id=$1 (22-30s durations). The likely chain is: larger cached payloads -> cache pressure/misses -> profile reads hitting Postgres -> DB saturation -> user-service timeouts. The DBA's 'bad query' theory is not well supported: the offending statement is a simple primary-key lookup, and the only query-plan-level anomaly is report_rollup() at 12:32-12:35, which preceded the incident by ~10 minutes and was not repeated in the window. The causal link via Redis/cache is inferred, not directly measured.

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
**INFERENCE:** Enabling feature.profile_v2_cache (12:10) inflated cached profile payloads ~4.1x, causing cache pressure and misses that push profile reads onto Postgres, saturating CPU/connections and causing slow user-profile queries and timeouts. Mechanism: Larger payloads reduce effective cache capacity/hit rate; misses fall back to SELECT * FROM users WHERE id=$1 against Postgres; DB CPU and connection utilisation climb; user-service queries exceed the 2000ms timeout, producing errors and p95 latency increase.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [CONFIRMED FACT] `cfg-b6fe4aaf` (strong): Config change on user-service: feature.profile_v2_cache false -> true at 2026-09-23T12:10:00Z (OPS-2229)
- [OBSERVED EVIDENCE] `logpat-user-service-9d44e354` (moderate): 1x INFO on user-service: 'Feature flag profile_v2_cache enabled (avg cached payload 4.1x larger)' (first 2026-09-23T12:10:00Z, last 2026-09-23T12:10:00Z)
- [OBSERVED EVIDENCE] `logpat-user-service-481445ce` (moderate): 24x WARN on user-service: 'Cache miss for user profile u-79, falling back to DB' (first 2026-09-23T12:45:15Z, last 2026-09-23T13:13:55Z)
- [OBSERVED EVIDENCE] `logpat-postgres-cee9c952` (strong): 9x WARN on postgres: 'duration: 26410 ms statement: SELECT * FROM users WHERE id = $1' (first 2026-09-23T12:46:04Z, last 2026-09-23T13:12:00Z)
- [OBSERVED EVIDENCE] `met-postgres-cpu_pct-1220-1315` (strong): postgres cpu_pct: baseline 35.46 -> window mean 64.02 (max 96.23, change 80.5%), onset 2026-09-23T12:45:00Z
- [OBSERVED EVIDENCE] `met-user-service-p95_latency_ms-1220-1315` (strong): user-service p95_latency_ms: baseline 79.7 -> window mean 939.95 (max 1972.06, change 1079.3%), onset 2026-09-23T12:46:00Z
- [OBSERVED EVIDENCE] `logpat-user-service-f882ebef` (moderate): 7x ERROR on user-service: 'Query timeout on users table after 2000ms (req 89)' (first 2026-09-23T12:47:12Z, last 2026-09-23T13:11:20Z)
- [INFERENCE] `hist-HIST-2025-061` (weak): Past incident HIST-2025-061 'Redis evictions overloaded database' (similarity 0.305): Redis reached maxmemory; LRU eviction caused cache misses and DB load.

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-user-service-request_rate-1220-1315` (moderate): user-service request_rate: baseline 495.63 -> window mean 497.98 (max 542.57, change 0.5%), onset none detected
- [OBSERVED EVIDENCE] `met-user-service-db_conn_util_pct-1220-1315` (moderate): user-service db_conn_util_pct: baseline 30.22 -> window mean 30.13 (max 32.03, change -0.3%), onset none detected
- [OBSERVED EVIDENCE] `met-user-service-cpu_pct-1220-1315` (moderate): user-service cpu_pct: baseline 29.46 -> window mean 30.24 (max 33.34, change 2.7%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Redis / cache memory and eviction telemetry (no cache_hit_rate for user-service; Redis not queried)
- [UNKNOWN] Direct proof that miss volume rose in proportion to the DB load
- [UNKNOWN] Postgres pg_stat_statements / lock wait data

### 2. H2 - `resource_saturation` in `postgres` (confidence 0.20, critic: n/a)
**INFERENCE:** Heavy analytical/maintenance work on Postgres (report_rollup() and autovacuum on public.orders) consumed CPU and I/O, slowing point lookups on users. Mechanism: Long-running report_rollup() executions and autovacuum create CPU/IO contention; user lookups queue behind it, causing latency and timeouts.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-postgres-44883ca5` (moderate): 2x WARN on postgres: 'duration: 15902 ms statement: SELECT report_rollup()' (first 2026-09-23T12:32:44Z, last 2026-09-23T12:35:26Z)
- [OBSERVED EVIDENCE] `logpat-postgres-24aa0214` (weak): 3x INFO on postgres: 'autovacuum: processing table public.orders' (first 2026-09-23T12:29:09Z, last 2026-09-23T12:48:19Z)

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-postgres-cpu_pct-1220-1315` (moderate): postgres cpu_pct: baseline 35.46 -> window mean 64.02 (max 96.23, change 80.5%), onset 2026-09-23T12:45:00Z
- [OBSERVED EVIDENCE] `met-postgres-disk_io_wait_ms-1220-1315` (moderate): postgres disk_io_wait_ms: baseline 1.99 -> window mean 1.99 (max 2.18, change -0.3%), onset none detected
- [OBSERVED EVIDENCE] `logpat-postgres-cee9c952` (moderate): 9x WARN on postgres: 'duration: 26410 ms statement: SELECT * FROM users WHERE id = $1' (first 2026-09-23T12:46:04Z, last 2026-09-23T13:12:00Z)

Remaining uncertainties / missing evidence:
- [UNKNOWN] Whether report_rollup was running at 12:45-13:15 (no records after 12:35)
- [UNKNOWN] pg_stat_activity snapshot

### 3. H3 - `infrastructure_degradation` in `postgres` (confidence 0.05, critic: n/a)
**INFERENCE:** Unrelated infrastructure degradation (storage or network) on the database host. Mechanism: Degraded storage or network path increases DB query latency and CPU.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- none

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-postgres-disk_io_wait_ms-1220-1315` (moderate): postgres disk_io_wait_ms: baseline 1.99 -> window mean 1.99 (max 2.18, change -0.3%), onset none detected
- [OBSERVED EVIDENCE] `met-postgres-p95_latency_ms-1220-1315` (moderate): postgres p95_latency_ms: baseline 11.97 -> window mean 12.13 (max 13.2, change 1.3%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Host-level network and storage metrics

## Critic Review
- **Verdict:** `NOT_RUN` (rounds reviewed: 0)
- **Reasoning:** 

## Probable Root Cause
MOST PROBABLE EXPLANATION (INFERENCE, not confirmed): configuration_regression in user-service - Enabling feature.profile_v2_cache (12:10) inflated cached profile payloads ~4.1x, causing cache pressure and misses that push profile reads onto Postgres, saturating CPU/connections and causing slow user-profile queries and timeouts.

## Corrective Actions
- Roll back feature.profile_v2_cache to false (OPS-2229) and confirm Postgres CPU and user-service p95 recover
- Once rolled back, verify that DB CPU returns to the ~35% baseline
- Review report_rollup() scheduling to confirm it is not overlapping peak hours

## Preventive Actions
- Gate feature flags that change cached payload size behind a canary and a cache-capacity check
- Add a pre-change review for flags that change payload size or cache behaviour
- Add cache-size and eviction budget tests to the flag rollout checklist

## Monitoring Recommendations
- Alert on Redis/user-service cache hit rate and evictions (not currently collected)
- Alert on cache-miss fallback rate to the DB
- Alert on Postgres statement durations above 1s for users queries
- Track user-service timeout_rate and p95 latency against the DB CPU

## Evidence Gaps
- none recorded

## Limitations
- Causal link between the flag change and DB load is inferred from timing and log messages, not verified by a controlled test
- Historical incident similarity is only an analogy
- The 35-minute gap between the flag change (12:10) and the onset (12:45) is not fully explained
- [agent-reported gap] No cache_hit_rate for user-service (metric not collected) and no Redis telemetry
- [agent-reported gap] No pg_stat_activity or pg_stat_statements data to attribute CPU to specific queries
- [agent-reported gap] No logs of report_rollup after 12:35 to rule it in or out for the 12:45+ window
- [agent-reported gap] Log output is sampled/truncated (2 records omitted), so exact miss volumes are unknown
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: agent submitted

## Final Status
`PROBABLE_ROOT_CAUSE`

The most likely root cause is the profile_v2_cache feature flag enabled at 12:10, which increased cached payload size ~4x and led to cache misses falling back to Postgres, driving CPU saturation and user-service timeouts from ~12:45. The bad-query theory is not well supported: the slow statement is a simple PK lookup, and report_rollup ran before the CPU rise. The cache-to-DB causal link is plausible and temporally ordered but not directly measured, because Redis and cache hit telemetry are missing. Confidence is moderate.

## Execution Statistics
```json
{
  "rounds": 1,
  "tool_calls": 10,
  "tool_failures": 0,
  "tool_retries": 0,
  "partial_results": 0,
  "agent_failures": 0,
  "agent_retries": 0,
  "invalid_llm_outputs": 0,
  "messages_exchanged": 0,
  "evidence_records": 65,
  "duration_s": 26.25,
  "tokens": {
    "input_tokens": 10,
    "output_tokens": 5728,
    "cache_read_tokens": 39646,
    "cache_write_tokens": 5524,
    "llm_calls": 4,
    "cost_usd": 0.00395196
  },
  "tokens_by_agent": {
    "single_agent": {
      "input_tokens": 10,
      "output_tokens": 5728,
      "cache_read_tokens": 39646,
      "cache_write_tokens": 5524,
      "llm_calls": 4,
      "cost_usd": 0.00395196
    }
  }
}
```
