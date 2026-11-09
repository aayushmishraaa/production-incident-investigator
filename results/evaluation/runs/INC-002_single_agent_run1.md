# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-002
- **Title:** Login and checkout failures
- **Severity:** SEV1
- **Affected services:** api-gateway, auth-service, payment-service
- **Start time:** 2026-09-05T09:30:00+00:00
- **Investigation ID:** inv-f14baa7d5b (single_agent)
- **Final status:** `PROBABLE_ROOT_CAUSE`

## Executive Summary
Errors on login and checkout began at 09:29-09:30Z, about one minute after auth-service 2.14.0 deployed at 09:28Z. Auth-service logs show 'unsupported key type EC in JWKS' under jose-4.2 from 09:29Z onward. Payment-service auth checks then return upstream 500s. Error rates rose roughly 40x on auth-service, 9x on api-gateway and 7x on payment-service. Latency, DB connection and timeout metrics are flat, so this is a functional failure rather than resource saturation. Recommended action: roll back auth-service to 2.13.4 and verify recovery.

## Incident Timeline
| Time (UTC) | Label | Event | Evidence |
|---|---|---|---|
| 2026-09-05T09:10:00Z | CONFIRMED FACT | Config change on user-service: feature.profile_badges false -> true at 2026-09-05T09:10:00Z (OPS-2306) | cfg-cc6f8080 |
| 2026-09-05T09:28:00Z | CONFIRMED FACT | Deployment of auth-service 2.13.4->2.14.0 at 2026-09-05T09:28:00Z (SUCCEEDED): Migrate JWT validation to jose-4.2; refactor token cache | dep-cbc63772 |
| 2026-09-05T09:29:00Z | OBSERVED EVIDENCE | Anomaly onset: auth-service error_rate: baseline 0.3 -> window mean 12.88 (max 29.54, change 4197.5%), onset 2026-09-05T09:29:00Z | met-auth-service-error_rate-0900-0955 |
| 2026-09-05T09:29:00Z | OBSERVED EVIDENCE | Anomaly onset: api-gateway error_rate: baseline 0.5 -> window mean 9.05 (max 19.93, change 1706.9%), onset 2026-09-05T09:29:00Z | met-api-gateway-error_rate-0900-0955 |
| 2026-09-05T09:29:00Z | OBSERVED EVIDENCE | First log: 12x ERROR on auth-service: 'TokenValidationException: unsupported key type 'EC' in JWKS (validator=jose-4.2, kid=k20)' (first 2026-09-05T09:29:00Z, last 2026-09-05T09:39:49Z) | logpat-auth-service-f41941c5 |
| 2026-09-05T09:30:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service error_rate: baseline 0.8 -> window mean 6.69 (max 15.09, change 735.8%), onset 2026-09-05T09:30:00Z | met-payment-service-error_rate-0900-0955 |
| 2026-09-05T09:30:00Z | CONFIRMED FACT | Reported symptom start |  |
| 2026-09-05T09:30:08Z | OBSERVED EVIDENCE | First log: 4x ERROR on payment-service: 'Authorization check failed: upstream auth-service 500 (charge ch_67)' (first 2026-09-05T09:30:08Z, last 2026-09-05T09:38:30Z) | logpat-payment-service-a56d8d43 |
| 2026-09-05T09:30:08Z | OBSERVED EVIDENCE | First log: 3x WARN on payment-service: 'Retrying request to auth-service (attempt 2/3)' (first 2026-09-05T09:30:08Z, last 2026-09-05T09:37:28Z) | logpat-payment-service-8d3ec00b |
| 2026-09-05T09:36:00Z | CONFIRMED FACT | Incident reported |  |

## Observed Symptoms
- **OBSERVED EVIDENCE:** auth-service error_rate: baseline 0.3 -> window mean 12.88 (max 29.54, change 4197.5%), onset 2026-09-05T09:29:00Z (met-auth-service-error_rate-0900-0955)
- **OBSERVED EVIDENCE:** payment-service error_rate: baseline 0.8 -> window mean 6.69 (max 15.09, change 735.8%), onset 2026-09-05T09:30:00Z (met-payment-service-error_rate-0900-0955)
- **OBSERVED EVIDENCE:** api-gateway error_rate: baseline 0.5 -> window mean 9.05 (max 19.93, change 1706.9%), onset 2026-09-05T09:29:00Z (met-api-gateway-error_rate-0900-0955)

## Investigation Performed

## Root-Cause Hypotheses (ranked by evidence strength)
### 1. H1 - `deployment_regression` in `auth-service` (confidence 0.85, critic: n/a)
**INFERENCE:** auth-service 2.14.0 JWT/JWKS validation change (jose-4.2) cannot handle EC keys, causing token validation exceptions and 5xx responses. Mechanism: After deploy at 09:28Z, auth-service validates tokens with jose-4.2, which throws 'unsupported key type EC' for JWKS key kids. Login and token checks return 5xx. payment-service's authorization call to auth-service receives 500 and fails after retries. api-gateway propagates the 5xx to clients, who are logged out.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [CONFIRMED FACT] `dep-cbc63772` (strong): Deployment of auth-service 2.13.4->2.14.0 at 2026-09-05T09:28:00Z (SUCCEEDED): Migrate JWT validation to jose-4.2; refactor token cache
- [OBSERVED EVIDENCE] `logpat-auth-service-f41941c5` (strong): 12x ERROR on auth-service: 'TokenValidationException: unsupported key type 'EC' in JWKS (validator=jose-4.2, kid=k20)' (first 2026-09-05T09:29:00Z, last 2026-09-05T09:39:49Z)
- [OBSERVED EVIDENCE] `met-auth-service-error_rate-0900-0955` (strong): auth-service error_rate: baseline 0.3 -> window mean 12.88 (max 29.54, change 4197.5%), onset 2026-09-05T09:29:00Z
- [OBSERVED EVIDENCE] `met-api-gateway-error_rate-0900-0955` (moderate): api-gateway error_rate: baseline 0.5 -> window mean 9.05 (max 19.93, change 1706.9%), onset 2026-09-05T09:29:00Z
- [OBSERVED EVIDENCE] `logpat-payment-service-a56d8d43` (moderate): 4x ERROR on payment-service: 'Authorization check failed: upstream auth-service 500 (charge ch_67)' (first 2026-09-05T09:30:08Z, last 2026-09-05T09:38:30Z)
- [INFERENCE] `hist-HIST-2025-022` (weak): Past incident HIST-2025-022 'Auth outage after JWT library upgrade' (similarity 0.367): New release mis-parsed JWKS keys.

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-auth-service-p99_latency_ms-0900-0955` (weak): auth-service p99_latency_ms: baseline 90.04 -> window mean 89.61 (max 97.79, change -0.5%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Diff of 2.14.0 confirming EC key handling or jose version
- [UNKNOWN] Logs or metrics from before 09:28 showing EC keys present in JWKS
- [UNKNOWN] Confirmation that the error count matches the 5xx count, since the log pattern shows only 12 events

### 2. H2 - `upstream_dependency_degradation` in `postgres` (confidence 0.08, critic: n/a)
**INFERENCE:** A shared dependency (postgres or redis via auth-service) degraded and caused auth 500s. Mechanism: If auth-service depends on a degraded DB or cache, token validation would fail with 5xx.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- none

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-auth-service-db_conn_util_pct-0900-0955` (strong): auth-service db_conn_util_pct: baseline 30.06 -> window mean 29.84 (max 32.95, change -0.7%), onset none detected
- [CONFIRMED FACT] `topo-payment-service-upstream-d2` (moderate): payment-service depends on ['auth-service', 'postgres', 'redis']; called by ? (graph topology-v1)

Remaining uncertainties / missing evidence:
- [UNKNOWN] postgres and redis metrics and logs were not queried

### 3. H3 - `configuration_regression` in `user-service` (confidence 0.03, critic: n/a)
**INFERENCE:** A config flag change at 09:10Z (feature.profile_badges) caused the failures. Mechanism: A user-service feature flag could affect login flows, but the timing and error signature do not match.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [CONFIRMED FACT] `cfg-cc6f8080` (weak): Config change on user-service: feature.profile_badges false -> true at 2026-09-05T09:10:00Z (OPS-2306)

Contradicting evidence:
- [OBSERVED EVIDENCE] `logpat-auth-service-f41941c5` (strong): 12x ERROR on auth-service: 'TokenValidationException: unsupported key type 'EC' in JWKS (validator=jose-4.2, kid=k20)' (first 2026-09-05T09:29:00Z, last 2026-09-05T09:39:49Z)

Remaining uncertainties / missing evidence:
- [UNKNOWN] No user-service error logs were queried

## Critic Review
- **Verdict:** `NOT_RUN` (rounds reviewed: 0)
- **Reasoning:** 

## Probable Root Cause
MOST PROBABLE EXPLANATION (INFERENCE, not confirmed): deployment_regression in auth-service - auth-service 2.14.0 JWT/JWKS validation change (jose-4.2) cannot handle EC keys, causing token validation exceptions and 5xx responses.

## Corrective Actions
- Roll back auth-service from 2.14.0 to 2.13.4 now, then confirm error rates return to baseline on auth, gateway and payment.
- Re-run any pending payment retries or checkout flows once rollback is verified.

## Preventive Actions
- Add contract tests for JWKS key types (EC, RSA, OKP) to the auth-service CI pipeline before release.
- Require canary rollout for auth-service changes that touch token validation.

## Monitoring Recommendations
- Alert on auth-service TokenValidationException count and on 5xx rate above 1% for 2 minutes.
- Track payment-service auth retry rate and upstream 500s from auth-service.

## Evidence Gaps
- none recorded

## Limitations
- Telemetry was checked only for auth, payment and api-gateway. Postgres, redis and user-service were not checked.
- Historical match is an analogy only.
- [agent-reported gap] Errors are about 12 log events against roughly 27% error rate, so log sampling may be incomplete.
- [agent-reported gap] No logs or metrics were queried for postgres, redis, or user-service.
- [agent-reported gap] No direct diff of the 2.14.0 build was available.
- [agent-reported gap] No evidence yet that the EC keys were present before the deploy.
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: agent submitted

## Final Status
`PROBABLE_ROOT_CAUSE`

The INC-002 login and checkout 5xx spike is most likely caused by auth-service release 2.14.0 (deployed 09:28Z, migrating JWT validation to jose-4.2). From 09:29Z the new build rejects EC keys in the JWKS with 'unsupported key type EC', producing 5xx on auth paths. payment-service authorization calls to auth-service then fail with 500 and are retried, and api-gateway errors rise in step. Strongest candidate: rollback of auth-service to 2.13.4. Not yet confirmed by a rollback or a controlled test.

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
  "invalid_llm_outputs": 1,
  "messages_exchanged": 0,
  "evidence_records": 40,
  "duration_s": 25.79,
  "tokens": {
    "input_tokens": 12,
    "output_tokens": 6843,
    "cache_read_tokens": 39251,
    "cache_write_tokens": 15868,
    "llm_calls": 5,
    "cost_usd": 0.00579871
  },
  "tokens_by_agent": {
    "single_agent": {
      "input_tokens": 12,
      "output_tokens": 6843,
      "cache_read_tokens": 39251,
      "cache_write_tokens": 15868,
      "llm_calls": 5,
      "cost_usd": 0.00579871
    }
  }
}
```
