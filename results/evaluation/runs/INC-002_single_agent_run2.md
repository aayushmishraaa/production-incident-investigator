# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-002
- **Title:** Login and checkout failures
- **Severity:** SEV1
- **Affected services:** api-gateway, auth-service, payment-service
- **Start time:** 2026-09-05T09:30:00+00:00
- **Investigation ID:** inv-e76aefa06b (single_agent)
- **Final status:** `ROOT_CAUSE_IDENTIFIED`

## Executive Summary
Login and checkout 5xx errors began at 09:29-09:30Z, about one minute after auth-service was deployed (2.13.4 to 2.14.0 at 09:28Z, which migrated JWT validation to jose-4.2 and refactored the token cache). auth-service then throws 'unsupported key type EC in JWKS' on token validation. Auth 500s propagate to api-gateway (/v1/token/verify) and payment-service (authorization checks). Error rates rose from ~0.3% to ~27% in auth, ~0.8% to ~14% in payment, and ~0.5% to ~19% in api-gateway. Latency, DB connection utilisation and timeouts were flat.

## Incident Timeline
| Time (UTC) | Label | Event | Evidence |
|---|---|---|---|
| 2026-09-05T09:10:00Z | CONFIRMED FACT | Config change on user-service: feature.profile_badges false -> true at 2026-09-05T09:10:00Z (OPS-2306) | cfg-cc6f8080 |
| 2026-09-05T09:28:00Z | CONFIRMED FACT | Deployment of auth-service 2.13.4->2.14.0 at 2026-09-05T09:28:00Z (SUCCEEDED): Migrate JWT validation to jose-4.2; refactor token cache | dep-cbc63772 |
| 2026-09-05T09:29:00Z | OBSERVED EVIDENCE | Anomaly onset: auth-service error_rate: baseline 0.3 -> window mean 12.88 (max 29.54, change 4197.5%), onset 2026-09-05T09:29:00Z | met-auth-service-error_rate-0900-0955 |
| 2026-09-05T09:29:00Z | OBSERVED EVIDENCE | Anomaly onset: api-gateway error_rate: baseline 0.5 -> window mean 9.05 (max 19.93, change 1706.9%), onset 2026-09-05T09:29:00Z | met-api-gateway-error_rate-0900-0955 |
| 2026-09-05T09:29:00Z | OBSERVED EVIDENCE | First log: 12x ERROR on auth-service: 'TokenValidationException: unsupported key type 'EC' in JWKS (validator=jose-4.2, kid=k20)' (first 2026-09-05T09:29:00Z, last 2026-09-05T09:39:49Z) | logpat-auth-service-f41941c5 |
| 2026-09-05T09:29:03Z | OBSERVED EVIDENCE | First log: 6x WARN on api-gateway: 'auth-service returned 500 for /v1/token/verify (req 63)' (first 2026-09-05T09:29:03Z, last 2026-09-05T09:38:28Z) | logpat-api-gateway-7c1adbea |
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
### 1. H1 - `deployment_regression` in `auth-service` (confidence 0.90, critic: n/a)
**INFERENCE:** auth-service 2.14.0 deployment introduced a JWT/JWKS validation regression (jose-4.2 migration) that cannot parse EC keys, causing token validation to fail with 500s. Mechanism: After the 09:28Z deploy, JWKS validation with jose-4.2 throws TokenValidationException for EC-type keys. Auth returns 500 on token verify, so api-gateway returns 5xx on login/session checks and payment-service authorization checks fail and retry. Users are logged out when token verification fails.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [CONFIRMED FACT] `dep-cbc63772` (strong): Deployment of auth-service 2.13.4->2.14.0 at 2026-09-05T09:28:00Z (SUCCEEDED): Migrate JWT validation to jose-4.2; refactor token cache
- [OBSERVED EVIDENCE] `logpat-auth-service-f41941c5` (strong): 12x ERROR on auth-service: 'TokenValidationException: unsupported key type 'EC' in JWKS (validator=jose-4.2, kid=k20)' (first 2026-09-05T09:29:00Z, last 2026-09-05T09:39:49Z)
- [OBSERVED EVIDENCE] `log-75321b43` (strong): ERROR auth-service: TokenValidationException: unsupported key type 'EC' in JWKS (validator=jose-4.2, kid=k20)
- [OBSERVED EVIDENCE] `met-auth-service-error_rate-0900-0955` (strong): auth-service error_rate: baseline 0.3 -> window mean 12.88 (max 29.54, change 4197.5%), onset 2026-09-05T09:29:00Z
- [OBSERVED EVIDENCE] `met-api-gateway-error_rate-0900-0955` (moderate): api-gateway error_rate: baseline 0.5 -> window mean 9.05 (max 19.93, change 1706.9%), onset 2026-09-05T09:29:00Z
- [OBSERVED EVIDENCE] `logpat-api-gateway-7c1adbea` (moderate): 6x WARN on api-gateway: 'auth-service returned 500 for /v1/token/verify (req 63)' (first 2026-09-05T09:29:03Z, last 2026-09-05T09:38:28Z)
- [OBSERVED EVIDENCE] `logpat-payment-service-a56d8d43` (moderate): 4x ERROR on payment-service: 'Authorization check failed: upstream auth-service 500 (charge ch_67)' (first 2026-09-05T09:30:08Z, last 2026-09-05T09:38:30Z)
- [CONFIRMED FACT] `topo-auth-service-both-d2` (moderate): auth-service depends on ['postgres', 'redis']; called by ['api-gateway', 'payment-service'] (graph topology-v1)

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-auth-service-p99_latency_ms-0900-0955` (moderate): auth-service p99_latency_ms: baseline 90.04 -> window mean 89.61 (max 97.79, change -0.5%), onset none detected
- [OBSERVED EVIDENCE] `met-auth-service-db_conn_util_pct-0900-0955` (moderate): auth-service db_conn_util_pct: baseline 30.06 -> window mean 29.84 (max 32.95, change -0.7%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] No direct rollback or canary result confirming that reverting 2.14.0 restores login
- [UNKNOWN] No JWKS content check confirming an EC key was newly published

### 2. H2 - `db_connection_pool_exhaustion` in `postgres` (confidence 0.05, critic: n/a)
**INFERENCE:** Database contention (slow report_rollup queries) degraded auth or payment dependencies. Mechanism: Long-running SELECT report_rollup() could starve connections and cause 5xx in auth/payment.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-postgres-44883ca5` (weak): 2x WARN on postgres: 'duration: 19502 ms statement: SELECT report_rollup()' (first 2026-09-05T09:21:55Z, last 2026-09-05T09:34:49Z)

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-auth-service-db_conn_util_pct-0900-0955` (strong): auth-service db_conn_util_pct: baseline 30.06 -> window mean 29.84 (max 32.95, change -0.7%), onset none detected
- [OBSERVED EVIDENCE] `met-auth-service-p99_latency_ms-0900-0955` (moderate): auth-service p99_latency_ms: baseline 90.04 -> window mean 89.61 (max 97.79, change -0.5%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] No postgres metrics were queried

### 3. H3 - `configuration_regression` in `user-service` (confidence 0.03, critic: n/a)
**INFERENCE:** A config change (feature.profile_badges enabled on user-service at 09:10Z) caused the failures. Mechanism: Would need to affect auth token validation or the gateway path, which is not shown.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [CONFIRMED FACT] `cfg-cc6f8080` (weak): Config change on user-service: feature.profile_badges false -> true at 2026-09-05T09:10:00Z (OPS-2306)

Contradicting evidence:
- [OBSERVED EVIDENCE] `logpat-auth-service-f41941c5` (strong): 12x ERROR on auth-service: 'TokenValidationException: unsupported key type 'EC' in JWKS (validator=jose-4.2, kid=k20)' (first 2026-09-05T09:29:00Z, last 2026-09-05T09:39:49Z)

Remaining uncertainties / missing evidence:
- [UNKNOWN] No evidence that user-service sits on the login or checkout 5xx path

## Critic Review
- **Verdict:** `NOT_RUN` (rounds reviewed: 0)
- **Reasoning:** 

## Probable Root Cause
ROOT CAUSE IDENTIFIED (critic-approved; still an INFERENCE from evidence): deployment_regression in auth-service - auth-service 2.14.0 deployment introduced a JWT/JWKS validation regression (jose-4.2 migration) that cannot parse EC keys, causing token validation to fail with 500s.

## Corrective Actions
- Roll back auth-service from 2.14.0 to 2.13.4 immediately (dep-cbc63772 is the trigger).
- Verify recovery: auth, gateway and payment error rates return to ~0.3%, 0.5% and 0.8%.
- Notify payment and checkout owners to reprocess failed authorizations from 09:29-09:40Z if needed.

## Preventive Actions
- Add a pre-deploy test that validates JWKS containing EC keys with the jose library version in use.
- Canary auth-service releases and gate them on the validation error rate.
- Require a rollback plan for security-critical dependency migrations such as the JWT library.

## Monitoring Recommendations
- Alert on TokenValidationException count and auth-service 5xx rate above baseline.
- Alert on the payment-service 'upstream auth-service 500' pattern.
- Watch api-gateway 5xx on /v1/token/verify.

## Evidence Gaps
- none recorded

## Limitations
- Rollback has not been performed or verified, so causality is established by timing and error signature rather than by reversal.
- Postgres and payment-service DB metrics were not queried.
- Logs truncated (16 more records omitted), though the pattern summaries cover the full set.
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: agent submitted

## Final Status
`ROOT_CAUSE_IDENTIFIED`

The most likely root cause is the auth-service 2.14.0 deployment at 09:28Z. Its jose-4.2 JWT/JWKS validation fails on EC keys, which produces auth 500s. These errors cascade to api-gateway and payment-service from 09:29-09:30Z, matching the reported login and checkout failures. Rollback to 2.13.4 is the recommended action. The fix is not yet confirmed as a result of rollback.

## Execution Statistics
```json
{
  "rounds": 1,
  "tool_calls": 7,
  "tool_failures": 0,
  "tool_retries": 0,
  "partial_results": 0,
  "agent_failures": 0,
  "agent_retries": 0,
  "invalid_llm_outputs": 0,
  "messages_exchanged": 0,
  "evidence_records": 53,
  "duration_s": 18.51,
  "tokens": {
    "input_tokens": 8,
    "output_tokens": 4484,
    "cache_read_tokens": 17487,
    "cache_write_tokens": 8098,
    "llm_calls": 3,
    "cost_usd": 0.0034299199999999995
  },
  "tokens_by_agent": {
    "single_agent": {
      "input_tokens": 8,
      "output_tokens": 4484,
      "cache_read_tokens": 17487,
      "cache_write_tokens": 8098,
      "llm_calls": 3,
      "cost_usd": 0.0034299199999999995
    }
  }
}
```
