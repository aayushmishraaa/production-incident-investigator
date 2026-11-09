# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-011
- **Title:** Platform-wide slowness and 429s
- **Severity:** SEV2
- **Affected services:** api-gateway, auth-service, user-service
- **Start time:** 2026-10-02T20:00:00+00:00
- **Investigation ID:** inv-3e427e7a6e (single_agent)
- **Final status:** `PROBABLE_ROOT_CAUSE`

## Executive Summary
Starting ~19:55Z, request rate on api-gateway rose from ~1,195 to ~2,700 rps (peak 4,529), auth-service rose ~123% and user-service ~125%. CPU on gateway (to ~90%), auth (to ~77-86%) and user-service (to ~65%) rose in step. Gateway logs show the rate limiter flagging mobile-ios-7.4.0 retries at 314-396% of requests with Retry-After ignored, and that client is the top RPS source (~1,700 rps). The 429s are the rate limiter responding to this client. A similar past incident (HIST-2025-068) had the same mechanism. The user-service 7.1.3 deploy at 19:48Z is not supported as the cause: its metrics were flat until the surge, and it had no config changes. Confidence is moderate because no mobile release record was found and p99 latency did not clearly rise.

## Incident Timeline
| Time (UTC) | Label | Event | Evidence |
|---|---|---|---|
| 2026-10-02T19:48:00Z | CONFIRMED FACT | Deployment of user-service 7.1.2->7.1.3 at 2026-10-02T19:48:00Z (SUCCEEDED): Copy changes on profile page | dep-78c036fc |
| 2026-10-02T19:51:15Z | OBSERVED EVIDENCE | First log: 3x WARN on api-gateway: 'Slow client upload from 10.4.72.12 (1.9MB)' (first 2026-10-02T19:51:15Z, last 2026-10-02T20:24:11Z) | logpat-api-gateway-88b04940 |
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
### 1. H1 - `traffic_surge` in `None` (confidence 0.70, critic: n/a)
**INFERENCE:** Retry storm from mobile-ios-7.4.0 clients ignoring Retry-After, driving traffic surge and resource saturation across api-gateway, auth-service and user-service. Mechanism: Retries from one client version multiply request volume about 2-3x starting 19:55Z. This saturates CPU on gateway, auth and user-service, and the gateway rate limiter returns 429s to clients. The surge precedes the 429s and the CPU rise, and the surge is attributed to a single client identity.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `met-api-gateway-request_rate-1930-2025` (strong): api-gateway request_rate: baseline 1195.01 -> window mean 2732.17 (max 4529.1, change 128.6%), onset 2026-10-02T19:55:00Z
- [OBSERVED EVIDENCE] `met-auth-service-request_rate-1930-2025` (strong): auth-service request_rate: baseline 903.83 -> window mean 2016.93 (max 3257.22, change 123.2%), onset 2026-10-02T19:55:00Z
- [OBSERVED EVIDENCE] `met-user-service-request_rate-1930-2025` (strong): user-service request_rate: baseline 500.78 -> window mean 1124.49 (max 1838.14, change 124.5%), onset 2026-10-02T19:55:00Z
- [OBSERVED EVIDENCE] `met-api-gateway-cpu_pct-1930-2025` (strong): api-gateway cpu_pct: baseline 34.95 -> window mean 63.51 (max 92.91, change 81.7%), onset 2026-10-02T19:55:00Z
- [OBSERVED EVIDENCE] `met-api-gateway-error_rate-1930-2025` (strong): api-gateway error_rate: baseline 0.51 -> window mean 3.86 (max 7.6, change 664.0%), onset 2026-10-02T19:56:00Z
- [OBSERVED EVIDENCE] `logpat-api-gateway-d39f8491` (strong): 10x WARN on api-gateway: 'Rate limiter: 363% of requests from client_id=mobile-ios-7.4.0 are retries (Retry-After ignored)' (first 2026-10-02T19:55:11Z, last 2026-10-02T20:25:00Z)
- [OBSERVED EVIDENCE] `logpat-api-gateway-8575c4f9` (moderate): 5x INFO on api-gateway: 'Top client by RPS: mobile-ios-7.4.0 (1700 rps)' (first 2026-10-02T19:56:19Z, last 2026-10-02T20:19:29Z)
- [OBSERVED EVIDENCE] `logpat-api-gateway-8a499a8e` (moderate): 9x WARN on api-gateway: '429 Too Many Requests returned to client 58' (first 2026-10-02T19:56:06Z, last 2026-10-02T20:21:50Z)
- [INFERENCE] `hist-HIST-2025-068` (weak): Past incident HIST-2025-068 'Retry storm from mobile client' (similarity 0.406): Mobile release ignored Retry-After causing retry storm.

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-api-gateway-p99_latency_ms-1930-2025` (moderate): api-gateway p99_latency_ms: baseline 247.87 -> window mean 250.34 (max 284.94, change 1.0%), onset none detected
- [OBSERVED EVIDENCE] `met-user-service-p99_latency_ms-1930-2025` (moderate): user-service p99_latency_ms: baseline 161.15 -> window mean 161.2 (max 173.38, change 0.0%), onset none detected
- [OBSERVED EVIDENCE] `met-user-service-db_conn_util_pct-1930-2025` (weak): user-service db_conn_util_pct: baseline 30.04 -> window mean 30.17 (max 33.21, change 0.4%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Mobile client release or rollout record for mobile-ios-7.4.0 (deployments tool covers only user-service)
- [UNKNOWN] Per-client traffic breakdown at the ingress or CDN layer
- [UNKNOWN] Confirmation that the 1,700 rps client is a single set of devices, not a spoofed or misattributed identity

### 2. H2 - `deployment_regression` in `user-service` (confidence 0.15, critic: n/a)
**INFERENCE:** user-service 7.1.3 release (19:48Z) caused the platform-wide load or latency increase. Mechanism: A regression in the 7.1.3 release would drive upstream retries or CPU. It would need to precede the surge by about 7 minutes.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [CONFIRMED FACT] `dep-78c036fc` (moderate): Deployment of user-service 7.1.2->7.1.3 at 2026-10-02T19:48:00Z (SUCCEEDED): Copy changes on profile page
- [OBSERVED EVIDENCE] `logpat-user-service-742b555e` (weak): 1x WARN on user-service: 'Deprecated API /v1/users/legacy called by client web-66' (first 2026-10-02T19:47:55Z, last 2026-10-02T19:47:55Z)

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-user-service-error_rate-1930-2025` (strong): user-service error_rate: baseline 0.4 -> window mean 0.4 (max 0.43, change -0.5%), onset none detected
- [OBSERVED EVIDENCE] `met-user-service-p99_latency_ms-1930-2025` (strong): user-service p99_latency_ms: baseline 161.15 -> window mean 161.2 (max 173.38, change 0.0%), onset none detected
- [OBSERVED EVIDENCE] `met-user-service-request_rate-1930-2025` (moderate): user-service request_rate: baseline 500.78 -> window mean 1124.49 (max 1838.14, change 124.5%), onset 2026-10-02T19:55:00Z
- [OBSERVED EVIDENCE] `met-user-service-db_conn_util_pct-1930-2025` (moderate): user-service db_conn_util_pct: baseline 30.04 -> window mean 30.17 (max 33.21, change 0.4%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Deployment-level diff of 7.1.3 beyond the change summary
- [UNKNOWN] Per-endpoint latency for user-service after 19:48Z

### 3. H3 - `upstream_dependency_degradation` in `None` (confidence 0.05, critic: n/a)
**INFERENCE:** Upstream dependency (postgres, redis or similar) degradation caused the slowness. Mechanism: Degraded backing store would raise latency and timeouts across services.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- none

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-user-service-timeout_rate-1930-2025` (moderate): user-service timeout_rate: baseline 0.05 -> window mean 0.05 (max 0.06, change -0.3%), onset none detected
- [OBSERVED EVIDENCE] `met-user-service-db_conn_util_pct-1930-2025` (moderate): user-service db_conn_util_pct: baseline 30.04 -> window mean 30.17 (max 33.21, change 0.4%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Redis and postgres metrics were not queried

## Critic Review
- **Verdict:** `NOT_RUN` (rounds reviewed: 0)
- **Reasoning:** 

## Probable Root Cause
MOST PROBABLE EXPLANATION (INFERENCE, not confirmed): traffic_surge in None - Retry storm from mobile-ios-7.4.0 clients ignoring Retry-After, driving traffic surge and resource saturation across api-gateway, auth-service and user-service.

## Corrective Actions
- Enforce server-side rate limiting or blocking for mobile-ios-7.4.0 at the gateway, and cap retries for that client version
- Coordinate with mobile to hotfix or force-upgrade clients that ignore Retry-After
- Confirm the 7.1.3 user-service release is not implicated before closing

## Preventive Actions
- Require clients to honour Retry-After and implement exponential backoff with jitter, enforced in client SDK tests
- Add per-client-version quotas and alerts on retry ratio
- Add pre-release load testing for mobile API clients

## Monitoring Recommendations
- Alert on request_rate per client_id and on retry ratio above 100%
- Alert on gateway CPU above 70% sustained for 5 min
- Track 429 rate per client version
- Monitor p99 latency on the user-facing endpoints, since gateway p99 did not show the reported slowness

## Evidence Gaps
- none recorded

## Limitations
- Gateway and service p99 latency did not show the reported slowness, so the user-facing impact is not fully characterised
- No mobile release telemetry was available
- Redis and postgres were not queried
- Client-level attribution rests on the gateway's per-client logs
- [agent-reported gap] No mobile release or rollout record for mobile-ios-7.4.0
- [agent-reported gap] No per-client traffic breakdown beyond log summaries
- [agent-reported gap] No redis or postgres metrics
- [agent-reported gap] No user-facing latency (e.g. RUM) data
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: agent submitted

## Final Status
`PROBABLE_ROOT_CAUSE`

INC-011's 429s and CPU saturation are best explained by a traffic surge from a single mobile client version (mobile-ios-7.4.0) that retries aggressively and ignores Retry-After. Traffic to api-gateway, auth-service and user-service roughly doubled-to-tripled starting 19:55Z, about 5 minutes before T0. The user-service deploy at 19:48Z (7.1.2 to 7.1.3, copy changes) is a weaker candidate: it preceded the surge, but no user-service latency or error change followed it. The 'slowness' symptom is not clearly visible in p99 latency at any of the three services, so the user-facing slowness is not fully explained.

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
  "evidence_records": 46,
  "duration_s": 33.69,
  "tokens": {
    "input_tokens": 12,
    "output_tokens": 9130,
    "cache_read_tokens": 49641,
    "cache_write_tokens": 16371,
    "llm_calls": 5,
    "cost_usd": 0.007108985
  },
  "tokens_by_agent": {
    "single_agent": {
      "input_tokens": 12,
      "output_tokens": 9130,
      "cache_read_tokens": 49641,
      "cache_write_tokens": 16371,
      "llm_calls": 5,
      "cost_usd": 0.007108985
    }
  }
}
```
