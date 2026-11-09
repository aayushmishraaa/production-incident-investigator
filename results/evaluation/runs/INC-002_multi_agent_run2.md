# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-002
- **Title:** Login and checkout failures
- **Severity:** SEV1
- **Affected services:** api-gateway, auth-service, payment-service
- **Start time:** 2026-09-05T09:30:00+00:00
- **Investigation ID:** inv-599bd4e869 (multi_agent)
- **Final status:** `ROOT_CAUSE_IDENTIFIED`

## Executive Summary
INC-002 (SEV1), login and checkout failures with users being logged out, began at 2026-09-05T09:30Z. Investigation status is ROOT_CAUSE_IDENTIFIED. The most probable root cause (confidence 0.88) is the auth-service 2.14.0 deployment, which ran 2.13.4 -> 2.14.0 at 09:28Z and migrated JWT validation to jose-4.2 and refactored the token cache (dep-cbc63772). The new validator rejects EC keys in the JWKS with "TokenValidationException: unsupported key type 'EC'" (log-75321b43). auth-service error rate rose from a 0.3% baseline to a window mean of 12.88% (max 29.54%) starting 09:29Z (met-auth-service-error_rate-0900-0955). The failures propagated as 500s to api-gateway on /v1/token/verify (logpat-api-gateway-7c1adbea) and to payment-service checkout authorization (logpat-payment-service-a56d8d43). Alternative causes were examined and not supported: a JWKS key-rotation trigger (H2), Postgres report_rollup contention (H3), and the user-service feature flag (H4).

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
| 2026-09-05T09:29:00Z | OBSERVED EVIDENCE | Anomaly onset: auth-service error_rate: baseline 0.3 -> window mean 14.9 (max 28.14, change 4873.3%), onset 2026-09-05T09:29:00Z | met-auth-service-error_rate-0920-0940 |
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
- **OBSERVED EVIDENCE:** auth-service error_rate: baseline 0.3 -> window mean 14.9 (max 28.14, change 4873.3%), onset 2026-09-05T09:29:00Z (met-auth-service-error_rate-0920-0940)
- **OBSERVED EVIDENCE:** [dependency] api-gateway upstream dependencies are auth-service, order-service, payment-service, user-service; transitive chains reach postgres and redis via auth-service and payment-service. Graph version topology-v1, no topology changes listed. (topo-api-gateway-both-d3)
- **OBSERVED EVIDENCE:** [dependency] auth-service calls postgres and redis only; downstream dependents are api-gateway and payment-service. No topology changes listed. (topo-auth-service-both-d2)
- **OBSERVED EVIDENCE:** [dependency] payment-service calls auth-service, postgres and redis; downstream dependents are api-gateway and order-service. No topology changes listed. (topo-payment-service-both-d2)
- **OBSERVED EVIDENCE:** [dependency] order-service calls message-queue, payment-service, postgres, user-service. A topology-v2 edge (order-service -> redis) is effective only from 2026-09-15, after this incident. (topo-order-service-both-d2)
- **OBSERVED EVIDENCE:** [dependency] user-service calls postgres and redis; topology-v2 (effective 2026-09-15) adds notification-service -> user-service, not active during the incident. (topo-user-service-both-d2)
- **OBSERVED EVIDENCE:** [dependency] auth-service deployed 2.13.4 -> 2.14.0 (SUCCEEDED, ci-pipeline): 'Migrate JWT validation to jose-4.2; refactor token cache'. This is the only deployment in 08:30Z-09:36Z for any in-scope service. (dep-cbc63772)
- **OBSERVED EVIDENCE:** [dependency] auth-service error_rate rose from baseline mean 0.3% to window mean 14.9% (max 28.1%), onset 09:29Z, about 1 minute after the deploy at 09:28Z and 1 minute before T0. Sampled 09:25 value 0.31%, 09:30 value 27.7%. (met-auth-service-error_rate-0920-0940)
- **OBSERVED EVIDENCE:** [dependency] auth-service p99 latency (-0.8%) and timeout_rate (-0.8%) were flat across the deploy; no latency or timeout onset detected. The error increase is not accompanied by a latency/timeout signature. (met-auth-service-p99_latency_ms-0920-0940, met-auth-service-timeout_rate-0920-0940)
- **OBSERVED EVIDENCE:** [dependency] Config change feature.profile_badges false -> true on user-service (config-bot, OPS-2306) at 09:10Z. user-service is not in the requested service set and has no listed dependency on auth-service in the returned graph; it is 80 min before the auth error onset. (cfg-cc6f8080)
- **OBSERVED EVIDENCE:** [dependency] Dependency graph (topo-auth-service-both-d2): auth-service calls postgres and redis; its callers are api-gateway and payment-service (potentially impacted also order-service). No topology changes reported. (topo-auth-service-both-d2)
- **OBSERVED EVIDENCE:** [observability] DB connection utilisation, p95/p99 latency, CPU, memory and disk IO wait stayed at baseline levels across 09:00-09:55 (db_conn_util 40.4% vs 39.9% baseline; p99 25.1ms vs 25.0ms; CPU 35.2% flat). No onset detected. (met-postgres-db_conn_util_pct-0900-0955, met-postgres-p95_latency_ms-0900-0955, met-postgres-p99_latency_ms-0900-0955, met-postgres-cpu_pct-0900-0955, met-postgres-memory_pct-0900-0955, met-postgres-disk_io_wait_ms-0900-0955)
- **OBSERVED EVIDENCE:** [observability] Redis memory (59.9% vs 59.6%), cache hit rate (94.9% vs 95.0%), p99 latency (3.0ms vs 3.0ms) and CPU (15.1% vs 15.2%) show no change. timeout_rate is not collected for redis (missing). (met-redis-memory_pct-0900-0955, met-redis-cache_hit_rate-0900-0955, met-redis-p99_latency_ms-0900-0955, met-redis-cpu_pct-0900-0955)
- **OBSERVED EVIDENCE:** [observability] order-service error rate (0.6% vs 0.6%), p99 latency (395ms vs 403ms), timeout rate (0.1%), CPU (45.6%) and DB connection util (30.0%) are unchanged from baseline. (met-order-service-error_rate-0900-0955, met-order-service-p99_latency_ms-0900-0955, met-order-service-timeout_rate-0900-0955, met-order-service-cpu_pct-0900-0955, met-order-service-db_conn_util_pct-0900-0955)
- **OBSERVED EVIDENCE:** [observability] user-service error rate (0.4%), p99 latency (160ms vs 158ms), timeout rate (0.05%), CPU (30.1%), memory (50.0%) and DB connection util (30.1%) are unchanged from baseline. (met-user-service-error_rate-0900-0955, met-user-service-p99_latency_ms-0900-0955, met-user-service-timeout_rate-0900-0955, met-user-service-cpu_pct-0900-0955, met-user-service-db_conn_util_pct-0900-0955)
- **OBSERVED EVIDENCE:** [observability] First ERROR of a new kind at 09:29:00Z: 'TokenValidationException: unsupported key type EC in JWKS' (27 occurrences through 09:54:18Z). Coincides with symptom start. (logpat-auth-service-f41941c5, log-75321b43)
- **OBSERVED EVIDENCE:** [observability] Authorization failures due to upstream auth-service 500 begin at 09:30:08Z (9 errors) with retries; api-gateway logs auth-service 500 on /v1/token/verify from 09:29:03Z. (logpat-payment-service-a56d8d43, logpat-payment-service-8d3ec00b, logpat-api-gateway-7c1adbea)
- **OBSERVED EVIDENCE:** [observability] Recurring WARN slow statements 'SELECT report_rollup()' (up to 14.6s) from 09:02 to 09:54, 8 occurrences; not visibly reflected in postgres aggregate metrics. (logpat-postgres-44883ca5)
- **INFERENCE:** [observability] The report_rollup() slow queries are a background load issue that does not appear to be on the login/checkout critical path given flat postgres latency; it is unlikely to explain the 09:29 onset but was not ruled out for auth-service DB paths (auth-service DB metrics not yet examined). (logpat-postgres-44883ca5)
- **OBSERVED EVIDENCE:** [observability] api-gateway error_rate rose from baseline mean 0.5% to window mean 9.05% (max 19.93%); metric onset 09:29, sampled 0.51% at 09:25 then 13.9% at 09:30 and ~18-19% through 09:55. p99 latency and timeout rate were flat (p99 249ms vs 249ms baseline; timeout 0.1%). (met-api-gateway-error_rate-0900-0955, met-api-gateway-p99_latency_ms-0900-0955, met-api-gateway-timeout_rate-0900-0955)
- **OBSERVED EVIDENCE:** [observability] auth-service error_rate rose from baseline 0.3% to window mean 12.88% (max 29.54%); onset 09:29, 0.31% at 09:25 then 27.69% at 09:30 and ~25-28% through 09:55. p99 latency (90ms), timeout rate and CPU were flat versus baseline. (met-auth-service-error_rate-0900-0955, met-auth-service-p99_latency_ms-0900-0955, met-auth-service-timeout_rate-0900-0955, met-auth-service-cpu_pct-0900-0955)
- **OBSERVED EVIDENCE:** [observability] payment-service error_rate rose from baseline 0.8% to window mean 6.69% (max 15.09%); onset 09:30 (5.38% at 09:30, ~14% from 09:35 onward). p99 latency, timeout rate and DB connection utilisation were within baseline. (met-payment-service-error_rate-0900-0955, met-payment-service-p99_latency_ms-0900-0955, met-payment-service-timeout_rate-0900-0955, met-payment-service-db_conn_util_pct-0900-0955)
- **ASSUMPTION:** [critic: unsupported assumption] That the 2.13.4 validator accepted the same EC keys (rollback comparison not yet done). 
- **ASSUMPTION:** [critic: unsupported assumption] That the JWKS content actually contains EC keys before 09:28; the logs show keys=4 but not key types. 
- **ASSUMPTION:** [critic: unsupported assumption] That the per-endpoint login vs checkout split matches the claimed downstream paths; only aggregated patterns were available. 

## Investigation Performed
- Round 1 | observability | completed | attempts 1 | 4 tool calls | Characterize the 5xx spike and latency on login and checkout paths in api-gateway, auth-service, and payment-service from 09:00Z to now; identify first-error ti
- Round 1 | observability | completed | attempts 1 | 5 tool calls | Check shared data-store health (postgres, redis) and order-service/user-service for saturation or errors that coincide with the symptom start.
- Round 1 | dependency | completed | attempts 1 | 4 tool calls | Identify deployments, configuration changes, or feature flag/secret/TTL changes to api-gateway, auth-service, payment-service, and shared stores in the window 0
- Round 1 | dependency | completed | attempts 1 | 5 tool calls | Confirm the upstream/downstream call graph for the affected path (api-gateway -> auth/payment -> postgres/redis) and any recent topology changes.
- Round 1 | reasoning | completed | attempts 1 | 0 tool calls | Develop and rank competing hypotheses
- Round 1 | critic | completed | attempts 1 | 3 tool calls | Independently review hypotheses
- Round 1 | reporting | completed | attempts 1 | 0 tool calls | Write final report

## Root-Cause Hypotheses (ranked by evidence strength)
### 1. H1 - `deployment_regression` in `auth-service` (confidence 0.88, critic: accept)
**INFERENCE:** auth-service 2.14.0 deployment (JWT validation migrated to jose-4.2, token cache refactor) rejects EC keys in JWKS, causing token verification to return 500s that propagate to api-gateway login/token-verify and payment-service checkout authorization. Mechanism: auth-service 2.13.4 -> 2.14.0 deployed 09:28Z with jose-4.2 validator -> JWKS containing EC keys (kid k20+) is rejected with 'TokenValidationException: unsupported key type EC in JWKS' -> /v1/token/verify returns 500 -> api-gateway returns 5xx on login and payment-service fails authorization after retries (9 errors) -> users logged out and checkout fails. Latency/CPU/timeouts flat because failure is a per-request validation error, not saturation.

Confidence breakdown: base 0.10; +0.08 corroboration across >=2 independent source types; +0.78 supporting evidence (7 refs, reliability-weighted, capped); -0.05 contradicting evidence (1 refs, capped 0.45); +0.08 proposed cause (09:28) precedes/coincides with first observed anomaly (09:29); -0.08 4 acknowledged evidence gaps; +0.05 critic review adjustment; = 0.88 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [OBSERVED EVIDENCE] `log-75321b43` (strong): ERROR auth-service: TokenValidationException: unsupported key type 'EC' in JWKS (validator=jose-4.2, kid=k20)
- [OBSERVED EVIDENCE] `logpat-auth-service-f41941c5` (strong): 27x ERROR on auth-service: 'TokenValidationException: unsupported key type 'EC' in JWKS (validator=jose-4.2, kid=k20)' (first 2026-09-05T09:29:00Z, last 2026-09-05T09:54:18Z)
- [CONFIRMED FACT] `dep-cbc63772` (moderate): Deployment of auth-service 2.13.4->2.14.0 at 2026-09-05T09:28:00Z (SUCCEEDED): Migrate JWT validation to jose-4.2; refactor token cache
- [OBSERVED EVIDENCE] `met-auth-service-error_rate-0900-0955` (strong): auth-service error_rate: baseline 0.3 -> window mean 12.88 (max 29.54, change 4197.5%), onset 2026-09-05T09:29:00Z
- [OBSERVED EVIDENCE] `logpat-api-gateway-7c1adbea` (moderate): 14x WARN on api-gateway: 'auth-service returned 500 for /v1/token/verify (req 63)' (first 2026-09-05T09:29:03Z, last 2026-09-05T09:53:26Z)
- [OBSERVED EVIDENCE] `logpat-payment-service-a56d8d43` (moderate): 9x ERROR on payment-service: 'Authorization check failed: upstream auth-service 500 (charge ch_67)' (first 2026-09-05T09:30:08Z, last 2026-09-05T09:52:21Z)
- [CONFIRMED FACT] `topo-auth-service-both-d2` (moderate): auth-service depends on ['postgres', 'redis']; called by ['api-gateway', 'payment-service'] (graph topology-v1)

Contradicting evidence:
- [CONFIRMED FACT] `cfg-cc6f8080` (weak): Config change on user-service: feature.profile_badges false -> true at 2026-09-05T09:10:00Z (OPS-2306)

Remaining uncertainties / missing evidence:
- [UNKNOWN] auth-service 2.14.0 changelog/diff confirming the jose-4.2 EC key support path
- [UNKNOWN] Whether the 2.13.4 validator accepted the same JWKS (rollback comparison)
- [UNKNOWN] auth-service metrics for the token-cache path and JWKS fetch behaviour
- [UNKNOWN] Per-endpoint login vs checkout 5xx breakdown

### 2. H2 - `configuration_regression` in `auth-service` (confidence 0.11, critic: reject)
**INFERENCE:** A JWKS/signing key change (new EC key, e.g. kid k20, published or rotated around 09:29) is what triggers the rejection; the deploy only exposed it or is coincident. Mechanism: New EC signing key published to JWKS at ~09:29 -> auth-service token validation encounters an EC key type it does not accept -> 500s on token verify -> downstream login/checkout failures. The 2.14.0 deploy could be coincidental if the key rotation was the trigger.

Confidence breakdown: base 0.10; +0.08 corroboration across >=2 independent source types; +0.42 supporting evidence (2 refs, reliability-weighted, capped); -0.05 contradicting evidence (1 refs, capped 0.45); +0.08 proposed cause (09:29) precedes/coincides with first observed anomaly (09:29); -0.04 2 acknowledged evidence gaps; -0.40 critic review adjustment; = 0.11 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [OBSERVED EVIDENCE] `log-75321b43` (strong): ERROR auth-service: TokenValidationException: unsupported key type 'EC' in JWKS (validator=jose-4.2, kid=k20)
- [OBSERVED EVIDENCE] `met-auth-service-error_rate-0900-0955` (moderate): auth-service error_rate: baseline 0.3 -> window mean 12.88 (max 29.54, change 4197.5%), onset 2026-09-05T09:29:00Z

Contradicting evidence:
- [CONFIRMED FACT] `dep-cbc63772` (weak): Deployment of auth-service 2.13.4->2.14.0 at 2026-09-05T09:28:00Z (SUCCEEDED): Migrate JWT validation to jose-4.2; refactor token cache

Remaining uncertainties / missing evidence:
- [UNKNOWN] No config/secret/JWKS publication events were queried for 09:00-09:30 (INFO logs not scanned)
- [UNKNOWN] No evidence of a key rotation or new EC key issuance

### 3. H3 - `resource_saturation` in `postgres` (confidence 0.00, critic: reject)
**INFERENCE:** Slow report_rollup() statements on postgres degrade auth/payment database paths, causing errors on login and checkout. Mechanism: Long-running report_rollup() queries (up to 14.6s) hold resources -> auth-service or payment-service DB calls slow or fail -> 5xx. Would need to show up in auth/payment DB metrics.

Confidence breakdown: base 0.10; +0.04 supporting evidence (1 refs, reliability-weighted, capped); -0.45 contradicting evidence (3 refs, capped 0.45); +0.08 proposed cause (09:02) precedes/coincides with first observed anomaly (09:29); -0.04 2 acknowledged evidence gaps; -0.40 critic review adjustment; = 0.00 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-postgres-44883ca5` (weak): 8x WARN on postgres: 'duration: 14602 ms statement: SELECT report_rollup()' (first 2026-09-05T09:02:03Z, last 2026-09-05T09:54:06Z)

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-postgres-db_conn_util_pct-0900-0955` (strong): postgres db_conn_util_pct: baseline 39.93 -> window mean 40.38 (max 44.23, change 1.1%), onset none detected
- [OBSERVED EVIDENCE] `logpat-auth-service-f41941c5` (strong): 27x ERROR on auth-service: 'TokenValidationException: unsupported key type 'EC' in JWKS (validator=jose-4.2, kid=k20)' (first 2026-09-05T09:29:00Z, last 2026-09-05T09:54:18Z)
- [OBSERVED EVIDENCE] `met-auth-service-timeout_rate-0900-0955` (moderate): auth-service timeout_rate: baseline 0.05 -> window mean 0.05 (max 0.06, change -1.4%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] auth-service and payment-service DB latency/error metrics
- [UNKNOWN] Whether report_rollup runs on the auth/payment path

### 4. H4 - `configuration_regression` in `user-service` (confidence 0.00, critic: reject)
**INFERENCE:** The user-service feature.profile_badges flag enabled at 09:10Z causes the login/checkout failures. Mechanism: Flag enabled -> user-service behaviour change -> session/logout effects on login path. Mechanism is not established.

Confidence breakdown: base 0.10; +0.04 supporting evidence (1 refs, reliability-weighted, capped); -0.45 contradicting evidence (3 refs, capped 0.45); +0.08 proposed cause (09:10) precedes/coincides with first observed anomaly (09:29); -0.02 1 acknowledged evidence gaps; -0.40 critic review adjustment; = 0.00 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [CONFIRMED FACT] `cfg-cc6f8080` (weak): Config change on user-service: feature.profile_badges false -> true at 2026-09-05T09:10:00Z (OPS-2306)

Contradicting evidence:
- [CONFIRMED FACT] `topo-auth-service-both-d2` (strong): auth-service depends on ['postgres', 'redis']; called by ['api-gateway', 'payment-service'] (graph topology-v1)
- [OBSERVED EVIDENCE] `met-user-service-error_rate-0900-0955` (strong): user-service error_rate: baseline 0.41 -> window mean 0.4 (max 0.43, change -1.6%), onset none detected
- [OBSERVED EVIDENCE] `log-75321b43` (moderate): ERROR auth-service: TokenValidationException: unsupported key type 'EC' in JWKS (validator=jose-4.2, kid=k20)

Remaining uncertainties / missing evidence:
- [UNKNOWN] Whether user-service calls auth-service or affects session state (not in topology)

## Critic Review
- **Verdict:** `APPROVED` (rounds reviewed: 1)
- **Reasoning:** Leading hypothesis H1 (auth-service 2.14.0 deployment regression, jose-4.2 validator rejecting EC keys in JWKS) is consistent in time and supported by multiple independent sources. The auth-service ERROR pattern starts at 09:29:00Z, one minute after the 09:28:00Z deploy of 2.13.4->2.14.0 (the only auth-service deployment in the window). The error recurs with distinct kids (k20, k24, k67, k41, k45, k56, k33) through 09:34 and to 09:54 in the full window. Downstream 500s appear at api-gateway (09:29:03Z) and payment-service (09:30:08Z) after auth onset, and topology places auth-service upstream of both login and checkout. The error rate moves 0.3% -> ~13% mean (max ~30%), while timeouts, latency and DB connection utilisation stay flat, which fits a per-request validation failure rather than saturation. H2 is not supported: INFO logs show the JWKS cache refreshing with a constant keys=4 from 09:07 through 09:31, with no key rotation or new key publication event before onset, so the key-rotation trigger is not evidenced and the deploy is the only change in the window. H3 is contradicted by flat DB connection utilisation, and the auth errors are validator errors, not DB errors or timeouts. H4 has no path to auth-service per topology, flat user-service metrics, and no mechanism. Remaining limitations: the rollback comparison and the 2.13.4 validator behaviour on the same JWKS are not yet confirmed, and the per-endpoint login vs checkout split is not available. These do not block approval of the category (deployment regression) and culprit (auth-service).
- H1: **accept** - Onset at 09:29:00Z is one minute after the only auth-service deploy. The error message names the EC key-type failure in the jose-4.2 validator, which matches the changelog. Downstream 500s follow auth onset at api-gateway and payment-service. Error rate rises sharply while latency, timeouts and saturation stay flat, consistent with a per-request validation failure. Limitation: rollback comparison not yet done, but not required for category attribution.
- H2: **reject** - INFO logs show JWKS cache refreshes with a constant keys=4 from 09:07 to 09:31, with no new key publication or rotation event before onset. The key-rotation trigger is therefore unevidenced, and the deploy is the only change in the window. The kid values in errors vary, but this does not show a rotation event.
- H3: **reject** - Postgres db_conn_util_pct is flat (39.9 to 40.4%) with no onset. Auth errors are validator exceptions, not DB errors or timeouts. The report_rollup slow statements are sparse and predate onset by 27 minutes, and their link to the auth/payment path is unshown.
- H4: **reject** - Topology shows auth-service does not depend on user-service. user-service error rate is flat at 0.4%. No mechanism or log/metric evidence links the flag to login/checkout failures. The 09:10 change is 19 minutes before onset and is not corroborated.
- pre-check warning `single_source` on H3: all support comes from one source type (log)
- pre-check blocking `correlation_only` on H4: change hypothesis supported only by the change record itself (temporal correlation); no log/metric evidence of the changed behaviour
- pre-check warning `culprit_symptom` on H4: no log/metric evidence cited for culprit user-service
- pre-check warning `single_source` on H4: all support comes from one source type (config)
- alternative: Key rotation publishing EC keys (H2) coincident with the deploy; not supported by constant keys=4 JWKS refresh logs, but a JWKS content diff before/after 09:28 would close this fully.
- alternative: Postgres report_rollup contention (H3); refuted by flat DB connection utilisation and validator-type errors.

## Probable Root Cause
ROOT CAUSE IDENTIFIED (critic-approved; still an INFERENCE from evidence): deployment_regression in auth-service - auth-service 2.14.0 deployment (JWT validation migrated to jose-4.2, token cache refactor) rejects EC keys in JWKS, causing token verification to return 500s that propagate to api-gateway login/token-verify and payment-service checkout authorization.

## Corrective Actions
- Roll back auth-service from 2.14.0 to 2.13.4 to restore token verification and stop the login and checkout failures (dep-cbc63772 is the only auth-service change in the window).
- After rollback, confirm recovery by checking that auth-service error_rate returns to baseline (~0.3%) and that api-gateway and payment-service 500 warnings/errors stop.
- Notify affected customers and support teams of the forced logouts and failed checkouts, and review failed charges for retry or reconciliation (payment-service, ch_67 pattern).

## Preventive Actions
- Fix the jose-4.2 validator so it accepts EC keys present in the JWKS (kid k20 and later), and add a test that verifies token validation against a JWKS containing EC keys before release.
- Add a pre-deploy or canary verification step for auth-service that exercises token verification against production-like JWKS content, so validator regressions are caught before full rollout.
- Confirm the rollback comparison: run 2.13.4 validator against the same JWKS to verify it accepts the EC keys, and diff the JWKS content before and after 09:28Z to close the H2 (key rotation) question fully.

## Monitoring Recommendations
- Alert on auth-service error_rate exceeding baseline (e.g., >1% for 2 minutes), and on any 'unsupported key type' TokenValidationException log pattern.
- Alert on api-gateway 5xx rate for /v1/token/verify and login, and on payment-service 'Authorization check failed: upstream auth-service 500' log pattern.
- Track JWKS key count and key types (kty) on each refresh in auth-service logs to detect unexpected key publication or rotation events.
- Keep deployment events for auth-service correlated with error-rate dashboards so future regressions are visible within minutes of rollout.

## Evidence Gaps
- none recorded

## Limitations
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: critic verdict APPROVED

## Final Status
`ROOT_CAUSE_IDENTIFIED`

The most probable root cause of INC-002 is the auth-service 2.14.0 deployment, whose jose-4.2 JWT validator rejects EC keys in the JWKS, causing token verification 500s that propagate to login and checkout. The timing (deploy at 09:28Z, errors from 09:29Z), the error pattern, and the topology all support this, and the alternatives were not supported by the evidence. The remaining gaps are the unconfirmed rollback comparison with the 2.13.4 validator and the lack of a per-endpoint login vs checkout split; these do not change the category or culprit. Rolling back auth-service is the immediate mitigation.

## Execution Statistics
```json
{
  "rounds": 1,
  "tool_calls": 24,
  "tool_failures": 0,
  "tool_retries": 0,
  "partial_results": 0,
  "agent_failures": 0,
  "agent_retries": 0,
  "invalid_llm_outputs": 0,
  "messages_exchanged": 20,
  "evidence_records": 102,
  "duration_s": 56.63,
  "tokens": {
    "input_tokens": 46,
    "output_tokens": 20203,
    "cache_read_tokens": 26471,
    "cache_write_tokens": 63145,
    "llm_calls": 15,
    "cost_usd": 0.018263935
  },
  "tokens_by_agent": {
    "orchestrator": {
      "input_tokens": 6,
      "output_tokens": 1179,
      "cache_read_tokens": 2650,
      "cache_write_tokens": 990,
      "llm_calls": 2,
      "cost_usd": 0.0007403500000000001
    },
    "dependency": {
      "input_tokens": 14,
      "output_tokens": 4075,
      "cache_read_tokens": 10377,
      "cache_write_tokens": 10335,
      "llm_calls": 5,
      "cost_usd": 0.003434545
    },
    "observability": {
      "input_tokens": 12,
      "output_tokens": 7305,
      "cache_read_tokens": 5711,
      "cache_write_tokens": 23816,
      "llm_calls": 4,
      "cost_usd": 0.006687809999999999
    },
    "reasoning": {
      "input_tokens": 4,
      "output_tokens": 3850,
      "cache_read_tokens": 0,
      "cache_write_tokens": 14086,
      "llm_calls": 1,
      "cost_usd": 0.00368615
    },
    "critic": {
      "input_tokens": 6,
      "output_tokens": 2427,
      "cache_read_tokens": 7733,
      "cache_write_tokens": 10197,
      "llm_calls": 2,
      "cost_usd": 0.0025660550000000002
    },
    "reporting": {
      "input_tokens": 4,
      "output_tokens": 1367,
      "cache_read_tokens": 0,
      "cache_write_tokens": 3721,
      "llm_calls": 1,
      "cost_usd": 0.0011490250000000001
    }
  }
}
```
