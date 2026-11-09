# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-011
- **Title:** Platform-wide slowness and 429s
- **Severity:** SEV2
- **Affected services:** api-gateway, auth-service, user-service
- **Start time:** 2026-10-02T20:00:00+00:00
- **Investigation ID:** inv-92b5d4ac2d (single_agent)
- **Final status:** `PROBABLE_ROOT_CAUSE`

## Executive Summary
Latency and 429 errors start at ~19:55-20:00Z, when request volume into api-gateway, user-service and auth-service roughly doubled-to-tripled. Logs attribute the surge to client_id=mobile-ios-7.4.0, which is reported as the top client by RPS and whose requests are mostly retries that ignore Retry-After. The gateway's rate limiter then returns 429s, which likely drive further retries. The user-service release 7.1.3 (19:48Z) does not match the symptom pattern: its latency and error metrics are flat, and the traffic onset came after it. The most likely cause is a retry storm from the mobile-ios 7.4.0 client, not the user-service deployment.

## Incident Timeline
| Time (UTC) | Label | Event | Evidence |
|---|---|---|---|
| 2026-10-02T19:48:00Z | CONFIRMED FACT | Deployment of user-service 7.1.2->7.1.3 at 2026-10-02T19:48:00Z (SUCCEEDED): Copy changes on profile page | dep-78c036fc |
| 2026-10-02T19:54:43Z | OBSERVED EVIDENCE | First log: 3x WARN on payment-service: 'Card network soft decline (code 05) for charge ch_25' (first 2026-10-02T19:54:43Z, last 2026-10-02T20:04:34Z) | logpat-payment-service-7e9bf84f |
| 2026-10-02T19:55:00Z | OBSERVED EVIDENCE | Anomaly onset: user-service request_rate: baseline 500.78 -> window mean 1124.49 (max 1838.14, change 124.5%), onset 2026-10-02T19:55:00Z | met-user-service-request_rate-1930-2025 |
| 2026-10-02T19:55:00Z | OBSERVED EVIDENCE | Anomaly onset: api-gateway request_rate: baseline 1195.01 -> window mean 2732.17 (max 4529.1, change 128.6%), onset 2026-10-02T19:55:00Z | met-api-gateway-request_rate-1930-2025 |
| 2026-10-02T19:55:00Z | OBSERVED EVIDENCE | Anomaly onset: api-gateway cpu_pct: baseline 34.95 -> window mean 63.51 (max 92.91, change 81.7%), onset 2026-10-02T19:55:00Z | met-api-gateway-cpu_pct-1930-2025 |
| 2026-10-02T19:55:00Z | OBSERVED EVIDENCE | Anomaly onset: auth-service request_rate: baseline 903.83 -> window mean 2016.93 (max 3257.22, change 123.2%), onset 2026-10-02T19:55:00Z | met-auth-service-request_rate-1930-2025 |
| 2026-10-02T19:55:00Z | OBSERVED EVIDENCE | Anomaly onset: auth-service cpu_pct: baseline 30.15 -> window mean 55.05 (max 86.3, change 82.6%), onset 2026-10-02T19:55:00Z | met-auth-service-cpu_pct-1930-2025 |
| 2026-10-02T19:55:11Z | OBSERVED EVIDENCE | First log: 5x WARN on api-gateway: 'Rate limiter: 363% of requests from client_id=mobile-ios-7.4.0 are retries (Retry-After ignored)' (first 2026-10-02T19:55:11Z, last 2026-10-02T20:08:29Z) | logpat-api-gateway-d39f8491 |
| 2026-10-02T19:56:00Z | OBSERVED EVIDENCE | Anomaly onset: user-service cpu_pct: baseline 29.56 -> window mean 48.83 (max 71.04, change 65.2%), onset 2026-10-02T19:56:00Z | met-user-service-cpu_pct-1930-2025 |
| 2026-10-02T19:56:00Z | OBSERVED EVIDENCE | Anomaly onset: api-gateway error_rate: baseline 0.51 -> window mean 3.86 (max 7.6, change 664.0%), onset 2026-10-02T19:56:00Z | met-api-gateway-error_rate-1930-2025 |
| 2026-10-02T19:56:06Z | OBSERVED EVIDENCE | First log: 5x WARN on api-gateway: '429 Too Many Requests returned to client 58' (first 2026-10-02T19:56:06Z, last 2026-10-02T20:09:09Z) | logpat-api-gateway-8a499a8e |
| 2026-10-02T20:00:00Z | CONFIRMED FACT | Reported symptom start |  |
| 2026-10-02T20:06:00Z | CONFIRMED FACT | Incident reported |  |

## Observed Symptoms
- **OBSERVED EVIDENCE:** user-service request_rate: baseline 500.78 -> window mean 1124.49 (max 1838.14, change 124.5%), onset 2026-10-02T19:55:00Z (met-user-service-request_rate-1930-2025)
- **OBSERVED EVIDENCE:** user-service cpu_pct: baseline 29.56 -> window mean 48.83 (max 71.04, change 65.2%), onset 2026-10-02T19:56:00Z (met-user-service-cpu_pct-1930-2025)
- **OBSERVED EVIDENCE:** api-gateway error_rate: baseline 0.51 -> window mean 3.86 (max 7.6, change 664.0%), onset 2026-10-02T19:56:00Z (met-api-gateway-error_rate-1930-2025)
- **OBSERVED EVIDENCE:** api-gateway request_rate: baseline 1195.01 -> window mean 2732.17 (max 4529.1, change 128.6%), onset 2026-10-02T19:55:00Z (met-api-gateway-request_rate-1930-2025)
- **OBSERVED EVIDENCE:** api-gateway cpu_pct: baseline 34.95 -> window mean 63.51 (max 92.91, change 81.7%), onset 2026-10-02T19:55:00Z (met-api-gateway-cpu_pct-1930-2025)
- **OBSERVED EVIDENCE:** auth-service request_rate: baseline 903.83 -> window mean 2016.93 (max 3257.22, change 123.2%), onset 2026-10-02T19:55:00Z (met-auth-service-request_rate-1930-2025)
- **OBSERVED EVIDENCE:** auth-service cpu_pct: baseline 30.15 -> window mean 55.05 (max 86.3, change 82.6%), onset 2026-10-02T19:55:00Z (met-auth-service-cpu_pct-1930-2025)

## Investigation Performed

## Root-Cause Hypotheses (ranked by evidence strength)
### 1. H1 - `traffic_surge` in `api-gateway` (confidence 0.75, critic: n/a)
**INFERENCE:** Retry storm from mobile-ios-7.4.0 clients that ignore Retry-After, saturating api-gateway and downstream auth/user services and triggering 429s. Mechanism: A mobile client version (7.4.0) retries aggressively and ignores Retry-After. Request rate rose from ~1.2k to ~4k rps at the gateway starting 19:55Z. Gateway CPU rose from ~34% to ~90%, which drives 429s and latency. Downstream auth-service and user-service request rates rose ~2.2x and their CPU rose to 75-86%, while their own error and timeout rates stayed flat. Retry traffic continues because Retry-After is ignored.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `met-api-gateway-request_rate-1930-2025` (strong): api-gateway request_rate: baseline 1195.01 -> window mean 2732.17 (max 4529.1, change 128.6%), onset 2026-10-02T19:55:00Z
- [OBSERVED EVIDENCE] `met-api-gateway-cpu_pct-1930-2025` (strong): api-gateway cpu_pct: baseline 34.95 -> window mean 63.51 (max 92.91, change 81.7%), onset 2026-10-02T19:55:00Z
- [OBSERVED EVIDENCE] `met-api-gateway-error_rate-1930-2025` (strong): api-gateway error_rate: baseline 0.51 -> window mean 3.86 (max 7.6, change 664.0%), onset 2026-10-02T19:56:00Z
- [OBSERVED EVIDENCE] `logpat-api-gateway-d39f8491` (strong): 5x WARN on api-gateway: 'Rate limiter: 363% of requests from client_id=mobile-ios-7.4.0 are retries (Retry-After ignored)' (first 2026-10-02T19:55:11Z, last 2026-10-02T20:08:29Z)
- [OBSERVED EVIDENCE] `logpat-api-gateway-8575c4f9` (strong): 3x INFO on api-gateway: 'Top client by RPS: mobile-ios-7.4.0 (1700 rps)' (first 2026-10-02T19:56:19Z, last 2026-10-02T20:07:47Z)
- [OBSERVED EVIDENCE] `logpat-api-gateway-8a499a8e` (moderate): 5x WARN on api-gateway: '429 Too Many Requests returned to client 58' (first 2026-10-02T19:56:06Z, last 2026-10-02T20:09:09Z)
- [OBSERVED EVIDENCE] `met-auth-service-request_rate-1930-2025` (moderate): auth-service request_rate: baseline 903.83 -> window mean 2016.93 (max 3257.22, change 123.2%), onset 2026-10-02T19:55:00Z
- [OBSERVED EVIDENCE] `met-user-service-request_rate-1930-2025` (moderate): user-service request_rate: baseline 500.78 -> window mean 1124.49 (max 1838.14, change 124.5%), onset 2026-10-02T19:55:00Z
- [INFERENCE] `hist-HIST-2025-068` (weak): Past incident HIST-2025-068 'Retry storm from mobile client' (similarity 0.462): Mobile release ignored Retry-After causing retry storm.

Contradicting evidence:
- [UNKNOWN] `logs-gap-top-client-rps` (weak): NOT FOUND in collected evidence

Remaining uncertainties / missing evidence:
- [UNKNOWN] Client-side telemetry or app release record for mobile-ios 7.4.0 (rollout time, percentage of users)
- [UNKNOWN] Per-client request breakdown at the gateway over time, reconciled with total RPS
- [UNKNOWN] Confirmation that retries are a feedback loop triggered by 429s rather than the initial trigger

### 2. H3 - `db_connection_pool_exhaustion` in `postgres` (confidence 0.15, critic: n/a)
**INFERENCE:** Database contention (postgres report_rollup) degraded user/auth services and caused the latency. Mechanism: A 14.2s SELECT report_rollup() ran at 19:56:49Z, which could hold resources and slow services that depend on postgres.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-postgres-44883ca5` (weak): 1x WARN on postgres: 'duration: 14202 ms statement: SELECT report_rollup()' (first 2026-10-02T19:56:49Z, last 2026-10-02T19:56:49Z)

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-user-service-db_conn_util_pct-1930-2025` (strong): user-service db_conn_util_pct: baseline 30.04 -> window mean 30.17 (max 33.21, change 0.4%), onset none detected
- [OBSERVED EVIDENCE] `met-user-service-p99_latency_ms-1930-2025` (moderate): user-service p99_latency_ms: baseline 161.15 -> window mean 161.2 (max 173.38, change 0.0%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] postgres metrics (not queried)
- [UNKNOWN] Frequency of report_rollup executions

### 3. H2 - `deployment_regression` in `user-service` (confidence 0.10, critic: n/a)
**INFERENCE:** user-service 7.1.2→7.1.3 release (19:48Z) caused the platform slowdown. Mechanism: A release at 19:48Z could cause regressions, but the metrics do not match this mechanism.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [CONFIRMED FACT] `dep-78c036fc` (weak): Deployment of user-service 7.1.2->7.1.3 at 2026-10-02T19:48:00Z (SUCCEEDED): Copy changes on profile page

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-user-service-p99_latency_ms-1930-2025` (strong): user-service p99_latency_ms: baseline 161.15 -> window mean 161.2 (max 173.38, change 0.0%), onset none detected
- [OBSERVED EVIDENCE] `met-user-service-error_rate-1930-2025` (strong): user-service error_rate: baseline 0.4 -> window mean 0.4 (max 0.43, change -0.5%), onset none detected
- [OBSERVED EVIDENCE] `met-user-service-db_conn_util_pct-1930-2025` (moderate): user-service db_conn_util_pct: baseline 30.04 -> window mean 30.17 (max 33.21, change 0.4%), onset none detected
- [CONFIRMED FACT] `dep-78c036fc` (moderate): Deployment of user-service 7.1.2->7.1.3 at 2026-10-02T19:48:00Z (SUCCEEDED): Copy changes on profile page

Remaining uncertainties / missing evidence:
- [UNKNOWN] user-service logs at the 19:48Z deploy time

## Critic Review
- **Verdict:** `NOT_RUN` (rounds reviewed: 0)
- **Reasoning:** 

## Probable Root Cause
MOST PROBABLE EXPLANATION (INFERENCE, not confirmed): traffic_surge in api-gateway - Retry storm from mobile-ios-7.4.0 clients that ignore Retry-After, saturating api-gateway and downstream auth/user services and triggering 429s.

## Corrective Actions
- Throttle or block mobile-ios-7.4.0 at the gateway, or enforce Retry-After server-side, to stop the retry loop
- Scale api-gateway and auth/user-service capacity temporarily if the throttle is not enough
- Coordinate with mobile team on a hotfix or forced upgrade for client 7.4.0

## Preventive Actions
- Enforce server-side backoff and per-client quotas at the gateway, and reject clients that ignore Retry-After
- Add client version-aware rate limits and canary rollout for mobile releases
- Add contract tests and client-behaviour tests for retry policy

## Monitoring Recommendations
- Alert on per-client retry ratio and requests per client_id at the gateway
- Alert on gateway request rate deviating more than 50% from baseline
- Track 429 rate by client version
- Monitor postgres report_rollup duration

## Evidence Gaps
- none recorded

## Limitations
- No client-side or app release telemetry was available
- The per-client RPS log values are inconsistent with total gateway RPS
- Postgres and redis metrics were not queried
- Log summaries were sampled and may be incomplete
- [agent-reported gap] Source of the initial traffic increase at 19:55Z (client release vs. external trigger) is not confirmed
- [agent-reported gap] No user-service logs were pulled for the 19:48Z deploy window
- [agent-reported gap] No postgres metrics for the report_rollup period
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: agent submitted

## Final Status
`PROBABLE_ROOT_CAUSE`

The incident is most consistent with a retry storm from mobile-ios-7.4.0 clients that ignore Retry-After. It began at ~19:55Z, which precedes the 429s and the latency and CPU rise. The user-service 7.1.3 deploy at 19:48Z is not supported by the metrics. Confidence is moderate because the per-client RPS figures are internally inconsistent, and the client release data was not available. The final status is PROBABLE_ROOT_CAUSE.

## Execution Statistics
```json
{
  "rounds": 1,
  "tool_calls": 9,
  "tool_failures": 0,
  "tool_retries": 0,
  "partial_results": 0,
  "agent_failures": 0,
  "agent_retries": 0,
  "invalid_llm_outputs": 0,
  "messages_exchanged": 0,
  "evidence_records": 51,
  "duration_s": 23.08,
  "tokens": {
    "input_tokens": 10,
    "output_tokens": 5299,
    "cache_read_tokens": 32587,
    "cache_write_tokens": 11590,
    "llm_calls": 4,
    "cost_usd": 0.004425119999999999
  },
  "tokens_by_agent": {
    "single_agent": {
      "input_tokens": 10,
      "output_tokens": 5299,
      "cache_read_tokens": 32587,
      "cache_write_tokens": 11590,
      "llm_calls": 4,
      "cost_usd": 0.004425119999999999
    }
  }
}
```
