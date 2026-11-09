# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-002
- **Title:** Login and checkout failures
- **Severity:** SEV1
- **Affected services:** api-gateway, auth-service, payment-service
- **Start time:** 2026-09-05T09:30:00+00:00
- **Investigation ID:** inv-a974df4b71 (single_agent)
- **Final status:** `PROBABLE_ROOT_CAUSE`

## Executive Summary
Login and checkout 5xx errors began at 09:29-09:30Z, roughly one minute after auth-service was deployed (2.13.4 to 2.14.0 at 09:28Z). Auth-service logs show repeated 'unsupported key type EC in JWKS' errors under the new jose-4.2 validator. Error rates rose on auth (~0.3% to ~27%), api-gateway (~0.5% to ~19%) and payment-service (~0.8% to ~14%), in the order the dependency graph predicts. Latency and DB saturation are unchanged, consistent with fast validation rejections. Most likely cause: the auth-service 2.14.0 JWT validation migration. Rollback is recommended; it has not yet been verified.

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
| 2026-09-05T09:36:00Z | CONFIRMED FACT | Incident reported |  |

## Observed Symptoms
- **OBSERVED EVIDENCE:** auth-service error_rate: baseline 0.3 -> window mean 12.88 (max 29.54, change 4197.5%), onset 2026-09-05T09:29:00Z (met-auth-service-error_rate-0900-0955)
- **OBSERVED EVIDENCE:** payment-service error_rate: baseline 0.8 -> window mean 6.69 (max 15.09, change 735.8%), onset 2026-09-05T09:30:00Z (met-payment-service-error_rate-0900-0955)
- **OBSERVED EVIDENCE:** api-gateway error_rate: baseline 0.5 -> window mean 9.05 (max 19.93, change 1706.9%), onset 2026-09-05T09:29:00Z (met-api-gateway-error_rate-0900-0955)

## Investigation Performed

## Root-Cause Hypotheses (ranked by evidence strength)
### 1. H1 - `deployment_regression` in `auth-service` (confidence 0.80, critic: n/a)
**INFERENCE:** auth-service 2.14.0 deployment (JWT validation migrated to jose-4.2) rejects EC keys in JWKS, causing token validation failures for login and downstream checkout. Mechanism: After deploy dep-cbc63772 at 09:28, auth-service raises TokenValidationException 'unsupported key type EC in JWKS (validator=jose-4.2)'. Token validation fails, auth returns 5xx, api-gateway (which validates/forwards auth) and payment-service (dependent on auth) surface 5xx; users are logged out when sessions cannot be validated.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [CONFIRMED FACT] `dep-cbc63772` (strong): Deployment of auth-service 2.13.4->2.14.0 at 2026-09-05T09:28:00Z (SUCCEEDED): Migrate JWT validation to jose-4.2; refactor token cache
- [OBSERVED EVIDENCE] `logpat-auth-service-f41941c5` (strong): 12x ERROR on auth-service: 'TokenValidationException: unsupported key type 'EC' in JWKS (validator=jose-4.2, kid=k20)' (first 2026-09-05T09:29:00Z, last 2026-09-05T09:39:49Z)
- [OBSERVED EVIDENCE] `log-75321b43` (strong): ERROR auth-service: TokenValidationException: unsupported key type 'EC' in JWKS (validator=jose-4.2, kid=k20)
- [OBSERVED EVIDENCE] `met-auth-service-error_rate-0900-0955` (strong): auth-service error_rate: baseline 0.3 -> window mean 12.88 (max 29.54, change 4197.5%), onset 2026-09-05T09:29:00Z
- [OBSERVED EVIDENCE] `met-api-gateway-error_rate-0900-0955` (strong): api-gateway error_rate: baseline 0.5 -> window mean 9.05 (max 19.93, change 1706.9%), onset 2026-09-05T09:29:00Z
- [OBSERVED EVIDENCE] `met-payment-service-error_rate-0900-0955` (moderate): payment-service error_rate: baseline 0.8 -> window mean 6.69 (max 15.09, change 735.8%), onset 2026-09-05T09:30:00Z
- [CONFIRMED FACT] `topo-auth-service-both-d2` (moderate): auth-service depends on ['postgres', 'redis']; called by ['api-gateway', 'payment-service'] (graph topology-v1)

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-auth-service-p99_latency_ms-0900-0955` (weak): auth-service p99_latency_ms: baseline 90.04 -> window mean 89.61 (max 97.79, change -0.5%), onset none detected
- [OBSERVED EVIDENCE] `logpat-auth-service-cc8d3b87` (weak): 1x WARN on auth-service: 'Login rate limit hit for user id u-73' (first 2026-09-05T09:35:49Z, last 2026-09-05T09:35:49Z)

Remaining uncertainties / missing evidence:
- [UNKNOWN] Direct payment-service logs showing auth-call errors (not queried)
- [UNKNOWN] Confirmation that JWKS actually publishes EC keys (no JWKS content checked)
- [UNKNOWN] Rollback test result

### 2. H2 - `configuration_regression` in `user-service` (confidence 0.05, critic: n/a)
**INFERENCE:** Config change feature.profile_badges false->true at 09:10 in user-service causes login/checkout failures. Mechanism: Would require user-service to be on the login/checkout request path causing 5xx; no evidence of this.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [CONFIRMED FACT] `cfg-cc6f8080` (weak): Config change on user-service: feature.profile_badges false -> true at 2026-09-05T09:10:00Z (OPS-2306)

Contradicting evidence:
- [OBSERVED EVIDENCE] `logpat-auth-service-f41941c5` (moderate): 12x ERROR on auth-service: 'TokenValidationException: unsupported key type 'EC' in JWKS (validator=jose-4.2, kid=k20)' (first 2026-09-05T09:29:00Z, last 2026-09-05T09:39:49Z)

Remaining uncertainties / missing evidence:
- [UNKNOWN] user-service metrics and logs not queried
- [UNKNOWN] No dependency path from user-service to auth/payment shown in topology

## Critic Review
- **Verdict:** `NOT_RUN` (rounds reviewed: 0)
- **Reasoning:** 

## Probable Root Cause
MOST PROBABLE EXPLANATION (INFERENCE, not confirmed): deployment_regression in auth-service - auth-service 2.14.0 deployment (JWT validation migrated to jose-4.2) rejects EC keys in JWKS, causing token validation failures for login and downstream checkout.

## Corrective Actions
- Roll back auth-service to 2.13.4 (dep-cbc63772 reverse) immediately and verify auth/gateway/payment error rates return to baseline
- Hold the jose-4.2 migration until EC key support in the JWKS validator is fixed and tested

## Preventive Actions
- Add a pre-production canary test that validates tokens signed with every key type published in JWKS
- Gate auth-service deploys on automated post-deploy error-rate checks with auto-rollback

## Monitoring Recommendations
- Alert on auth-service TokenValidationException count and error rate >2% for 5 minutes
- Track api-gateway and payment-service 5xx rate split by upstream auth dependency

## Evidence Gaps
- none recorded

## Limitations
- Historical incident search was not run
- Telemetry is limited to the investigation window and baseline; no post-rollback data exists yet
- [agent-reported gap] No logs queried for api-gateway or payment-service
- [agent-reported gap] No user-service metrics or logs queried despite a config change at 09:10Z
- [agent-reported gap] JWKS contents not verified
- [agent-reported gap] Log summary shows 12 auth ERRORs against a ~27% error rate; sampling or log loss may exist
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: agent submitted

## Final Status
`PROBABLE_ROOT_CAUSE`

The evidence points to the auth-service 2.14.0 deployment as the probable root cause. Its JWT validation fails on EC keys, and the failures spread to api-gateway and payment-service. Confidence is not yet ROOT_CAUSE_IDENTIFIED because the rollback has not been tested, the JWKS contents were not inspected, and downstream logs were not pulled.

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
  "evidence_records": 29,
  "duration_s": 16.56,
  "tokens": {
    "input_tokens": 8,
    "output_tokens": 3961,
    "cache_read_tokens": 13418,
    "cache_write_tokens": 11327,
    "llm_calls": 3,
    "cost_usd": 0.003531355
  },
  "tokens_by_agent": {
    "single_agent": {
      "input_tokens": 8,
      "output_tokens": 3961,
      "cache_read_tokens": 13418,
      "cache_write_tokens": 11327,
      "llm_calls": 3,
      "cost_usd": 0.003531355
    }
  }
}
```
