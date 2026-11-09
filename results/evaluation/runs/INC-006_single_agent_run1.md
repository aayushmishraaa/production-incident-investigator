# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-006
- **Title:** User profile errors
- **Severity:** SEV2
- **Affected services:** user-service
- **Start time:** 2026-09-17T21:05:00+00:00
- **Investigation ID:** inv-a80df30149 (single_agent)
- **Final status:** `PROBABLE_ROOT_CAUSE`

## Executive Summary
user-service error rate rose from ~0.4% to ~30% and timeout rate from ~0.05% to ~9% starting 21:03Z, five minutes into the T0 window. Logs show repeated "connection refused" and "connection reset by peer" errors to postgres-primary:5432. One kernel conntrack "table full, dropping packet" warning was logged on usr-node-3 at 21:02Z, one minute before onset. The database itself shows no clear saturation at onset, and its telemetry is missing from 21:00 onward. The most likely cause is a connection-layer failure between user-service nodes and the database, probably related to the conntrack exhaustion on usr-node-3. This is not confirmed: the per-node error breakdown and network-level data are missing.

## Incident Timeline
| Time (UTC) | Label | Event | Evidence |
|---|---|---|---|
| 2026-09-17T20:36:15Z | OBSERVED EVIDENCE | First log: 7x WARN on user-service: 'Deprecated API /v1/users/legacy called by client web-59' (first 2026-09-17T20:36:15Z, last 2026-09-17T21:21:22Z) | logpat-user-service-742b555e |
| 2026-09-17T20:50:35Z | OBSERVED EVIDENCE | First log: 5x WARN on postgres: 'duration: 14502 ms statement: SELECT report_rollup()' (first 2026-09-17T20:50:35Z, last 2026-09-17T21:22:05Z) | logpat-postgres-44883ca5 |
| 2026-09-17T21:03:00Z | OBSERVED EVIDENCE | Anomaly onset: user-service error_rate: baseline 0.4 -> window mean 14.93 (max 33.51, change 3606.8%), onset 2026-09-17T21:03:00Z | met-user-service-error_rate-2035-2130 |
| 2026-09-17T21:03:00Z | OBSERVED EVIDENCE | Anomaly onset: user-service timeout_rate: baseline 0.05 -> window mean 4.4 (max 9.91, change 8712.6%), onset 2026-09-17T21:03:00Z | met-user-service-timeout_rate-2035-2130 |
| 2026-09-17T21:03:00Z | OBSERVED EVIDENCE | First log: 19x ERROR on user-service: 'PSQLException: Connection to postgres-primary:5432 refused (attempt 76)' (first 2026-09-17T21:03:00Z, last 2026-09-17T21:28:37Z) | logpat-user-service-f82ed4bd |
| 2026-09-17T21:03:08Z | OBSERVED EVIDENCE | First log: 9x ERROR on user-service: 'I/O error: connection reset by peer (postgres-primary:5432)' (first 2026-09-17T21:03:08Z, last 2026-09-17T21:27:05Z) | logpat-user-service-97a18e1d |
| 2026-09-17T21:05:00Z | CONFIRMED FACT | Reported symptom start |  |
| 2026-09-17T21:11:00Z | CONFIRMED FACT | Incident reported |  |

## Observed Symptoms
- **OBSERVED EVIDENCE:** user-service error_rate: baseline 0.4 -> window mean 14.93 (max 33.51, change 3606.8%), onset 2026-09-17T21:03:00Z (met-user-service-error_rate-2035-2130)
- **OBSERVED EVIDENCE:** user-service timeout_rate: baseline 0.05 -> window mean 4.4 (max 9.91, change 8712.6%), onset 2026-09-17T21:03:00Z (met-user-service-timeout_rate-2035-2130)

## Investigation Performed

## Root-Cause Hypotheses (ranked by evidence strength)
### 1. H1 - `infrastructure_degradation` in `user-service` (confidence 0.50, critic: n/a)
**INFERENCE:** Connection tracking table exhaustion on user-service node usr-node-3 causes dropped/reset TCP sessions to postgres, producing intermittent connection-refused and reset errors. Mechanism: nf_conntrack table fills at ~21:02, new connections from usr-node-3 are dropped or reset; the pool retries (attempt counters up to 91) and requests time out, raising error and timeout rates in user-service.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-user-service-227e81bb` (moderate): 1x WARN on user-service: 'kernel: nf_conntrack: table full, dropping packet (node usr-node-3)' (first 2026-09-17T21:02:00Z, last 2026-09-17T21:02:00Z)
- [OBSERVED EVIDENCE] `log-b27e25ff` (moderate): WARN user-service: kernel: nf_conntrack: table full, dropping packet (node usr-node-3)
- [OBSERVED EVIDENCE] `logpat-user-service-f82ed4bd` (strong): 19x ERROR on user-service: 'PSQLException: Connection to postgres-primary:5432 refused (attempt 76)' (first 2026-09-17T21:03:00Z, last 2026-09-17T21:28:37Z)
- [OBSERVED EVIDENCE] `logpat-user-service-97a18e1d` (moderate): 9x ERROR on user-service: 'I/O error: connection reset by peer (postgres-primary:5432)' (first 2026-09-17T21:03:08Z, last 2026-09-17T21:27:05Z)
- [OBSERVED EVIDENCE] `met-user-service-error_rate-2035-2130` (strong): user-service error_rate: baseline 0.4 -> window mean 14.93 (max 33.51, change 3606.8%), onset 2026-09-17T21:03:00Z
- [OBSERVED EVIDENCE] `met-user-service-timeout_rate-2035-2130` (strong): user-service timeout_rate: baseline 0.05 -> window mean 4.4 (max 9.91, change 8712.6%), onset 2026-09-17T21:03:00Z
- [OBSERVED EVIDENCE] `met-user-service-p99_latency_ms-2035-2130` (weak): user-service p99_latency_ms: baseline 161.96 -> window mean 161.17 (max 176.5, change -0.5%), onset none detected

Contradicting evidence:
- [OBSERVED EVIDENCE] `logpat-user-service-227e81bb` (moderate): 1x WARN on user-service: 'kernel: nf_conntrack: table full, dropping packet (node usr-node-3)' (first 2026-09-17T21:02:00Z, last 2026-09-17T21:02:00Z)

Remaining uncertainties / missing evidence:
- [UNKNOWN] Per-node breakdown of user-service errors (is usr-node-3 the only source?)
- [UNKNOWN] Network or conntrack utilisation metrics for usr-node-3 and the other nodes
- [UNKNOWN] Postgres-side connection/accept counters (max_connections, listen queue) during 21:00-21:30

### 2. H2 - `resource_saturation` in `postgres` (confidence 0.20, critic: n/a)
**INFERENCE:** Long-running report_rollup() queries on postgres saturate the primary, causing connection acceptance failures and resets for user-service. Mechanism: report_rollup() runs for 11-20 seconds from 20:50 onward, holding resources and possibly exhausting connection slots or backend processes, so new connections are refused or reset.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-postgres-44883ca5` (moderate): 5x WARN on postgres: 'duration: 14502 ms statement: SELECT report_rollup()' (first 2026-09-17T20:50:35Z, last 2026-09-17T21:22:05Z)
- [OBSERVED EVIDENCE] `log-74bd915b` (weak): WARN postgres: duration: 19602 ms statement: SELECT report_rollup()

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-postgres-db_conn_util_pct-2035-2130` (moderate): postgres db_conn_util_pct: baseline 39.51 -> window mean 39.92 (max 44.21, change 1.0%), onset none detected, 31 points missing
- [OBSERVED EVIDENCE] `met-postgres-cpu_pct-2035-2130` (weak): postgres cpu_pct: baseline 35.12 -> window mean 35.39 (max 38.98, change 0.8%), onset none detected, 31 points missing
- [OBSERVED EVIDENCE] `logpat-postgres-44883ca5` (weak): 5x WARN on postgres: 'duration: 14502 ms statement: SELECT report_rollup()' (first 2026-09-17T20:50:35Z, last 2026-09-17T21:22:05Z)

Remaining uncertainties / missing evidence:
- [UNKNOWN] Postgres telemetry for 21:00-21:30 (31 of 56 datapoints missing)
- [UNKNOWN] Postgres max_connections / backend counts and lock-wait data

### 3. H3 - `upstream_dependency_degradation` in `postgres` (confidence 0.10, critic: n/a)
**INFERENCE:** Database telemetry gaps and metrics-agent export backlog hid a real database-side outage. Mechanism: A metrics-agent backlog at 20:59 delayed telemetry, so the database may have had problems that the dashboards cannot show.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-postgres-42ecece2` (moderate): 1x INFO on postgres: 'metrics-agent: export queue backlog, telemetry delayed' (first 2026-09-17T20:59:00Z, last 2026-09-17T20:59:00Z)
- [OBSERVED EVIDENCE] `met-postgres-cpu_pct-2035-2130` (weak): postgres cpu_pct: baseline 35.12 -> window mean 35.39 (max 38.98, change 0.8%), onset none detected, 31 points missing

Contradicting evidence:
- [OBSERVED EVIDENCE] `logpat-postgres-72cfef4c` (weak): 3x INFO on postgres: 'checkpoint complete: wrote 95 buffers' (first 2026-09-17T21:04:59Z, last 2026-09-17T21:25:17Z)

Remaining uncertainties / missing evidence:
- [UNKNOWN] Health checks for postgres-primary connectivity during 21:03-21:30

## Critic Review
- **Verdict:** `NOT_RUN` (rounds reviewed: 0)
- **Reasoning:** 

## Probable Root Cause
MOST PROBABLE EXPLANATION (INFERENCE, not confirmed): infrastructure_degradation in user-service - Connection tracking table exhaustion on user-service node usr-node-3 causes dropped/reset TCP sessions to postgres, producing intermittent connection-refused and reset errors.

## Corrective Actions
- Check nf_conntrack usage on all user-service nodes, especially usr-node-3, and raise nf_conntrack_max or drain and restart the affected node if it is full.
- Confirm whether errors are concentrated on usr-node-3 and fail over or drain that node from the load balancer.
- Verify postgres-primary accepts connections from user-service and that max_connections is not exceeded.

## Preventive Actions
- Alert on conntrack table utilisation above 80% on all service nodes.
- Move the report_rollup() job off the primary or bound its runtime.
- Fix the metrics-agent export backlog so database telemetry is not lost during incidents.

## Monitoring Recommendations
- Track nf_conntrack count vs max per node, and user-service error rate and timeout rate per node.
- Track postgres connection counts and rollup query duration, with alerts on any gap in postgres telemetry.
- Monitor user-service connection refused and reset counts by node.

## Evidence Gaps
- [UNKNOWN] query_logs failed for service=postgres-primary: unknown service 'postgres-primary'. Known: ['api-gateway', 'auth-service', 'message-queue', 'notification-service', 'order-service', 'payment-service', 'postgres', 'redis', 'user-service'] (INVALID_QUERY)
- [UNKNOWN] query_metrics failed for service=postgres-primary, metrics=['cpu_pct', 'db_conn_util_pct', 'error_rate', 'timeout_rate', 'memory_pct']: unknown service 'postgres-primary'. Known: ['api-gateway', 'auth-service', 'message-queue', 'notification-service', 'order-service', 'payment-service', 'postgres', 'redis', 'user-service'] (INVALID_QUERY)

## Limitations
- Errors and telemetry may have been delayed by the metrics-agent backlog.
- The conntrack warning is a single log line and is not proof of causation.
- Temporal correlation between the 21:02 conntrack warning and the 21:03 onset is not causation.
- [agent-reported gap] Telemetry for postgres is missing for 31 of 56 datapoints from 21:00 onward; query_metrics returned postgres as a service, but timeout_rate is not collected for it.
- [agent-reported gap] The query for 'postgres-primary' failed because it is not a known service name. The database is registered as 'postgres'.
- [agent-reported gap] No per-node breakdown of user-service errors.
- [agent-reported gap] No network or conntrack utilisation metrics beyond one log line.
- [agent-reported gap] Historical incident search was not run.
- 2 tool calls failed and 0 returned partial data; affected areas are treated as unknown, not healthy.
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: agent submitted

## Final Status
`PROBABLE_ROOT_CAUSE`

The most likely cause is a connection-layer failure between user-service and postgres starting 21:03Z. The best candidate is conntrack exhaustion on usr-node-3 (H1), but the evidence is limited: one warning on one node, no per-node error breakdown, and no network metrics. Postgres-side saturation from report_rollup (H2) is less likely because connection utilisation stayed normal in the available telemetry. No deployment or configuration change was recorded in the window. Final status is PROBABLE, not ROOT_CAUSE_IDENTIFIED.

## Execution Statistics
```json
{
  "rounds": 1,
  "tool_calls": 11,
  "tool_failures": 2,
  "tool_retries": 0,
  "partial_results": 0,
  "agent_failures": 0,
  "agent_retries": 0,
  "invalid_llm_outputs": 0,
  "messages_exchanged": 0,
  "evidence_records": 51,
  "duration_s": 24.2,
  "tokens": {
    "input_tokens": 10,
    "output_tokens": 5673,
    "cache_read_tokens": 24251,
    "cache_write_tokens": 14455,
    "llm_calls": 4,
    "cost_usd": 0.0048868850000000005
  },
  "tokens_by_agent": {
    "single_agent": {
      "input_tokens": 10,
      "output_tokens": 5673,
      "cache_read_tokens": 24251,
      "cache_write_tokens": 14455,
      "llm_calls": 4,
      "cost_usd": 0.0048868850000000005
    }
  }
}
```
