# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-011
- **Title:** Platform-wide slowness and 429s
- **Severity:** SEV2
- **Affected services:** api-gateway, auth-service, user-service
- **Start time:** 2026-10-02T20:00:00+00:00
- **Investigation ID:** inv-f5e61099fa (single_agent)
- **Final status:** `PROBABLE_ROOT_CAUSE`

## Executive Summary
Latency and 429s began at ~19:55-20:00Z, coinciding with a ~2.2-2.5x surge in request rate at api-gateway, auth-service and user-service. Logs attribute the surge to client_id=mobile-ios-7.4.0, which the gateway reports as the top client by RPS (up to ~9,500 rps) and whose traffic is flagged as retries with Retry-After ignored. The best-supported explanation is a mobile client retry storm. The user-service release 7.1.3 (19:48Z) is not supported as the cause: user-service latency and error rate were flat through the window, and the change was cosmetic.

## Incident Timeline
| Time (UTC) | Label | Event | Evidence |
|---|---|---|---|
| 2026-10-02T19:32:46Z | OBSERVED EVIDENCE | First log: 4x WARN on auth-service: 'Login rate limit hit for user id u-79' (first 2026-10-02T19:32:46Z, last 2026-10-02T20:24:31Z) | logpat-auth-service-cc8d3b87 |
| 2026-10-02T19:35:26Z | OBSERVED EVIDENCE | First log: 7x WARN on payment-service: 'Card network soft decline (code 05) for charge ch_30' (first 2026-10-02T19:35:26Z, last 2026-10-02T20:17:02Z) | logpat-payment-service-7e9bf84f |
| 2026-10-02T19:35:44Z | OBSERVED EVIDENCE | First log: 5x WARN on postgres: 'duration: 14702 ms statement: SELECT report_rollup()' (first 2026-10-02T19:35:44Z, last 2026-10-02T20:24:30Z) | logpat-postgres-44883ca5 |
| 2026-10-02T19:40:07Z | OBSERVED EVIDENCE | First log: 5x WARN on api-gateway: 'Slow client upload from 10.4.50.12 (1.9MB)' (first 2026-10-02T19:40:07Z, last 2026-10-02T20:24:11Z) | logpat-api-gateway-88b04940 |
| 2026-10-02T19:47:26Z | OBSERVED EVIDENCE | First log: 5x WARN on notification-service: 'SMTP provider throttled 1 message' (first 2026-10-02T19:47:26Z, last 2026-10-02T20:20:56Z) | logpat-notification-service-54b86179 |
| 2026-10-02T19:48:00Z | CONFIRMED FACT | Deployment of user-service 7.1.2->7.1.3 at 2026-10-02T19:48:00Z (SUCCEEDED): Copy changes on profile page | dep-78c036fc |
| 2026-10-02T19:55:00Z | OBSERVED EVIDENCE | Anomaly onset: user-service request_rate: baseline 500.78 -> window mean 1124.49 (max 1838.14, change 124.5%), onset 2026-10-02T19:55:00Z | met-user-service-request_rate-1930-2025 |
| 2026-10-02T19:55:00Z | OBSERVED EVIDENCE | Anomaly onset: api-gateway request_rate: baseline 1195.01 -> window mean 2732.17 (max 4529.1, change 128.6%), onset 2026-10-02T19:55:00Z | met-api-gateway-request_rate-1930-2025 |
| 2026-10-02T19:55:00Z | OBSERVED EVIDENCE | Anomaly onset: api-gateway cpu_pct: baseline 34.95 -> window mean 63.51 (max 92.91, change 81.7%), onset 2026-10-02T19:55:00Z | met-api-gateway-cpu_pct-1930-2025 |
| 2026-10-02T19:55:00Z | OBSERVED EVIDENCE | Anomaly onset: auth-service request_rate: baseline 903.83 -> window mean 2016.93 (max 3257.22, change 123.2%), onset 2026-10-02T19:55:00Z | met-auth-service-request_rate-1930-2025 |
| 2026-10-02T19:55:00Z | OBSERVED EVIDENCE | Anomaly onset: auth-service cpu_pct: baseline 30.15 -> window mean 55.05 (max 86.3, change 82.6%), onset 2026-10-02T19:55:00Z | met-auth-service-cpu_pct-1930-2025 |
| 2026-10-02T19:55:11Z | OBSERVED EVIDENCE | First log: 10x WARN on api-gateway: 'Rate limiter: 363% of requests from client_id=mobile-ios-7.4.0 are retries (Retry-After ignored)' (first 2026-10-02T19:55:11Z, last 2026-10-02T20:25:00Z) | logpat-api-gateway-d39f8491 |
| 2026-10-02T19:56:00Z | OBSERVED EVIDENCE | Anomaly onset: user-service cpu_pct: baseline 29.56 -> window mean 48.83 (max 71.04, change 65.2%), onset 2026-10-02T19:56:00Z | met-user-service-cpu_pct-1930-2025 |
| 2026-10-02T19:56:00Z | OBSERVED EVIDENCE | Anomaly onset: api-gateway error_rate: baseline 0.51 -> window mean 3.86 (max 7.6, change 664.0%), onset 2026-10-02T19:56:00Z | met-api-gateway-error_rate-1930-2025 |
| 2026-10-02T19:56:06Z | OBSERVED EVIDENCE | First log: 9x WARN on api-gateway: '429 Too Many Requests returned to client 58' (first 2026-10-02T19:56:06Z, last 2026-10-02T20:21:50Z) | logpat-api-gateway-8a499a8e |
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
**INFERENCE:** Retry storm from mobile-ios-7.4.0 clients that ignore Retry-After, overloading the gateway and downstream auth/user services and triggering rate-limit 429s. Mechanism: Starting ~19:55Z the mobile-ios-7.4.0 client's request volume rises sharply (request_rate 2.2x at gateway, 2.2x at auth, 2.2x at user-service). The gateway flags retries as a large share of that client's traffic with Retry-After ignored, so the retries are not backing off. CPU on the gateway (to ~90%) and auth-service (to ~77-86%) climbs in step, and the gateway begins returning 429s and error rate rises from ~0.5% to ~7%. Causality is consistent with the onset order: client surge at 19:55, then gateway/auth CPU at 19:55-20:00, then 429s at 19:56 and error rate at 19:56.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-api-gateway-d39f8491` (strong): 10x WARN on api-gateway: 'Rate limiter: 363% of requests from client_id=mobile-ios-7.4.0 are retries (Retry-After ignored)' (first 2026-10-02T19:55:11Z, last 2026-10-02T20:25:00Z)
- [OBSERVED EVIDENCE] `logpat-api-gateway-8575c4f9` (strong): 5x INFO on api-gateway: 'Top client by RPS: mobile-ios-7.4.0 (1700 rps)' (first 2026-10-02T19:56:19Z, last 2026-10-02T20:19:29Z)
- [OBSERVED EVIDENCE] `met-api-gateway-request_rate-1930-2025` (strong): api-gateway request_rate: baseline 1195.01 -> window mean 2732.17 (max 4529.1, change 128.6%), onset 2026-10-02T19:55:00Z
- [OBSERVED EVIDENCE] `met-api-gateway-error_rate-1930-2025` (strong): api-gateway error_rate: baseline 0.51 -> window mean 3.86 (max 7.6, change 664.0%), onset 2026-10-02T19:56:00Z
- [OBSERVED EVIDENCE] `met-api-gateway-cpu_pct-1930-2025` (moderate): api-gateway cpu_pct: baseline 34.95 -> window mean 63.51 (max 92.91, change 81.7%), onset 2026-10-02T19:55:00Z
- [OBSERVED EVIDENCE] `met-auth-service-request_rate-1930-2025` (moderate): auth-service request_rate: baseline 903.83 -> window mean 2016.93 (max 3257.22, change 123.2%), onset 2026-10-02T19:55:00Z
- [OBSERVED EVIDENCE] `logpat-api-gateway-8a499a8e` (moderate): 9x WARN on api-gateway: '429 Too Many Requests returned to client 58' (first 2026-10-02T19:56:06Z, last 2026-10-02T20:21:50Z)
- [INFERENCE] `hist-HIST-2025-068` (weak): Past incident HIST-2025-068 'Retry storm from mobile client' (similarity 0.48): Mobile release ignored Retry-After causing retry storm.

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-api-gateway-p99_latency_ms-1930-2025` (moderate): api-gateway p99_latency_ms: baseline 247.87 -> window mean 250.34 (max 284.94, change 1.0%), onset none detected
- [OBSERVED EVIDENCE] `met-user-service-p99_latency_ms-1930-2025` (moderate): user-service p99_latency_ms: baseline 161.15 -> window mean 161.2 (max 173.38, change 0.0%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Release or version history for the mobile-ios client (7.4.0) to explain why its retry behaviour changed.
- [UNKNOWN] Per-client breakdown of 429s and of the gateway's rate-limit configuration.
- [UNKNOWN] Latency by endpoint or client segment, to reconcile flat p99 with the reported slowness.

### 2. H2 - `deployment_regression` in `user-service` (confidence 0.10, critic: n/a)
**INFERENCE:** The user-service 7.1.3 release (19:48Z) caused a regression that produced the slowness and 429s. Mechanism: A new user-service build could in theory increase per-request cost or call amplification, which could explain the CPU rise and downstream load.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [CONFIRMED FACT] `dep-78c036fc` (weak): Deployment of user-service 7.1.2->7.1.3 at 2026-10-02T19:48:00Z (SUCCEEDED): Copy changes on profile page
- [OBSERVED EVIDENCE] `met-user-service-cpu_pct-1930-2025` (weak): user-service cpu_pct: baseline 29.56 -> window mean 48.83 (max 71.04, change 65.2%), onset 2026-10-02T19:56:00Z

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-user-service-p99_latency_ms-1930-2025` (strong): user-service p99_latency_ms: baseline 161.15 -> window mean 161.2 (max 173.38, change 0.0%), onset none detected
- [OBSERVED EVIDENCE] `met-user-service-error_rate-1930-2025` (strong): user-service error_rate: baseline 0.4 -> window mean 0.4 (max 0.43, change -0.5%), onset none detected
- [OBSERVED EVIDENCE] `met-user-service-timeout_rate-1930-2025` (moderate): user-service timeout_rate: baseline 0.05 -> window mean 0.05 (max 0.06, change -0.3%), onset none detected
- [OBSERVED EVIDENCE] `met-user-service-request_rate-1930-2025` (strong): user-service request_rate: baseline 500.78 -> window mean 1124.49 (max 1838.14, change 124.5%), onset 2026-10-02T19:55:00Z
- [OBSERVED EVIDENCE] `logpat-user-service-742b555e` (weak): 1x WARN on user-service: 'Deprecated API /v1/users/legacy called by client web-66' (first 2026-10-02T19:47:55Z, last 2026-10-02T19:47:55Z)

Remaining uncertainties / missing evidence:
- [UNKNOWN] Diff of 7.1.3 beyond the change summary.
- [UNKNOWN] Per-endpoint latency for the profile page.

### 3. H3 - `resource_saturation` in `postgres` (confidence 0.10, critic: n/a)
**INFERENCE:** A slow report_rollup() query on postgres (background load) is saturating the database and degrading the platform. Mechanism: Long-running SELECT report_rollup() statements (11-15 s) could consume DB capacity and slow services that query postgres.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-postgres-44883ca5` (moderate): 5x WARN on postgres: 'duration: 14702 ms statement: SELECT report_rollup()' (first 2026-10-02T19:35:44Z, last 2026-10-02T20:24:30Z)

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-user-service-db_conn_util_pct-1930-2025` (strong): user-service db_conn_util_pct: baseline 30.04 -> window mean 30.17 (max 33.21, change 0.4%), onset none detected
- [OBSERVED EVIDENCE] `logpat-postgres-44883ca5` (moderate): 5x WARN on postgres: 'duration: 14702 ms statement: SELECT report_rollup()' (first 2026-10-02T19:35:44Z, last 2026-10-02T20:24:30Z)

Remaining uncertainties / missing evidence:
- [UNKNOWN] Postgres CPU, lock and connection metrics (no telemetry was queried for postgres).

## Critic Review
- **Verdict:** `NOT_RUN` (rounds reviewed: 0)
- **Reasoning:** 

## Probable Root Cause
MOST PROBABLE EXPLANATION (INFERENCE, not confirmed): traffic_surge in api-gateway - Retry storm from mobile-ios-7.4.0 clients that ignore Retry-After, overloading the gateway and downstream auth/user services and triggering rate-limit 429s.

## Corrective Actions
- Throttle or block mobile-ios-7.4.0 at the gateway (per-client rate limit or client-version block) to stop the retry amplification.
- Enforce server-side backoff: return and honour Retry-After, and apply a circuit breaker or 429 shedding at the gateway.
- Roll back or hotfix the mobile-ios-7.4.0 client retry behaviour, and coordinate with mobile release owners.
- Hold a rollback of user-service 7.1.3 in reserve; roll it back only if the surge is ruled out and user-service degrades.

## Preventive Actions
- Require client SDK tests that verify Retry-After compliance before release.
- Add gateway-side retry-budget enforcement per client, with alerts on retry ratio.
- Add canary and per-client-version monitoring for mobile releases.

## Monitoring Recommendations
- Alert on per-client request rate and retry ratio at api-gateway (threshold, e.g., retries >50% of a client's traffic).
- Alert on gateway 429 rate and error rate above 1%.
- Monitor gateway and auth CPU, and track p95/p99 latency per endpoint so slowness is not hidden by flat aggregate p99.
- Monitor postgres report_rollup() duration as a separate background-load signal.

## Evidence Gaps
- none recorded

## Limitations
- No telemetry was queried for postgres, the notification or order services, or the mobile client itself.
- Telemetry is aggregated per service; per-client latency was not available.
- The 429 log patterns are sampled, so exact 429 volume is unknown.
- [agent-reported gap] Release/trigger for mobile-ios-7.4.0 is unknown.
- [agent-reported gap] Flat user-service and gateway p99 latency conflicts with the reported slowness and was not explained.
- [agent-reported gap] No postgres or DB-side metrics were examined for the report_rollup() statements.
- [agent-reported gap] No per-client latency or 429 breakdown was available.
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: agent submitted

## Final Status
`PROBABLE_ROOT_CAUSE`

INC-011's most likely root cause is a retry storm from mobile-ios-7.4.0 clients that ignore Retry-After, starting ~19:55Z. This drove a ~2.2x request surge that saturated gateway and auth CPU and produced the 429s and gateway error rate. The user-service 7.1.3 release at 19:48Z is not supported as the cause: its latency, error and timeout metrics are flat, and the traffic surge it coincides with is external. The status is PROBABLE rather than confirmed because the mobile client's release trigger and the cause of the flat p99 latency are not established.

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
  "evidence_records": 70,
  "duration_s": 24.97,
  "tokens": {
    "input_tokens": 8,
    "output_tokens": 5843,
    "cache_read_tokens": 17463,
    "cache_write_tokens": 16814,
    "llm_calls": 3,
    "cost_usd": 0.00519868
  },
  "tokens_by_agent": {
    "single_agent": {
      "input_tokens": 8,
      "output_tokens": 5843,
      "cache_read_tokens": 17463,
      "cache_write_tokens": 16814,
      "llm_calls": 3,
      "cost_usd": 0.00519868
    }
  }
}
```
