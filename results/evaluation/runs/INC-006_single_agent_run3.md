# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-006
- **Title:** User profile errors
- **Severity:** SEV2
- **Affected services:** user-service
- **Start time:** 2026-09-17T21:05:00+00:00
- **Investigation ID:** inv-234949d997 (single_agent)
- **Final status:** `PROBABLE_ROOT_CAUSE`

## Executive Summary
user-service errors began at 21:03Z, about 2 minutes after a kernel nf_conntrack "table full" event on usr-node-3 (21:02Z). Error rate rose from ~0.4% to ~30% and timeouts from 0.05% to ~9%. Errors are PSQLException "connection refused" and "connection reset by peer" to postgres-primary:5432, so the failure is at the network/connection layer, not pool exhaustion (user-service DB connection utilisation stayed flat at ~30%, baseline 29.9%). The most likely cause is conntrack exhaustion on usr-node-3 dropping DB packets. This is unconfirmed: the log does not say whether other nodes are affected, and PostgreSQL-side telemetry is missing for the window.

## Incident Timeline
| Time (UTC) | Label | Event | Evidence |
|---|---|---|---|
| 2026-09-17T20:32:04Z | OBSERVED EVIDENCE | First log: 7x WARN on postgres: 'duration: 12902 ms statement: SELECT report_rollup()' (first 2026-09-17T20:32:04Z, last 2026-09-17T21:35:22Z) | logpat-postgres-44883ca5 |
| 2026-09-17T20:36:15Z | OBSERVED EVIDENCE | First log: 7x WARN on user-service: 'Deprecated API /v1/users/legacy called by client web-59' (first 2026-09-17T20:36:15Z, last 2026-09-17T21:21:22Z) | logpat-user-service-742b555e |
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
### 1. H1 - `infrastructure_degradation` in `user-service` (confidence 0.70, critic: n/a)
**INFERENCE:** nf_conntrack table exhaustion on usr-node-3 drops user-service -> postgres-primary connections, producing refused/reset errors and timeouts. Mechanism: The conntrack table filled on usr-node-3 at 21:02Z and the kernel began dropping packets. New and existing TCP sessions to postgres-primary:5432 from that node were refused or reset. user-service retries fail, which surfaces as DB errors and timeouts. Onset of the error spike (21:03Z) follows the kernel event by about one minute.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-user-service-227e81bb` (strong): 1x WARN on user-service: 'kernel: nf_conntrack: table full, dropping packet (node usr-node-3)' (first 2026-09-17T21:02:00Z, last 2026-09-17T21:02:00Z)
- [OBSERVED EVIDENCE] `log-b27e25ff` (strong): WARN user-service: kernel: nf_conntrack: table full, dropping packet (node usr-node-3)
- [OBSERVED EVIDENCE] `logpat-user-service-f82ed4bd` (strong): 19x ERROR on user-service: 'PSQLException: Connection to postgres-primary:5432 refused (attempt 76)' (first 2026-09-17T21:03:00Z, last 2026-09-17T21:28:37Z)
- [OBSERVED EVIDENCE] `logpat-user-service-97a18e1d` (moderate): 9x ERROR on user-service: 'I/O error: connection reset by peer (postgres-primary:5432)' (first 2026-09-17T21:03:08Z, last 2026-09-17T21:27:05Z)
- [OBSERVED EVIDENCE] `met-user-service-error_rate-2035-2130` (strong): user-service error_rate: baseline 0.4 -> window mean 14.93 (max 33.51, change 3606.8%), onset 2026-09-17T21:03:00Z
- [OBSERVED EVIDENCE] `met-user-service-timeout_rate-2035-2130` (moderate): user-service timeout_rate: baseline 0.05 -> window mean 4.4 (max 9.91, change 8712.6%), onset 2026-09-17T21:03:00Z
- [INFERENCE] `hist-HIST-2025-073` (weak): Past incident HIST-2025-073 'User service DB errors from node network issue' (similarity 0.494): Node conntrack table exhaustion dropped DB packets for one service.

Contradicting evidence:
- [OBSERVED EVIDENCE] `logpat-user-service-227e81bb` (moderate): 1x WARN on user-service: 'kernel: nf_conntrack: table full, dropping packet (node usr-node-3)' (first 2026-09-17T21:02:00Z, last 2026-09-17T21:02:00Z)
- [OBSERVED EVIDENCE] `met-user-service-db_conn_util_pct-2035-2130` (moderate): user-service db_conn_util_pct: baseline 29.86 -> window mean 30.08 (max 33.37, change 0.7%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Per-node error or conntrack metrics for usr-node-1..N (not queried; no node-level metric is available in the toolset)
- [UNKNOWN] Whether errors come only from usr-node-3 (error log lacks a node field)
- [UNKNOWN] PostgreSQL-side connection and network metrics for 21:00Z onward (missing datapoints)

### 2. H2 - `resource_saturation` in `postgres` (confidence 0.15, critic: n/a)
**INFERENCE:** Long-running report_rollup() queries on the database saturate it and cause connection failures. Mechanism: report_rollup() ran for 11–20 seconds repeatedly from 20:32Z, which could hold DB resources and reject or reset new connections.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-postgres-44883ca5` (moderate): 7x WARN on postgres: 'duration: 12902 ms statement: SELECT report_rollup()' (first 2026-09-17T20:32:04Z, last 2026-09-17T21:35:22Z)
- [OBSERVED EVIDENCE] `met-postgres-cpu_pct-2035-2130` (weak): postgres cpu_pct: baseline 35.12 -> window mean 35.39 (max 38.98, change 0.8%), onset none detected, 31 points missing

Contradicting evidence:
- [OBSERVED EVIDENCE] `logpat-postgres-44883ca5` (strong): 7x WARN on postgres: 'duration: 12902 ms statement: SELECT report_rollup()' (first 2026-09-17T20:32:04Z, last 2026-09-17T21:35:22Z)
- [OBSERVED EVIDENCE] `log-cf483fe1` (moderate): WARN postgres: duration: 14502 ms statement: SELECT report_rollup()

Remaining uncertainties / missing evidence:
- [UNKNOWN] postgres CPU, connection, and error metrics for 21:00Z to 21:30Z (31 of 56 points missing)
- [UNKNOWN] Postgres max_connections and active connection counts during the window

### 3. H3 - `upstream_dependency_degradation` in `postgres-primary` (confidence 0.10, critic: n/a)
**INFERENCE:** postgres-primary itself became unavailable or failed over at about 21:00Z, refusing connections. Mechanism: If the primary restarted or stopped accepting connections, user-service would see refused and reset errors across all nodes, not just one.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `log-e9dd6ec0` (moderate): ERROR user-service: PSQLException: Connection to postgres-primary:5432 refused (attempt 76)

Contradicting evidence:
- [OBSERVED EVIDENCE] `logpat-postgres-72cfef4c` (moderate): 7x INFO on postgres: 'checkpoint complete: wrote 42 buffers' (first 2026-09-17T20:36:30Z, last 2026-09-17T21:30:42Z)
- [OBSERVED EVIDENCE] `logpat-user-service-227e81bb` (moderate): 1x WARN on user-service: 'kernel: nf_conntrack: table full, dropping packet (node usr-node-3)' (first 2026-09-17T21:02:00Z, last 2026-09-17T21:02:00Z)

Remaining uncertainties / missing evidence:
- [UNKNOWN] postgres-primary host or process health data (the service is named 'postgres' in the topology, and 'postgres-primary' was rejected as unknown by the metrics tool)

## Critic Review
- **Verdict:** `NOT_RUN` (rounds reviewed: 0)
- **Reasoning:** 

## Probable Root Cause
MOST PROBABLE EXPLANATION (INFERENCE, not confirmed): infrastructure_degradation in user-service - nf_conntrack table exhaustion on usr-node-3 drops user-service -> postgres-primary connections, producing refused/reset errors and timeouts.

## Corrective Actions
- Drain or reschedule user-service pods off usr-node-3 and confirm the error rate returns to baseline
- Raise nf_conntrack_max on usr nodes, or clear stale entries, then verify the table no longer fills

## Preventive Actions
- Alert on nf_conntrack usage above 80% on all nodes
- Review connection churn from user-service to postgres (pooling, keepalive) to reduce conntrack load
- Optimise or schedule report_rollup() so it does not run during peak traffic

## Monitoring Recommendations
- Track user-service error and timeout rate per node
- Track conntrack count vs max per node
- Restore postgres metrics-agent export so DB-side telemetry is complete
- Alert on report_rollup duration above 5s

## Evidence Gaps
- [UNKNOWN] query_metrics failed for service=postgres-primary, metrics=['cpu_pct', 'db_conn_util_pct', 'error_rate', 'memory_pct']: unknown service 'postgres-primary'. Known: ['api-gateway', 'auth-service', 'message-queue', 'notification-service', 'order-service', 'payment-service', 'postgres', 'redis', 'user-service'] (INVALID_QUERY)

## Limitations
- Telemetry was only available from T0-60m to T0+30m
- Historical match HIST-2025-073 is an analogy only
- The error log lacks node or pod identifiers
- [agent-reported gap] No per-node breakdown of user-service errors
- [agent-reported gap] Postgres telemetry missing for 21:00Z to 21:30Z (31 of 56 points)
- [agent-reported gap] The metrics tool does not recognise 'postgres-primary'; the 'postgres' service was used instead
- [agent-reported gap] No node-level conntrack metrics
- 1 tool calls failed and 0 returned partial data; affected areas are treated as unknown, not healthy.
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: agent submitted

## Final Status
`PROBABLE_ROOT_CAUSE`

The most probable cause is nf_conntrack table exhaustion on usr-node-3, which began at 21:02Z and dropped user-service's connections to postgres-primary, causing refused and reset errors from 21:03Z. There is no deployment or configuration change in the window. The status is PROBABLE rather than confirmed because per-node attribution and PostgreSQL-side telemetry are missing. The report_rollup slowness is a real but pre-existing issue that does not explain the step change at 21:03Z.

## Execution Statistics
```json
{
  "rounds": 1,
  "tool_calls": 10,
  "tool_failures": 1,
  "tool_retries": 0,
  "partial_results": 0,
  "agent_failures": 0,
  "agent_retries": 0,
  "invalid_llm_outputs": 0,
  "messages_exchanged": 0,
  "evidence_records": 60,
  "duration_s": 21.96,
  "tokens": {
    "input_tokens": 10,
    "output_tokens": 5023,
    "cache_read_tokens": 23871,
    "cache_write_tokens": 15158,
    "llm_calls": 4,
    "cost_usd": 0.004645959999999999
  },
  "tokens_by_agent": {
    "single_agent": {
      "input_tokens": 10,
      "output_tokens": 5023,
      "cache_read_tokens": 23871,
      "cache_write_tokens": 15158,
      "llm_calls": 4,
      "cost_usd": 0.004645959999999999
    }
  }
}
```
