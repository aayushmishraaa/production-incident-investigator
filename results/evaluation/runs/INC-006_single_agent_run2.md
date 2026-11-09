# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-006
- **Title:** User profile errors
- **Severity:** SEV2
- **Affected services:** user-service
- **Start time:** 2026-09-17T21:05:00+00:00
- **Investigation ID:** inv-af3b7d5692 (single_agent)
- **Final status:** `PROBABLE_ROOT_CAUSE`

## Executive Summary
user-service error rate rose from ~0.4% to ~30% and timeouts from ~0.05% to ~9% starting 21:03Z (T0 reported 21:05Z). Errors are PSQLException "Connection to postgres-primary:5432 refused" and "connection reset by peer", i.e. connection-establishment/transport failures rather than pool exhaustion (user-service DB connection utilisation stayed flat at ~30%). One kernel warning, nf_conntrack table full and dropping packets on usr-node-3, was logged at 21:02Z, one minute before the error onset. No deployments or config changes occurred in the window. Most likely cause is connection-tracking exhaustion on the user-service node network path dropping database packets. This is not confirmed: the conntrack log is a single event and I could not verify that the failing connections are confined to usr-node-3.

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
### 1. H1 - `infrastructure_degradation` in `user-service` (confidence 0.55, critic: n/a)
**INFERENCE:** Node-level nf_conntrack table exhaustion on usr-node-3 dropped new/established TCP packets to postgres-primary, producing 'connection refused' and 'connection reset by peer' errors in user-service. Mechanism: conntrack table full -> packets dropped -> JDBC connect attempts refused/reset -> failed requests and timeouts. Error onset (21:03) follows the kernel warning (21:02) and DB connection pool utilisation is unchanged, which fits a network-layer rather than pool-level failure.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-user-service-227e81bb` (strong): 1x WARN on user-service: 'kernel: nf_conntrack: table full, dropping packet (node usr-node-3)' (first 2026-09-17T21:02:00Z, last 2026-09-17T21:02:00Z)
- [OBSERVED EVIDENCE] `log-b27e25ff` (moderate): WARN user-service: kernel: nf_conntrack: table full, dropping packet (node usr-node-3)
- [OBSERVED EVIDENCE] `logpat-user-service-f82ed4bd` (strong): 19x ERROR on user-service: 'PSQLException: Connection to postgres-primary:5432 refused (attempt 76)' (first 2026-09-17T21:03:00Z, last 2026-09-17T21:28:37Z)
- [OBSERVED EVIDENCE] `logpat-user-service-97a18e1d` (moderate): 9x ERROR on user-service: 'I/O error: connection reset by peer (postgres-primary:5432)' (first 2026-09-17T21:03:08Z, last 2026-09-17T21:27:05Z)
- [OBSERVED EVIDENCE] `met-user-service-error_rate-2035-2130` (strong): user-service error_rate: baseline 0.4 -> window mean 14.93 (max 33.51, change 3606.8%), onset 2026-09-17T21:03:00Z
- [OBSERVED EVIDENCE] `met-user-service-timeout_rate-2035-2130` (strong): user-service timeout_rate: baseline 0.05 -> window mean 4.4 (max 9.91, change 8712.6%), onset 2026-09-17T21:03:00Z
- [OBSERVED EVIDENCE] `met-user-service-db_conn_util_pct-2035-2130` (moderate): user-service db_conn_util_pct: baseline 29.86 -> window mean 30.08 (max 33.37, change 0.7%), onset none detected
- [INFERENCE] `hist-HIST-2025-073` (weak): Past incident HIST-2025-073 'User service DB errors from node network issue' (similarity 0.484): Node conntrack table exhaustion dropped DB packets for one service.

Contradicting evidence:
- [OBSERVED EVIDENCE] `logpat-user-service-227e81bb` (weak): 1x WARN on user-service: 'kernel: nf_conntrack: table full, dropping packet (node usr-node-3)' (first 2026-09-17T21:02:00Z, last 2026-09-17T21:02:00Z)
- [OBSERVED EVIDENCE] `met-user-service-p99_latency_ms-2035-2130` (weak): user-service p99_latency_ms: baseline 161.96 -> window mean 161.17 (max 176.5, change -0.5%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Per-node breakdown of errors (is usr-node-3 the only failing node?)
- [UNKNOWN] Node-level conntrack usage metrics over time
- [UNKNOWN] Network-level drop counters between user-service and postgres

### 2. H2 - `resource_saturation` in `postgres` (confidence 0.20, critic: n/a)
**INFERENCE:** Long-running report_rollup() queries on the primary (11-20 s each) degraded database availability and caused connection resets/refusals. Mechanism: Heavy analytics queries hold resources on postgres, leading to backend slowness and connection failures for user-service.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-postgres-44883ca5` (moderate): 5x WARN on postgres: 'duration: 14502 ms statement: SELECT report_rollup()' (first 2026-09-17T20:50:35Z, last 2026-09-17T21:22:05Z)

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-user-service-p99_latency_ms-2035-2130` (moderate): user-service p99_latency_ms: baseline 161.96 -> window mean 161.17 (max 176.5, change -0.5%), onset none detected
- [OBSERVED EVIDENCE] `met-postgres-cpu_pct-2035-2130` (weak): postgres cpu_pct: baseline 35.12 -> window mean 35.39 (max 38.98, change 0.8%), onset none detected, 31 points missing
- [OBSERVED EVIDENCE] `logpat-postgres-44883ca5` (weak): 5x WARN on postgres: 'duration: 14502 ms statement: SELECT report_rollup()' (first 2026-09-17T20:50:35Z, last 2026-09-17T21:22:05Z)

Remaining uncertainties / missing evidence:
- [UNKNOWN] postgres CPU/connection metrics after 21:00 (telemetry gap)
- [UNKNOWN] postgres max_connections and rejected-connection counts

### 3. H3 - `db_connection_pool_exhaustion` in `user-service` (confidence 0.05, critic: n/a)
**INFERENCE:** user-service connection pool leak or saturation. Mechanism: Pool exhaustion would cause acquisition timeouts and rising pool utilisation.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `met-user-service-timeout_rate-2035-2130` (weak): user-service timeout_rate: baseline 0.05 -> window mean 4.4 (max 9.91, change 8712.6%), onset 2026-09-17T21:03:00Z

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-user-service-db_conn_util_pct-2035-2130` (strong): user-service db_conn_util_pct: baseline 29.86 -> window mean 30.08 (max 33.37, change 0.7%), onset none detected
- [OBSERVED EVIDENCE] `logpat-user-service-f82ed4bd` (moderate): 19x ERROR on user-service: 'PSQLException: Connection to postgres-primary:5432 refused (attempt 76)' (first 2026-09-17T21:03:00Z, last 2026-09-17T21:28:37Z)

Remaining uncertainties / missing evidence:
- [UNKNOWN] Pool wait-time metrics

## Critic Review
- **Verdict:** `NOT_RUN` (rounds reviewed: 0)
- **Reasoning:** 

## Probable Root Cause
MOST PROBABLE EXPLANATION (INFERENCE, not confirmed): infrastructure_degradation in user-service - Node-level nf_conntrack table exhaustion on usr-node-3 dropped new/established TCP packets to postgres-primary, producing 'connection refused' and 'connection reset by peer' errors in user-service.

## Corrective Actions
- Raise nf_conntrack_max on usr-nodes or drain/reschedule user-service pods off usr-node-3
- Confirm error recovery after node remediation and verify error_rate returns to baseline (~0.4%)
- Investigate and throttle the report_rollup() job on postgres-primary that runs 11-20 s

## Preventive Actions
- Add alerting on nf_conntrack usage (>80% of nf_conntrack_max) per node
- Ensure connection-pool and node network dashboards are included in user-service runbooks
- Move heavy report_rollup() to a replica or off-peak schedule

## Monitoring Recommendations
- Per-node nf_conntrack count/max and drop counters for all usr-nodes
- user-service errors grouped by node and by error class (refused / reset / timeout)
- postgres-primary connection counts, max_connections headroom, and telemetry completeness (metrics-agent backlog seen at 20:59Z)
- Duration of report_rollup() statements

## Evidence Gaps
- [UNKNOWN] query_logs failed for service=postgres-primary: unknown service 'postgres-primary'. Known: ['api-gateway', 'auth-service', 'message-queue', 'notification-service', 'order-service', 'payment-service', 'postgres', 'redis', 'user-service'] (INVALID_QUERY)
- [UNKNOWN] query_metrics failed for service=postgres-primary, metrics=['cpu_pct', 'db_conn_util_pct', 'error_rate', 'disk_io_wait_ms', 'memory_pct']: unknown service 'postgres-primary'. Known: ['api-gateway', 'auth-service', 'message-queue', 'notification-service', 'order-service', 'payment-service', 'postgres', 'redis', 'user-service'] (INVALID_QUERY)

## Limitations
- Historical incident similarity is only an analogy
- Telemetry is incomplete for the database side during the window
- Temporal ordering supports but does not prove causation
- [agent-reported gap] postgres metrics are missing 31 of 56 datapoints after 21:00Z (metrics-agent export backlog), so DB-side health during the incident is unverified
- [agent-reported gap] Tool calls using 'postgres-primary' as a service name failed (unknown service); the postgres service was used instead
- [agent-reported gap] No per-node error breakdown, so it is unknown whether errors come only from usr-node-3
- [agent-reported gap] No conntrack utilisation metrics, only a single kernel log line
- [agent-reported gap] timeout_rate is not collected for postgres
- 2 tool calls failed and 0 returned partial data; affected areas are treated as unknown, not healthy.
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: agent submitted

## Final Status
`PROBABLE_ROOT_CAUSE`

Most likely: the incident is a node-level network failure on usr-node-3 (conntrack table exhaustion), which dropped user-service's connections to postgres-primary starting 21:02-21:03Z. Pool exhaustion is ruled out by flat pool utilisation, and the postgres report_rollup slowdown is a weaker alternative with no matching latency signal. Confidence is moderate because per-node attribution and conntrack-usage metrics are missing and postgres telemetry is incomplete after 21:00.

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
  "evidence_records": 53,
  "duration_s": 23.03,
  "tokens": {
    "input_tokens": 10,
    "output_tokens": 5443,
    "cache_read_tokens": 28931,
    "cache_write_tokens": 10465,
    "llm_calls": 4,
    "cost_usd": 0.004319935
  },
  "tokens_by_agent": {
    "single_agent": {
      "input_tokens": 10,
      "output_tokens": 5443,
      "cache_read_tokens": 28931,
      "cache_write_tokens": 10465,
      "llm_calls": 4,
      "cost_usd": 0.004319935
    }
  }
}
```
