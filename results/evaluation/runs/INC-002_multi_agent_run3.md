# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-002
- **Title:** Login and checkout failures
- **Severity:** SEV1
- **Affected services:** api-gateway, auth-service, payment-service
- **Start time:** 2026-09-05T09:30:00+00:00
- **Investigation ID:** inv-5e2f2d30ab (multi_agent)
- **Final status:** `ROOT_CAUSE_IDENTIFIED`

## Executive Summary
INC-002 (SEV1, login and checkout failures) began at 09:30Z on 2026-09-05. The investigation status is ROOT_CAUSE_IDENTIFIED, with the most probable cause being the auth-service 2.14.0 deployment (build 4410), which ran from 09:28:00Z (dep-cbc63772). The deploy migrated JWT validation to jose-4.2 and refactored the token cache. From 09:29:00Z, auth-service logged 'TokenValidationException: unsupported key type EC in JWKS (validator=jose-4.2, kid=k20)' (logpat-auth-service-f41941c5). Its error rate rose from a 0.3% baseline to a window mean of about 12.9%, peaking near 29.5% (met-auth-service-error_rate-0900-0955). Latency, timeouts and request rate stayed flat, which points to a deterministic validation failure rather than load. The failure propagated to api-gateway, where /v1/token/verify returned 500s from 09:29:03Z (logpat-api-gateway-7c1adbea), and to payment-service, where authorization checks failed from 09:30:08Z (logpat-payment-service-a56d8d43). Users whose token verification failed were logged out, and login and checkout requests returned 5xx. Alternative explanations were examined and rejected: a JWKS key-set change (H2), database saturation from report_rollup (H3), and a user-service feature flag (H4). The root cause is the most probable explanation, not a confirmed fact, with confidence 0.85.

## Incident Timeline
| Time (UTC) | Label | Event | Evidence |
|---|---|---|---|
| 2026-09-05T09:00:11Z | OBSERVED EVIDENCE | First log: 4x WARN on payment-service: 'Card network soft decline (code 05) for charge ch_74' (first 2026-09-05T09:00:11Z, last 2026-09-05T09:25:49Z) | logpat-payment-service-7e9bf84f |
| 2026-09-05T09:01:05Z | OBSERVED EVIDENCE | First log: 5x WARN on api-gateway: 'Slow client upload from 10.4.90.12 (1.9MB)' (first 2026-09-05T09:01:05Z, last 2026-09-05T09:44:38Z) | logpat-api-gateway-88b04940 |
| 2026-09-05T09:02:03Z | OBSERVED EVIDENCE | First log: 8x WARN on postgres: 'duration: 14602 ms statement: SELECT report_rollup()' (first 2026-09-05T09:02:03Z, last 2026-09-05T09:54:06Z) | logpat-postgres-44883ca5 |
| 2026-09-05T09:10:00Z | CONFIRMED FACT | Config change on user-service: feature.profile_badges false -> true at 2026-09-05T09:10:00Z (OPS-2306) | cfg-cc6f8080 |
| 2026-09-05T09:19:21Z | OBSERVED EVIDENCE | First log: 4x WARN on auth-service: 'Login rate limit hit for user id u-32' (first 2026-09-05T09:19:21Z, last 2026-09-05T09:45:33Z) | logpat-auth-service-cc8d3b87 |
| 2026-09-05T09:25:15Z | OBSERVED EVIDENCE | First log: 4x WARN on order-service: 'Inventory reservation retry for sku-98' (first 2026-09-05T09:25:15Z, last 2026-09-05T09:48:05Z) | logpat-order-service-95abd1bb |
| 2026-09-05T09:28:00Z | CONFIRMED FACT | Deployment of auth-service 2.13.4->2.14.0 at 2026-09-05T09:28:00Z (SUCCEEDED): Migrate JWT validation to jose-4.2; refactor token cache | dep-cbc63772 |
| 2026-09-05T09:29:00Z | OBSERVED EVIDENCE | Anomaly onset: api-gateway error_rate: baseline 0.5 -> window mean 9.05 (max 19.93, change 1706.9%), onset 2026-09-05T09:29:00Z | met-api-gateway-error_rate-0900-0955 |
| 2026-09-05T09:29:00Z | OBSERVED EVIDENCE | Anomaly onset: auth-service error_rate: baseline 0.3 -> window mean 12.88 (max 29.54, change 4197.5%), onset 2026-09-05T09:29:00Z | met-auth-service-error_rate-0900-0955 |
| 2026-09-05T09:29:00Z | OBSERVED EVIDENCE | First log: 27x ERROR on auth-service: 'TokenValidationException: unsupported key type 'EC' in JWKS (validator=jose-4.2, kid=k20)' (first 2026-09-05T09:29:00Z, last 2026-09-05T09:54:18Z) | logpat-auth-service-f41941c5 |
| 2026-09-05T09:29:03Z | OBSERVED EVIDENCE | First log: 14x WARN on api-gateway: 'auth-service returned 500 for /v1/token/verify (req 63)' (first 2026-09-05T09:29:03Z, last 2026-09-05T09:53:26Z) | logpat-api-gateway-7c1adbea |
| 2026-09-05T09:30:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service error_rate: baseline 0.8 -> window mean 6.69 (max 15.09, change 735.8%), onset 2026-09-05T09:30:00Z | met-payment-service-error_rate-0900-0955 |
| 2026-09-05T09:30:00Z | CONFIRMED FACT | Reported symptom start |  |
| 2026-09-05T09:30:08Z | OBSERVED EVIDENCE | First log: 9x ERROR on payment-service: 'Authorization check failed: upstream auth-service 500 (charge ch_67)' (first 2026-09-05T09:30:08Z, last 2026-09-05T09:52:21Z) | logpat-payment-service-a56d8d43 |
| 2026-09-05T09:30:08Z | OBSERVED EVIDENCE | First log: 7x WARN on payment-service: 'Retrying request to auth-service (attempt 2/3)' (first 2026-09-05T09:30:08Z, last 2026-09-05T09:51:40Z) | logpat-payment-service-8d3ec00b |
| 2026-09-05T09:32:18Z | OBSERVED EVIDENCE | First log: 5x WARN on user-service: 'Deprecated API /v1/users/legacy called by client web-19' (first 2026-09-05T09:32:18Z, last 2026-09-05T09:54:15Z) | logpat-user-service-742b555e |
| 2026-09-05T09:36:00Z | CONFIRMED FACT | Incident reported |  |

## Observed Symptoms
- **OBSERVED EVIDENCE:** api-gateway error_rate: baseline 0.5 -> window mean 9.05 (max 19.93, change 1706.9%), onset 2026-09-05T09:29:00Z (met-api-gateway-error_rate-0900-0955)
- **OBSERVED EVIDENCE:** auth-service error_rate: baseline 0.3 -> window mean 12.88 (max 29.54, change 4197.5%), onset 2026-09-05T09:29:00Z (met-auth-service-error_rate-0900-0955)
- **OBSERVED EVIDENCE:** payment-service error_rate: baseline 0.8 -> window mean 6.69 (max 15.09, change 735.8%), onset 2026-09-05T09:30:00Z (met-payment-service-error_rate-0900-0955)
- **OBSERVED EVIDENCE:** [dependency] auth-service deployed 2.13.4 -> 2.14.0 (SUCCEEDED, ci-pipeline): 'Migrate JWT validation to jose-4.2; refactor token cache'. Deployed 2 minutes before T0. (dep-cbc63772)
- **OBSERVED EVIDENCE:** [dependency] auth-service error_rate onset at 09:29Z: baseline mean 0.30% -> window mean 12.88% (max 29.54%). Sampled series is flat ~0.3% through 09:25 and jumps to ~27% at 09:30, persisting through 09:55. (met-auth-service-error_rate-0900-0955)
- **OBSERVED EVIDENCE:** [dependency] auth-service p99 latency (~90ms) and timeout_rate (~0.05%) were unchanged over 09:00-09:55 versus baseline; errors are not accompanied by latency or timeout increase. (met-auth-service-p99_latency_ms-0900-0955, met-auth-service-timeout_rate-0900-0955)
- **OBSERVED EVIDENCE:** [dependency] Config change feature.profile_badges false -> true on user-service at 09:10Z (author config-bot, ticket OPS-2306). user-service is not in the api-gateway/auth-service/payment-service dependency chain reported here; no metrics checked for it. (cfg-cc6f8080)
- **OBSERVED EVIDENCE:** [dependency] Dependency graph: auth-service upstream = postgres, redis; downstream dependents = api-gateway, payment-service; potentially impacted = api-gateway, order-service, payment-service. No topology changes recorded. (topo-auth-service-both-d2)
- **INFERENCE:** [dependency] api-gateway and payment-service 5xx and user logouts may be downstream effects of auth-service token validation failures (both are direct dependents). Not yet verified with their metrics. (topo-auth-service-both-d2)
- **OBSERVED EVIDENCE:** [observability] DB connection utilisation flat: window mean 40.38% vs baseline 39.93% (+1.1%), max 44.23%, no onset detected. Sampled values around 09:30 are 39.27%, no saturation. (met-postgres-db_conn_util_pct-0900-0955)
- **OBSERVED EVIDENCE:** [observability] Postgres CPU (35.17% vs 35.17%), memory (65.23% vs 64.85%), p95 latency (12.01ms vs 12.05ms) and disk IO wait (2.0ms vs 1.99ms) all unchanged across the window; no onset detected. (met-postgres-cpu_pct-0900-0955, met-postgres-memory_pct-0900-0955, met-postgres-p95_latency_ms-0900-0955, met-postgres-disk_io_wait_ms-0900-0955)
- **OBSERVED EVIDENCE:** [observability] Postgres WARN logs show slow statement 'SELECT report_rollup()' (e.g. 14602 ms), 8 occurrences from 09:02:03Z to 09:54:06Z. These predate T0 and are not reflected in the p95 latency metric. (logpat-postgres-44883ca5)
- **OBSERVED EVIDENCE:** [observability] Redis shows no degradation: memory 59.91% vs 59.58% baseline, cache hit rate 94.87% vs 95.03%, p95 latency 1.51ms vs 1.49ms, CPU 15.08% vs 15.19%, error rate ~0.01% unchanged. No evictions metric was available in the tool output. (met-redis-memory_pct-0900-0955, met-redis-cache_hit_rate-0900-0955, met-redis-p95_latency_ms-0900-0955, met-redis-cpu_pct-0900-0955, met-redis-error_rate-0900-0955)
- **OBSERVED EVIDENCE:** [observability] user-service healthy by metrics: error rate 0.40% vs 0.41% baseline, p95 80.7ms vs 80.3ms, CPU 30.1% vs 29.8%, DB conn 30.1% vs 30.0%, timeout rate 0.05% vs 0.05%. No onset. (met-user-service-error_rate-0900-0955, met-user-service-p95_latency_ms-0900-0955, met-user-service-cpu_pct-0900-0955, met-user-service-db_conn_util_pct-0900-0955, met-user-service-timeout_rate-0900-0955)
- **OBSERVED EVIDENCE:** [observability] order-service shows no meaningful change: error rate 0.60% vs 0.60%, p95 200.5ms vs 198.4ms (+1.1%), timeout rate 0.10% vs 0.10%, CPU 45.6% vs 45.1%, DB conn 30.0% vs 30.2%. Only WARN is inventory reservation retry (4 occurrences, 09:25:15Z to 09:48:05Z), at low volume. (met-order-service-error_rate-0900-0955, met-order-service-p95_latency_ms-0900-0955, met-order-service-timeout_rate-0900-0955, met-order-service-cpu_pct-0900-0955, met-order-service-db_conn_util_pct-0900-0955, logpat-order-service-95abd1bb)
- **OBSERVED EVIDENCE:** [observability] Earliest ERROR in the window: auth-service TokenValidationException 'unsupported key type EC in JWKS' (jose-4.2), first at 09:29:00Z, 27 occurrences through 09:54:18Z, across varying kids. (logpat-auth-service-f41941c5, log-75321b43)
- **OBSERVED EVIDENCE:** [observability] payment-service 'Authorization check failed: upstream auth-service 500' errors begin at 09:30:08Z (9 occurrences) with 7 retries to auth-service; api-gateway logs auth-service 500 on /v1/token/verify starting 09:29:03Z (14 WARNs). (logpat-payment-service-a56d8d43, logpat-payment-service-8d3ec00b, logpat-api-gateway-7c1adbea)
- **OBSERVED EVIDENCE:** [observability] auth-service error_rate rose from baseline mean 0.3% to window mean 12.88% (max 29.54%), onset 09:29:00. Step change at 09:30 sample (27.69%), sustained at ~25-28% through 09:55. Request rate and CPU unchanged (req 903.9 -> 896.8/s; CPU 30.1% -> 30.0%). (met-auth-service-error_rate-0900-0955, met-auth-service-request_rate-0900-0955, met-auth-service-cpu_pct-0900-0955)
- **OBSERVED EVIDENCE:** [observability] First auth-service ERROR is TokenValidationException 'unsupported key type EC in JWKS' (jose-4.2, kid=k20) at 09:29:00; 27 occurrences through 09:54:18, with varying kids (k24, k67, k41, k45, k56, k33, k32, k53). Latency p99 and timeout_rate on auth-service stayed flat (p99 ~90ms, timeout ~0.05%). (logpat-auth-service-f41941c5, log-75321b43, log-6201a078, log-90d59037)
- **OBSERVED EVIDENCE:** [observability] api-gateway error_rate rose from baseline 0.5% to window mean 9.05% (max 19.93%), onset 09:29:00; first sample at 09:30 is 13.9% and ~18-19% thereafter. p99 latency (~249ms) and timeout_rate (~0.1%) unchanged; request rate unchanged (~1195/s vs 1201/s baseline). (met-api-gateway-error_rate-0900-0955, met-api-gateway-p99_latency_ms-0900-0955, met-api-gateway-timeout_rate-0900-0955, met-api-gateway-request_rate-0900-0955)
- **OBSERVED EVIDENCE:** [observability] api-gateway WARN: 'auth-service returned 500 for /v1/token/verify' (14 occurrences, 09:29:03 to 09:53:26), i.e. gateway token verification calls to auth-service fail with 500. (logpat-api-gateway-7c1adbea)
- **OBSERVED EVIDENCE:** [observability] payment-service error_rate rose from baseline 0.8% to window mean 6.69% (max 15.09%), onset 09:30:00 (5.4% at 09:30, ~14% from 09:35 onward). p99 latency (~301ms), timeout_rate (~0.1%), CPU (~40%) and request rate (~302/s vs 296/s) show no meaningful change. (met-payment-service-error_rate-0900-0955, met-payment-service-p99_latency_ms-0900-0955, met-payment-service-timeout_rate-0900-0955, met-payment-service-cpu_pct-0900-0955)
- **OBSERVED EVIDENCE:** [observability] payment-service ERROR 'Authorization check failed: upstream auth-service 500' first at 09:30:08 (9 occurrences to 09:52:21); accompanied by 7 WARN 'Retrying request to auth-service (attempt n/3)' from 09:30:08 to 09:51:40. (logpat-payment-service-a56d8d43, logpat-payment-service-8d3ec00b, log-cd9169e1)
- **OBSERVED EVIDENCE:** [observability] Postgres WARN slow statements 'SELECT report_rollup()' (e.g. 14602 ms), 8 occurrences from 09:02:03 to 09:54:06. Not on the login/checkout error path by itself; no metrics queried for postgres in this round. (logpat-postgres-44883ca5)
- **ASSUMPTION:** [critic: unsupported assumption] That 2.13.4 validated the same EC kid successfully (not yet directly tested; rollback would confirm). 
- **ASSUMPTION:** [critic: unsupported assumption] That the 5-minute metric granularity does not hide a slightly earlier onset; the 09:29:00Z log timestamp is more precise. 

## Investigation Performed
- Round 1 | observability | completed | attempts 1 | 4 tool calls | Characterize 5xx error rate, latency and traffic on api-gateway, auth-service and payment-service from 09:00Z to now; identify first error timestamp and error t
- Round 1 | observability | completed | attempts 1 | 5 tool calls | Check shared data stores and downstream services for saturation or errors starting near 09:30Z (connections, CPU, memory, latency, evictions).
- Round 1 | dependency | completed | attempts 1 | 4 tool calls | Identify deployments, configuration changes, or feature flag/secret/TTL changes to api-gateway, auth-service, payment-service and shared stores in the window 08
- Round 1 | reasoning | completed | attempts 1 | 0 tool calls | Develop and rank competing hypotheses
- Round 1 | critic | completed | attempts 1 | 3 tool calls | Independently review hypotheses
- Round 1 | reporting | completed | attempts 1 | 0 tool calls | Write final report

## Root-Cause Hypotheses (ranked by evidence strength)
### 1. H1 - `deployment_regression` in `auth-service` (confidence 0.85, critic: accept)
**INFERENCE:** auth-service 2.14.0 deploy (jose-4.2 JWT/JWKS validation and token-cache refactor) broke validation of EC keys, so auth-service rejects valid tokens and returns 500s, which propagate to api-gateway and payment-service. Mechanism: auth-service 2.13.4->2.14.0 deployed at 09:28Z; the new jose-4.2 validator throws 'unsupported key type EC in JWKS' on tokens/keys with EC kids, starting 09:29:00Z. auth-service 5xx rises 0.3% -> ~27%, with no latency, timeout or traffic change (consistent with a deterministic validation failure, not load). api-gateway /v1/token/verify calls to auth-service fail with 500 from 09:29:03Z; payment-service auth checks fail from 09:30:08Z after retries. Users who fail token verification are logged out and login/checkout requests return 5xx.

Confidence breakdown: base 0.10; +0.08 corroboration across >=2 independent source types; +0.78 supporting evidence (10 refs, reliability-weighted, capped); -0.10 contradicting evidence (2 refs, capped 0.45); +0.08 proposed cause (09:28) precedes/coincides with first observed anomaly (09:29); -0.06 3 acknowledged evidence gaps; +0.05 critic review adjustment; = 0.85 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [CONFIRMED FACT] `dep-cbc63772` (strong): Deployment of auth-service 2.13.4->2.14.0 at 2026-09-05T09:28:00Z (SUCCEEDED): Migrate JWT validation to jose-4.2; refactor token cache
- [OBSERVED EVIDENCE] `logpat-auth-service-f41941c5` (strong): 27x ERROR on auth-service: 'TokenValidationException: unsupported key type 'EC' in JWKS (validator=jose-4.2, kid=k20)' (first 2026-09-05T09:29:00Z, last 2026-09-05T09:54:18Z)
- [OBSERVED EVIDENCE] `met-auth-service-error_rate-0900-0955` (strong): auth-service error_rate: baseline 0.3 -> window mean 12.88 (max 29.54, change 4197.5%), onset 2026-09-05T09:29:00Z
- [OBSERVED EVIDENCE] `met-auth-service-p99_latency_ms-0900-0955` (moderate): auth-service p99_latency_ms: baseline 90.04 -> window mean 89.61 (max 97.79, change -0.5%), onset none detected
- [OBSERVED EVIDENCE] `met-auth-service-request_rate-0900-0955` (moderate): auth-service request_rate: baseline 903.91 -> window mean 896.76 (max 967.13, change -0.8%), onset none detected
- [OBSERVED EVIDENCE] `logpat-api-gateway-7c1adbea` (strong): 14x WARN on api-gateway: 'auth-service returned 500 for /v1/token/verify (req 63)' (first 2026-09-05T09:29:03Z, last 2026-09-05T09:53:26Z)
- [OBSERVED EVIDENCE] `met-api-gateway-error_rate-0900-0955` (moderate): api-gateway error_rate: baseline 0.5 -> window mean 9.05 (max 19.93, change 1706.9%), onset 2026-09-05T09:29:00Z
- [OBSERVED EVIDENCE] `logpat-payment-service-a56d8d43` (moderate): 9x ERROR on payment-service: 'Authorization check failed: upstream auth-service 500 (charge ch_67)' (first 2026-09-05T09:30:08Z, last 2026-09-05T09:52:21Z)
- [OBSERVED EVIDENCE] `met-payment-service-error_rate-0900-0955` (moderate): payment-service error_rate: baseline 0.8 -> window mean 6.69 (max 15.09, change 735.8%), onset 2026-09-05T09:30:00Z
- [CONFIRMED FACT] `topo-auth-service-both-d2` (moderate): auth-service depends on ['postgres', 'redis']; called by ['api-gateway', 'payment-service'] (graph topology-v1)

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-auth-service-error_rate-0900-0955` (weak): auth-service error_rate: baseline 0.3 -> window mean 12.88 (max 29.54, change 4197.5%), onset 2026-09-05T09:29:00Z
- [OBSERVED EVIDENCE] `logpat-auth-service-f41941c5` (weak): 27x ERROR on auth-service: 'TokenValidationException: unsupported key type 'EC' in JWKS (validator=jose-4.2, kid=k20)' (first 2026-09-05T09:29:00Z, last 2026-09-05T09:54:18Z)

Remaining uncertainties / missing evidence:
- [UNKNOWN] Confirmation that the EC key/kid existed in JWKS before 09:28 and that 2.13.4 validated it (e.g. rollback or canary comparison)
- [UNKNOWN] Per-endpoint split confirming login/checkout 5xx and logout linkage
- [UNKNOWN] Direct confirmation of api-gateway and payment-service route-level error breakdown

### 2. H2 - `configuration_regression` in `auth-service` (confidence 0.11, critic: reject)
**INFERENCE:** A JWKS / signing-key change (new EC key published or key rotation) at ~09:29 made auth-service encounter EC keys it cannot handle; the deploy is coincident rather than causal. Mechanism: An upstream key publication or rotation introduces EC-type keys into the JWKS served to auth-service. auth-service's validator rejects them as 'unsupported key type EC', producing 500s on token verification, which propagate to gateway and payment as in H1. The 2.14.0 deploy would then only be a temporal coincidence, or a contributing factor if the old version handled EC keys differently.

Confidence breakdown: base 0.10; +0.08 corroboration across >=2 independent source types; +0.54 supporting evidence (3 refs, reliability-weighted, capped); -0.15 contradicting evidence (1 refs, capped 0.45); +0.08 proposed cause (09:28) precedes/coincides with first observed anomaly (09:29); -0.06 3 acknowledged evidence gaps; -0.40 critic review adjustment; = 0.11 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-auth-service-f41941c5` (strong): 27x ERROR on auth-service: 'TokenValidationException: unsupported key type 'EC' in JWKS (validator=jose-4.2, kid=k20)' (first 2026-09-05T09:29:00Z, last 2026-09-05T09:54:18Z)
- [OBSERVED EVIDENCE] `met-auth-service-error_rate-0900-0955` (moderate): auth-service error_rate: baseline 0.3 -> window mean 12.88 (max 29.54, change 4197.5%), onset 2026-09-05T09:29:00Z
- [OBSERVED EVIDENCE] `logpat-api-gateway-7c1adbea` (moderate): 14x WARN on api-gateway: 'auth-service returned 500 for /v1/token/verify (req 63)' (first 2026-09-05T09:29:03Z, last 2026-09-05T09:53:26Z)

Contradicting evidence:
- [CONFIRMED FACT] `dep-cbc63772` (moderate): Deployment of auth-service 2.13.4->2.14.0 at 2026-09-05T09:28:00Z (SUCCEEDED): Migrate JWT validation to jose-4.2; refactor token cache

Remaining uncertainties / missing evidence:
- [UNKNOWN] Key rotation / JWKS change events between 08:00 and 09:29
- [UNKNOWN] Kid history showing when EC kids first appeared in JWKS
- [UNKNOWN] Whether 2.13.4 accepted the same EC keys

### 3. H3 - `resource_saturation` in `postgres` (confidence 0.00, critic: reject)
**INFERENCE:** Slow report_rollup() queries on postgres degrade shared resources and cause auth/checkout failures. Mechanism: Long-running SELECT report_rollup() statements (up to 14.6s from 09:02Z) hold connections or locks, causing auth-service DB calls to time out and fail.

Confidence breakdown: base 0.10; +0.12 supporting evidence (1 refs, reliability-weighted, capped); -0.45 contradicting evidence (4 refs, capped 0.45); +0.08 proposed cause (09:02) precedes/coincides with first observed anomaly (09:29); -0.04 2 acknowledged evidence gaps; -0.40 critic review adjustment; = 0.00 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-postgres-44883ca5` (moderate): 8x WARN on postgres: 'duration: 14602 ms statement: SELECT report_rollup()' (first 2026-09-05T09:02:03Z, last 2026-09-05T09:54:06Z)

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-postgres-db_conn_util_pct-0900-0955` (strong): postgres db_conn_util_pct: baseline 39.93 -> window mean 40.38 (max 44.23, change 1.1%), onset none detected
- [OBSERVED EVIDENCE] `met-postgres-p95_latency_ms-0900-0955` (strong): postgres p95_latency_ms: baseline 12.05 -> window mean 12.01 (max 13.0, change -0.3%), onset none detected
- [OBSERVED EVIDENCE] `met-auth-service-timeout_rate-0900-0955` (strong): auth-service timeout_rate: baseline 0.05 -> window mean 0.05 (max 0.06, change -1.4%), onset none detected
- [OBSERVED EVIDENCE] `met-auth-service-p99_latency_ms-0900-0955` (moderate): auth-service p99_latency_ms: baseline 90.04 -> window mean 89.61 (max 97.79, change -0.5%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Postgres lock wait and connection-count data
- [UNKNOWN] Whether report_rollup runs on the auth path at all

### 4. H4 - `configuration_regression` in `user-service` (confidence 0.00, critic: reject)
**INFERENCE:** The profile_badges feature flag enabled on user-service at 09:10Z causes session or token failures that cascade into auth. Mechanism: Feature flag enables a new code path in user-service that affects session or profile lookups, which auth-service or gateway depends on, causing 5xx and logouts.

Confidence breakdown: base 0.10; +0.12 supporting evidence (1 refs, reliability-weighted, capped); -0.45 contradicting evidence (4 refs, capped 0.45); +0.08 proposed cause (09:10) precedes/coincides with first observed anomaly (09:29); -0.02 1 acknowledged evidence gaps; -0.40 critic review adjustment; = 0.00 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [CONFIRMED FACT] `cfg-cc6f8080` (moderate): Config change on user-service: feature.profile_badges false -> true at 2026-09-05T09:10:00Z (OPS-2306)

Contradicting evidence:
- [CONFIRMED FACT] `topo-auth-service-both-d2` (strong): auth-service depends on ['postgres', 'redis']; called by ['api-gateway', 'payment-service'] (graph topology-v1)
- [OBSERVED EVIDENCE] `met-user-service-error_rate-0900-0955` (strong): user-service error_rate: baseline 0.41 -> window mean 0.4 (max 0.43, change -1.6%), onset none detected
- [OBSERVED EVIDENCE] `logpat-auth-service-f41941c5` (strong): 27x ERROR on auth-service: 'TokenValidationException: unsupported key type 'EC' in JWKS (validator=jose-4.2, kid=k20)' (first 2026-09-05T09:29:00Z, last 2026-09-05T09:54:18Z)
- [OBSERVED EVIDENCE] `met-user-service-timeout_rate-0900-0955` (moderate): user-service timeout_rate: baseline 0.05 -> window mean 0.05 (max 0.06, change -0.6%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Any code path linking profile_badges to auth or session handling

## Critic Review
- **Verdict:** `APPROVED` (rounds reviewed: 1)
- **Reasoning:** H1 is well supported. auth-service 2.14.0 (build 4410) started at 09:28:00Z, and the only 'unsupported key type EC ... validator=jose-4.2' errors begin at 09:29:00Z, so the failure follows the deploy by about a minute and the error names the library the deploy changed. Auth error rate steps from 0.3% to ~27% with flat latency, timeouts and request rate, which fits a deterministic validation failure. Gateway 500s from /v1/token/verify (from 09:29:03Z) and payment auth-check failures (from 09:30:08Z) follow in dependency order. I checked for an alternative trigger: auth-service has no config changes in 08:00-09:55, and its JWKS cache refreshes report a constant keys=4 from 08:30 to 09:26, so there is no sign of a key-set change before the deploy. The residual gap is that the EC kid's presence in 2.13.4's validation path was not directly compared, so the rollback test remains the confirmatory step, not a precondition.
- H1: **accept** - Deploy at 09:28 immediately precedes the library-specific EC validation errors at 09:29; error rate step, gateway and payment propagation are in time order; flat latency/timeouts/traffic rule out capacity. Auth-service logs show the EC error only under v2.14.0. Rollback confirmation is recommended but not required for approval.
- H2: **reject** - No auth-service configuration change in 08:00-09:55. JWKS cache refreshes report a constant keys=4 from 08:30 to 09:26, so no key-set expansion is visible before onset. The EC error appears only after the 2.14.0 start, which points to the validator change rather than an independent key publication. Not fully excluded (key count after 09:29 not compared), but unsupported as the primary cause.
- H3: **reject** - Postgres connection utilisation (40.4 vs 39.9%), p95 latency (12.0 ms flat) and auth-service timeout rate (0.05%) are all flat. Auth failures are validation exceptions, not DB timeouts. The 14.6 s report_rollup warnings started at 09:02 with no matching impact.
- H4: **reject** - user-service is not on auth-service's dependency path. Its error rate and timeout rate are flat. The auth errors are JWKS key-type exceptions, unrelated to profile badges. The change is temporal coincidence only.
- pre-check warning `single_source` on H3: all support comes from one source type (log)
- pre-check blocking `correlation_only` on H4: change hypothesis supported only by the change record itself (temporal correlation); no log/metric evidence of the changed behaviour
- pre-check warning `culprit_symptom` on H4: no log/metric evidence cited for culprit user-service
- pre-check warning `single_source` on H4: all support comes from one source type (config)
- alternative: JWKS key-set change coincident with the deploy (H2): not supported, as keys=4 is stable before onset and there is no config change.
- alternative: Database resource saturation from report_rollup (H3): contradicted by flat DB connection, latency and auth timeout metrics.
- alternative: Feature-flag side effect in user-service (H4): contradicted by topology and flat user-service metrics.

## Probable Root Cause
ROOT CAUSE IDENTIFIED (critic-approved; still an INFERENCE from evidence): deployment_regression in auth-service - auth-service 2.14.0 deploy (jose-4.2 JWT/JWKS validation and token-cache refactor) broke validation of EC keys, so auth-service rejects valid tokens and returns 500s, which propagate to api-gateway and payment-service.

## Corrective Actions
- Roll back auth-service from 2.14.0 to 2.13.4 immediately to restore token validation. This also serves as the confirmatory test of the hypothesis (dep-cbc63772).
- After rollback, confirm that auth-service error_rate returns to the ~0.3% baseline and that the 'unsupported key type EC' error stops appearing in logs (logpat-auth-service-f41941c5).
- Confirm recovery at api-gateway (/v1/token/verify 500s) and payment-service (authorization check failures), and check that users are no longer being logged out.
- Consider re-issuing or validating tokens for users who were logged out during the incident window, if session state was affected.

## Preventive Actions
- Before re-releasing 2.14.0, add a regression test that validates tokens and JWKS keys with EC kids against the jose-4.2 validator, using the key set in production (kid=k20).
- Add a pre-deploy canary or staging check that exercises JWT verification with every key type published in JWKS, and block promotion on validation exceptions.
- Review dependency upgrades (jose 4.x) and token-cache refactors for compatibility with existing key types before release, and require a rollback plan for auth changes.

## Monitoring Recommendations
- Alert when auth-service 5xx or error_rate exceeds 1% for 2 consecutive minutes, and page on-call at SEV1 thresholds.
- Alert on log pattern 'TokenValidationException' or 'unsupported key type' in auth-service at any non-zero rate, tagged with validator version and kid.
- Track api-gateway 500s on /v1/token/verify and payment-service upstream auth 500s as dependency-chain metrics, so propagation is visible within a minute.
- Add a deploy-marker correlation view showing auth-service build and version changes against error-rate onset, to shorten future triage.
- Keep JWKS cache refresh logs (key count and kid set) on dashboards so any key-set change can be distinguished from a code change.

## Evidence Gaps
- none recorded

## Limitations
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: critic verdict APPROVED

## Final Status
`ROOT_CAUSE_IDENTIFIED`

The most probable root cause of INC-002 is the auth-service 2.14.0 deployment. Its jose-4.2 JWT/JWKS validation fails on EC keys, which causes token verification to return 500s and propagates to api-gateway and payment-service, producing the login and checkout failures and forced logouts. The evidence is strong: the deploy preceded the errors by about one minute, the error names the changed library, and the failure is stable with flat latency and traffic. The hypothesis has not yet been directly confirmed. The rollback to 2.13.4 should be treated as the confirmatory test, and the residual gap (whether 2.13.4 validated the same EC kid) should be closed by that test.

## Execution Statistics
```json
{
  "rounds": 1,
  "tool_calls": 19,
  "tool_failures": 0,
  "tool_retries": 0,
  "partial_results": 0,
  "agent_failures": 0,
  "agent_retries": 0,
  "invalid_llm_outputs": 0,
  "messages_exchanged": 17,
  "evidence_records": 94,
  "duration_s": 59.84,
  "tokens": {
    "input_tokens": 40,
    "output_tokens": 20309,
    "cache_read_tokens": 23086,
    "cache_write_tokens": 60971,
    "llm_calls": 13,
    "cost_usd": 0.018010735
  },
  "tokens_by_agent": {
    "orchestrator": {
      "input_tokens": 6,
      "output_tokens": 1048,
      "cache_read_tokens": 1325,
      "cache_write_tokens": 2507,
      "llm_calls": 2,
      "cost_usd": 0.000851225
    },
    "dependency": {
      "input_tokens": 8,
      "output_tokens": 2651,
      "cache_read_tokens": 7247,
      "cache_write_tokens": 5308,
      "llm_calls": 3,
      "cost_usd": 0.0020622699999999997
    },
    "observability": {
      "input_tokens": 12,
      "output_tokens": 7894,
      "cache_read_tokens": 5721,
      "cache_write_tokens": 24337,
      "llm_calls": 4,
      "cost_usd": 0.007047535000000001
    },
    "reasoning": {
      "input_tokens": 4,
      "output_tokens": 4861,
      "cache_read_tokens": 0,
      "cache_write_tokens": 13401,
      "llm_calls": 1,
      "cost_usd": 0.004106024999999999
    },
    "critic": {
      "input_tokens": 6,
      "output_tokens": 2307,
      "cache_read_tokens": 8793,
      "cache_write_tokens": 11482,
      "llm_calls": 2,
      "cost_usd": 0.00267728
    },
    "reporting": {
      "input_tokens": 4,
      "output_tokens": 1548,
      "cache_read_tokens": 0,
      "cache_write_tokens": 3936,
      "llm_calls": 1,
      "cost_usd": 0.0012664
    }
  }
}
```
