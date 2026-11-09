# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-001
- **Title:** Payment API latency spike
- **Severity:** SEV2
- **Affected services:** api-gateway, payment-service
- **Start time:** 2026-09-02T14:00:00+00:00
- **Investigation ID:** inv-60bf19e31d (multi_agent)
- **Final status:** `ROOT_CAUSE_IDENTIFIED`

## Executive Summary
INC-001 (SEV2): Payment API latency spike. Checkout took 3-5 seconds and some payments failed with 5xx errors from 14:00Z. The investigation status is ROOT_CAUSE_IDENTIFIED, and the critic approved the result. The leading hypothesis (H1, confidence 0.63) is database connection pool exhaustion in payment-service. Connections held by RefundService.processPartialRefund filled payment-db-pool, so payment calls queued, timed out after 5 seconds, and returned errors. Leak-detection warnings for connections held over 30 seconds by RefundService began at 13:45Z (payment-service logs). Payment-service db_conn_util_pct rose from about 35% before any latency change (critic review; 52% at 13:50Z, 78% at 13:55Z, 96% at 14:00Z). At 14:00:16Z the pool reached active=50, idle=0, with up to 98 waiters, and the timeout errors began (logpat-payment-service-7d1739af). Payment-service P95 latency rose from a 150 ms baseline to a window mean of 1315 ms, and error rate rose from 0.8% to 9.9% from 14:00Z (met-payment-service-p95_latency_ms, met-payment-service-error_rate). API gateway 503s followed at 14:01Z (logpat-api-gateway-2be6bd23). Request rate was flat (about 302 req/s), so the cause is a holding problem, not load. The hypotheses that Postgres report_rollup contention (H2) and the notification-service 3.4.1 deployment (H3) caused the incident were rejected. The trigger that started the RefundService connection hold has not been identified, so this is the most probable explanation at the category and culprit level, not a fully confirmed mechanism.

## Incident Timeline
| Time (UTC) | Label | Event | Evidence |
|---|---|---|---|
| 2026-09-02T13:31:28Z | OBSERVED EVIDENCE | First log: 7x WARN on postgres: 'duration: 18302 ms statement: SELECT report_rollup()' (first 2026-09-02T13:31:28Z, last 2026-09-02T14:23:09Z) | logpat-postgres-44883ca5 |
| 2026-09-02T13:31:29Z | OBSERVED EVIDENCE | First log: 7x WARN on api-gateway: 'Slow client upload from 10.4.81.12 (1.9MB)' (first 2026-09-02T13:31:29Z, last 2026-09-02T14:24:02Z) | logpat-api-gateway-88b04940 |
| 2026-09-02T13:35:35Z | OBSERVED EVIDENCE | First log: 5x WARN on auth-service: 'Login rate limit hit for user id u-47' (first 2026-09-02T13:35:35Z, last 2026-09-02T14:19:54Z) | logpat-auth-service-cc8d3b87 |
| 2026-09-02T13:36:43Z | OBSERVED EVIDENCE | First log: 4x WARN on order-service: 'Inventory reservation retry for sku-47' (first 2026-09-02T13:36:43Z, last 2026-09-02T14:22:14Z) | logpat-order-service-95abd1bb |
| 2026-09-02T13:37:07Z | OBSERVED EVIDENCE | First log: 7x WARN on notification-service: 'SMTP provider throttled 1 message' (first 2026-09-02T13:37:07Z, last 2026-09-02T14:23:53Z) | logpat-notification-service-54b86179 |
| 2026-09-02T13:44:44Z | OBSERVED EVIDENCE | First log: 4x WARN on payment-service: 'Card network soft decline (code 05) for charge ch_88' (first 2026-09-02T13:44:44Z, last 2026-09-02T14:20:23Z) | logpat-payment-service-7e9bf84f |
| 2026-09-02T13:45:08Z | OBSERVED EVIDENCE | First log: 9x WARN on payment-service: 'HikariPool-payment - Connection leak detection triggered for connection conn-98, held > 30000 ms by RefundService.processPartialRefund' (first 2026-09-02T13:45:08Z, last 2026-09-02T14:00:16Z) | logpat-payment-service-9d1f3d29 |
| 2026-09-02T13:49:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service db_conn_util_pct: baseline 34.95 -> window mean 57.85 (max 100.0, change 65.5%), onset 2026-09-02T13:49:00Z | met-payment-service-db_conn_util_pct-1330-1405 |
| 2026-09-02T13:54:00Z | CONFIRMED FACT | Deployment of notification-service 3.4.0->3.4.1 at 2026-09-02T13:54:00Z (SUCCEEDED): Update email templates for receipts | dep-d757f128 |
| 2026-09-02T13:54:42Z | OBSERVED EVIDENCE | First log: 4x WARN on user-service: 'Deprecated API /v1/users/legacy called by client web-86' (first 2026-09-02T13:54:42Z, last 2026-09-02T14:17:53Z) | logpat-user-service-742b555e |
| 2026-09-02T14:00:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service p95_latency_ms: baseline 150.24 -> window mean 1315.14 (max 3018.96, change 775.3%), onset 2026-09-02T14:00:00Z | met-payment-service-p95_latency_ms-1330-1425 |
| 2026-09-02T14:00:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service p99_latency_ms: baseline 302.14 -> window mean 2429.49 (max 5545.92, change 704.1%), onset 2026-09-02T14:00:00Z | met-payment-service-p99_latency_ms-1330-1425 |
| 2026-09-02T14:00:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service error_rate: baseline 0.8 -> window mean 9.93 (max 23.67, change 1139.4%), onset 2026-09-02T14:00:00Z | met-payment-service-error_rate-1330-1425 |
| 2026-09-02T14:00:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service timeout_rate: baseline 0.1 -> window mean 8.04 (max 19.09, change 7957.0%), onset 2026-09-02T14:00:00Z | met-payment-service-timeout_rate-1330-1425 |
| 2026-09-02T14:00:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service p95_latency_ms: baseline 150.24 -> window mean 469.81 (max 2865.11, change 212.7%), onset 2026-09-02T14:00:00Z | met-payment-service-p95_latency_ms-1330-1405 |
| 2026-09-02T14:00:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service error_rate: baseline 0.8 -> window mean 3.39 (max 21.36, change 323.6%), onset 2026-09-02T14:00:00Z | met-payment-service-error_rate-1330-1405 |
| 2026-09-02T14:00:00Z | CONFIRMED FACT | Reported symptom start |  |
| 2026-09-02T14:00:16Z | OBSERVED EVIDENCE | First log: 29x ERROR on payment-service: 'Timeout acquiring connection from pool payment-db-pool after 5000ms (active=50, idle=0, waiting=46)' (first 2026-09-02T14:00:16Z, last 2026-09-02T14:24:16Z) | logpat-payment-service-7d1739af |
| 2026-09-02T14:01:00Z | OBSERVED EVIDENCE | Anomaly onset: api-gateway p95_latency_ms: baseline 119.71 -> window mean 868.12 (max 2004.12, change 625.2%), onset 2026-09-02T14:01:00Z | met-api-gateway-p95_latency_ms-1330-1425 |
| 2026-09-02T14:01:00Z | OBSERVED EVIDENCE | Anomaly onset: api-gateway error_rate: baseline 0.5 -> window mean 4.05 (max 9.88, change 710.4%), onset 2026-09-02T14:01:00Z | met-api-gateway-error_rate-1330-1425 |
| 2026-09-02T14:01:09Z | OBSERVED EVIDENCE | First log: 11x ERROR on api-gateway: 'Upstream payment-service responded 503 for POST /v1/payments (latency 50ms)' (first 2026-09-02T14:01:09Z, last 2026-09-02T14:23:05Z) | logpat-api-gateway-2be6bd23 |
| 2026-09-02T14:06:00Z | CONFIRMED FACT | Incident reported |  |

## Observed Symptoms
- **OBSERVED EVIDENCE:** payment-service p95_latency_ms: baseline 150.24 -> window mean 1315.14 (max 3018.96, change 775.3%), onset 2026-09-02T14:00:00Z (met-payment-service-p95_latency_ms-1330-1425)
- **OBSERVED EVIDENCE:** payment-service p99_latency_ms: baseline 302.14 -> window mean 2429.49 (max 5545.92, change 704.1%), onset 2026-09-02T14:00:00Z (met-payment-service-p99_latency_ms-1330-1425)
- **OBSERVED EVIDENCE:** payment-service error_rate: baseline 0.8 -> window mean 9.93 (max 23.67, change 1139.4%), onset 2026-09-02T14:00:00Z (met-payment-service-error_rate-1330-1425)
- **OBSERVED EVIDENCE:** payment-service timeout_rate: baseline 0.1 -> window mean 8.04 (max 19.09, change 7957.0%), onset 2026-09-02T14:00:00Z (met-payment-service-timeout_rate-1330-1425)
- **OBSERVED EVIDENCE:** api-gateway p95_latency_ms: baseline 119.71 -> window mean 868.12 (max 2004.12, change 625.2%), onset 2026-09-02T14:01:00Z (met-api-gateway-p95_latency_ms-1330-1425)
- **OBSERVED EVIDENCE:** api-gateway error_rate: baseline 0.5 -> window mean 4.05 (max 9.88, change 710.4%), onset 2026-09-02T14:01:00Z (met-api-gateway-error_rate-1330-1425)
- **OBSERVED EVIDENCE:** payment-service db_conn_util_pct: baseline 34.95 -> window mean 57.85 (max 100.0, change 65.5%), onset 2026-09-02T13:49:00Z (met-payment-service-db_conn_util_pct-1330-1405)
- **OBSERVED EVIDENCE:** payment-service p95_latency_ms: baseline 150.24 -> window mean 469.81 (max 2865.11, change 212.7%), onset 2026-09-02T14:00:00Z (met-payment-service-p95_latency_ms-1330-1405)
- **OBSERVED EVIDENCE:** payment-service error_rate: baseline 0.8 -> window mean 3.39 (max 21.36, change 323.6%), onset 2026-09-02T14:00:00Z (met-payment-service-error_rate-1330-1405)
- **OBSERVED EVIDENCE:** [dependency] Dependency graph for payment-service (topology-v1) shows upstream dependencies auth-service, postgres, redis (plus chains via auth-service to postgres and redis). Downstream dependents are api-gateway and order-service. No topology changes are listed for payment-service. (topo-payment-service-both-d3)
- **OBSERVED EVIDENCE:** [dependency] order-service (topology-v1) upstream: message-queue, payment-service, postgres, user-service; downstream: api-gateway. The only listed topology change is topology-v2 adding edge order-service -> redis, effective 2026-09-15, which is after this incident (2026-09-02), so it is not a candidate cause. (topo-order-service-both-d2)
- **OBSERVED EVIDENCE:** [dependency] Only deployment in 13:00-14:25Z window: notification-service 3.4.0->3.4.1 at 2026-09-02T13:54:00Z (SUCCEEDED, email template update). notification-service is not in payment-service's or order-service's upstream/downstream graph, so it is not an obvious path to payment latency. (dep-d757f128)
- **INFERENCE:** [dependency] Payment latency could originate in shared dependencies (auth-service, postgres, redis) that are upstream of payment-service; these need metric checks, since the graph shows no change to them. 
- **OBSERVED EVIDENCE:** [dependency] No deployments to payment-service, api-gateway, auth-service or order-service were recorded between 13:30Z and 14:10Z. The only deployment in the window (all services queried) was notification-service 3.4.0 -> 3.4.1 at 13:54Z (receipt email template update, ci-pipeline, SUCCEEDED). (dep-d757f128)
- **OBSERVED EVIDENCE:** [dependency] Payment-service dependency graph (topology-v1): upstream = auth-service, postgres, redis (and auth-service -> postgres/redis chains); downstream callers = api-gateway, order-service. notification-service is not in payment-service's upstream or downstream graph, and no topology changes were recorded. (topo-payment-service-both-d2)
- **OBSERVED EVIDENCE:** [observability] auth-service latency, error rate, timeout rate, CPU and memory are flat across 13:30-14:25 vs baseline 13:00-13:30 (p95 ~45ms both; error_rate ~0.3%; timeout ~0.05%; no onset detected). (met-auth-service-p95_latency_ms-1330-1425, met-auth-service-p99_latency_ms-1330-1425, met-auth-service-error_rate-1330-1425, met-auth-service-timeout_rate-1330-1425, met-auth-service-cpu_pct-1330-1425, met-auth-service-memory_pct-1330-1425)
- **OBSERVED EVIDENCE:** [observability] postgres db_conn_util_pct rose from baseline mean 40.6% to 53.2% window mean (max 67.9%), with onset at 13:55Z (57.0% at 13:55 sample, ~64% from 14:00 onward). (met-postgres-db_conn_util_pct-1330-1425)
- **OBSERVED EVIDENCE:** [observability] postgres p95 latency (~12ms), CPU (~35%), disk IO wait (~2ms) and error rate (~0.05%) are unchanged vs baseline. (met-postgres-p95_latency_ms-1330-1425, met-postgres-cpu_pct-1330-1425, met-postgres-disk_io_wait_ms-1330-1425, met-postgres-error_rate-1330-1425)
- **OBSERVED EVIDENCE:** [observability] postgres logged slow statements 'SELECT report_rollup()' (e.g. 18302 ms), 7 occurrences from 13:31:28Z to 14:23:09Z. (logpat-postgres-44883ca5)
- **OBSERVED EVIDENCE:** [observability] redis p95 latency (~1.5ms), cache hit rate (~95%), CPU (~15%), memory (~60%) and error rate are unchanged vs baseline. (met-redis-p95_latency_ms-1330-1425, met-redis-cache_hit_rate-1330-1425, met-redis-cpu_pct-1330-1425, met-redis-memory_pct-1330-1425, met-redis-error_rate-1330-1425)
- **OBSERVED EVIDENCE:** [observability] payment-service ERROR logs: 'Timeout acquiring connection from pool payment-db-pool after 5000ms (active=50, idle=0, waiting=46-98)', 29 occurrences from 14:00:16Z to 14:24:16Z. (logpat-payment-service-7d1739af, log-853bbeab, log-55cc357e)
- **OBSERVED EVIDENCE:** [observability] payment-service WARN logs: HikariPool connection leak detection triggered (connection held >30000ms) by RefundService.processPartialRefund, 9 occurrences 13:45:08Z to 14:00:16Z, preceding the pool exhaustion. (logpat-payment-service-9d1f3d29)
- **OBSERVED EVIDENCE:** [observability] api-gateway ERROR logs: upstream payment-service responded 503 for POST /v1/payments, 11 occurrences, first 14:01:09Z, last 14:23:05Z. (logpat-api-gateway-2be6bd23, log-143e39ed)
- **INFERENCE:** [observability] Connections held by RefundService.processPartialRefund (leak detection) may be exhausting payment-db-pool, causing checkout/payment request timeouts. Postgres itself is not CPU/latency saturated, so the constraint appears to be pool/connection holding rather than DB compute. Needs confirmation by the payment-service/DB team. (logpat-payment-service-9d1f3d29, logpat-payment-service-7d1739af, met-postgres-db_conn_util_pct-1330-1425)
- **OBSERVED EVIDENCE:** [observability] payment-service P95 latency rose from baseline mean 150.24 ms to window mean 1315.14 ms (+775%), max 3018.96 ms. Sampled series: 13:55 at 147.8 ms, 14:00 at 811 ms, 14:05 at 2714 ms, staying ~2700-2950 ms through 14:25. Onset detected 14:00:00Z. (met-payment-service-p95_latency_ms-1330-1425)
- **ASSUMPTION:** [critic: unsupported assumption] That the leaked connections belong exclusively to RefundService is inferred from application leak-detection attribution; pg_stat_activity was not queried. 
- **ASSUMPTION:** [critic: unsupported assumption] The trigger that started the RefundService connection hold at ~13:45Z is not explained. 

## Investigation Performed
- Round 1 | observability | completed | attempts 1 | 3 tool calls | Characterize latency and 5xx error rate for payment-service and api-gateway from 13:30Z onward; identify the onset time relative to 14:00Z and which endpoints a
- Round 1 | observability | completed | attempts 1 | 4 tool calls | Check downstream dependencies of payment-service (auth-service, postgres, redis) for latency, saturation, connection pool usage, and errors over the same window
- Round 1 | dependency | completed | attempts 1 | 3 tool calls | Identify deployments, configuration changes, or feature flag changes to payment-service, api-gateway, auth-service, and order-service in the window 13:30Z-14:10
- Round 1 | dependency | completed | attempts 1 | 3 tool calls | Review the upstream and downstream dependency graph for payment-service and its callers, and check for any topology changes since the prior graph version.
- Round 1 | reasoning | completed | attempts 1 | 0 tool calls | Develop and rank competing hypotheses
- Round 1 | critic | completed | attempts 1 | 3 tool calls | Independently review hypotheses
- Round 1 | reporting | completed | attempts 1 | 0 tool calls | Write final report

## Root-Cause Hypotheses (ranked by evidence strength)
### 1. H1 - `db_connection_pool_exhaustion` in `payment-service` (confidence 0.63, critic: accept)
**INFERENCE:** Connections leaked by RefundService.processPartialRefund exhaust payment-db-pool, so checkout payment calls queue, time out and return 5xx. Mechanism: RefundService.processPartialRefund begins holding pooled connections (leak detection at 13:45Z, held >30s) -> free connections in payment-db-pool shrink and Postgres connection utilisation climbs (41%->57% at 13:55Z, ~64% from 14:00Z) -> at 14:00:16Z the pool hits active=50, idle=0 with 46-98 waiters -> payment requests wait 5s, time out, and fail -> payment-service P95/P99/error/timeout step up at 14:00Z -> api-gateway sees 503s and P95 rise at 14:01Z.

Confidence breakdown: base 0.10; +0.08 corroboration across >=2 independent source types; +0.78 supporting evidence (8 refs, reliability-weighted, capped); -0.30 contradicting evidence (2 refs, capped 0.45); +0.08 proposed cause (13:45) precedes/coincides with first observed anomaly (13:49); -0.08 4 acknowledged evidence gaps; +0.05 critic review adjustment; = 0.63 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-payment-service-9d1f3d29` (strong): 9x WARN on payment-service: 'HikariPool-payment - Connection leak detection triggered for connection conn-98, held > 30000 ms by RefundService.processPartialRefund' (first 2026-09-02T13:45:08Z, last 2026-09-02T14:00:16Z)
- [OBSERVED EVIDENCE] `logpat-payment-service-7d1739af` (strong): 29x ERROR on payment-service: 'Timeout acquiring connection from pool payment-db-pool after 5000ms (active=50, idle=0, waiting=46)' (first 2026-09-02T14:00:16Z, last 2026-09-02T14:24:16Z)
- [OBSERVED EVIDENCE] `met-payment-service-p95_latency_ms-1330-1425` (strong): payment-service p95_latency_ms: baseline 150.24 -> window mean 1315.14 (max 3018.96, change 775.3%), onset 2026-09-02T14:00:00Z
- [OBSERVED EVIDENCE] `met-payment-service-error_rate-1330-1425` (moderate): payment-service error_rate: baseline 0.8 -> window mean 9.93 (max 23.67, change 1139.4%), onset 2026-09-02T14:00:00Z
- [OBSERVED EVIDENCE] `met-payment-service-timeout_rate-1330-1425` (strong): payment-service timeout_rate: baseline 0.1 -> window mean 8.04 (max 19.09, change 7957.0%), onset 2026-09-02T14:00:00Z
- [OBSERVED EVIDENCE] `met-postgres-db_conn_util_pct-1330-1425` (moderate): postgres db_conn_util_pct: baseline 40.59 -> window mean 53.15 (max 67.91, change 31.0%), onset 2026-09-02T13:55:00Z
- [OBSERVED EVIDENCE] `logpat-api-gateway-2be6bd23` (moderate): 11x ERROR on api-gateway: 'Upstream payment-service responded 503 for POST /v1/payments (latency 50ms)' (first 2026-09-02T14:01:09Z, last 2026-09-02T14:23:05Z)
- [OBSERVED EVIDENCE] `met-payment-service-request_rate-1330-1425` (moderate): payment-service request_rate: baseline 302.3 -> window mean 301.62 (max 332.79, change -0.2%), onset none detected

Contradicting evidence:
- [OBSERVED EVIDENCE] `logpat-payment-service-9d1f3d29` (moderate): 9x WARN on payment-service: 'HikariPool-payment - Connection leak detection triggered for connection conn-98, held > 30000 ms by RefundService.processPartialRefund' (first 2026-09-02T13:45:08Z, last 2026-09-02T14:00:16Z)
- [OBSERVED EVIDENCE] `met-postgres-db_conn_util_pct-1330-1425` (moderate): postgres db_conn_util_pct: baseline 40.59 -> window mean 53.15 (max 67.91, change 31.0%), onset 2026-09-02T13:55:00Z

Remaining uncertainties / missing evidence:
- [UNKNOWN] pg_stat_activity: which sessions and which application hold the connections, and their query state and age
- [UNKNOWN] Confirmation that the leaked connections belong to RefundService (vs. report_rollup or other sessions)
- [UNKNOWN] Per-pool acquire-time and active-count time series for payment-db-pool from 13:40Z onward
- [UNKNOWN] Endpoint-level breakdown of which payment routes fail

### 2. H2 - `resource_saturation` in `postgres` (confidence 0.00, critic: reject)
**INFERENCE:** Long-running report_rollup() statements in Postgres hold connections or locks, reducing the connections available to payment-service and causing pool exhaustion. Mechanism: report_rollup() runs slow (up to 18.3s) from 13:31Z -> sessions running it occupy DB connections or locks, so connection utilisation climbs from 13:55Z -> payment-service requests wait for connections from payment-db-pool -> pool saturates at 14:00:16Z and payments time out -> latency and 5xx rise.

Confidence breakdown: base 0.10; +0.08 corroboration across >=2 independent source types; +0.44 supporting evidence (3 refs, reliability-weighted, capped); -0.45 contradicting evidence (4 refs, capped 0.45); +0.08 proposed cause (13:31) precedes/coincides with first observed anomaly (13:49); -0.06 3 acknowledged evidence gaps; -0.40 critic review adjustment; = 0.00 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-postgres-44883ca5` (moderate): 7x WARN on postgres: 'duration: 18302 ms statement: SELECT report_rollup()' (first 2026-09-02T13:31:28Z, last 2026-09-02T14:23:09Z)
- [OBSERVED EVIDENCE] `met-postgres-db_conn_util_pct-1330-1425` (moderate): postgres db_conn_util_pct: baseline 40.59 -> window mean 53.15 (max 67.91, change 31.0%), onset 2026-09-02T13:55:00Z
- [OBSERVED EVIDENCE] `logpat-payment-service-7d1739af` (moderate): 29x ERROR on payment-service: 'Timeout acquiring connection from pool payment-db-pool after 5000ms (active=50, idle=0, waiting=46)' (first 2026-09-02T14:00:16Z, last 2026-09-02T14:24:16Z)

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-postgres-cpu_pct-1330-1425` (strong): postgres cpu_pct: baseline 34.63 -> window mean 34.97 (max 38.3, change 1.0%), onset none detected
- [OBSERVED EVIDENCE] `met-postgres-p95_latency_ms-1330-1425` (moderate): postgres p95_latency_ms: baseline 11.98 -> window mean 12.06 (max 12.83, change 0.7%), onset none detected
- [OBSERVED EVIDENCE] `met-postgres-disk_io_wait_ms-1330-1425` (moderate): postgres disk_io_wait_ms: baseline 2.0 -> window mean 1.99 (max 2.14, change -0.8%), onset none detected
- [OBSERVED EVIDENCE] `logpat-postgres-44883ca5` (weak): 7x WARN on postgres: 'duration: 18302 ms statement: SELECT report_rollup()' (first 2026-09-02T13:31:28Z, last 2026-09-02T14:23:09Z)

Remaining uncertainties / missing evidence:
- [UNKNOWN] Whether report_rollup sessions use the same database role or pool as payment-service
- [UNKNOWN] pg_stat_locks / blocking-lock data during 13:55-14:05Z
- [UNKNOWN] report_rollup schedule and whether it started at 13:31Z

### 3. H3 - `deployment_regression` in `notification-service` (confidence 0.00, critic: reject)
**INFERENCE:** The notification-service 3.4.1 deployment at 13:54Z caused payment-service latency through an indirect path. Mechanism: notification-service 3.4.1 deployed at 13:54Z -> some side effect propagates to payment-service -> pool exhaustion at 14:00Z.

Confidence breakdown: base 0.10; +0.04 supporting evidence (1 refs, reliability-weighted, capped); -0.45 contradicting evidence (4 refs, capped 0.45); -0.30 proposed cause (13:54) is AFTER the first observed anomaly (13:49); -0.04 2 acknowledged evidence gaps; -0.40 critic review adjustment; = 0.00 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [CONFIRMED FACT] `dep-d757f128` (weak): Deployment of notification-service 3.4.0->3.4.1 at 2026-09-02T13:54:00Z (SUCCEEDED): Update email templates for receipts

Contradicting evidence:
- [CONFIRMED FACT] `topo-payment-service-both-d2` (strong): payment-service depends on ['auth-service', 'postgres', 'redis']; called by ['api-gateway', 'order-service'] (graph topology-v1)
- [CONFIRMED FACT] `topo-order-service-both-d2` (moderate): order-service depends on ['message-queue', 'payment-service', 'postgres', 'user-service']; called by ['api-gateway'] (graph topology-v1)
- [OBSERVED EVIDENCE] `logpat-notification-service-54b86179` (weak): 7x WARN on notification-service: 'SMTP provider throttled 1 message' (first 2026-09-02T13:37:07Z, last 2026-09-02T14:23:53Z)
- [OBSERVED EVIDENCE] `logpat-payment-service-9d1f3d29` (moderate): 9x WARN on payment-service: 'HikariPool-payment - Connection leak detection triggered for connection conn-98, held > 30000 ms by RefundService.processPartialRefund' (first 2026-09-02T13:45:08Z, last 2026-09-02T14:00:16Z)

Remaining uncertainties / missing evidence:
- [UNKNOWN] Any metric or log evidence linking notification-service to payment-service resources
- [UNKNOWN] Shared resource usage by notification-service (DB, redis, queue) after 13:54Z

## Critic Review
- **Verdict:** `APPROVED` (rounds reviewed: 1)
- **Reasoning:** H1 is the best-supported hypothesis: connection-pool exhaustion in payment-service caused by connections held by RefundService.processPartialRefund. Independent checks support it. Payment-service's own db_conn_util_pct rose from a ~35% baseline starting at 13:49Z (52% at 13:50, 78% at 13:55, 96% at 14:00), before any latency or error change. Leak-detection warnings for RefundService holds >30s recur from 13:45Z onward. Pool exhaustion (active=50, idle=0, waiting up to 98) begins at 14:00:16Z, coinciding with the P95 and error-rate step at 14:00:00Z. The gateway 503s start at 14:01Z, downstream of this. Request rate is flat, which fits a holding problem rather than load. The 15-minute lead is explained by gradual pool depletion, not a timing contradiction. H2 is rejected: Postgres CPU, p95 and disk IO are flat, the report_rollup statements are not attributed to the payment pool, and the application logs attribute the held connections to RefundService. H3 is rejected: notification-service is not in payment-service's dependency graph, there is no shared-resource evidence, and the SMTP throttling predates the deployment. Limitation: the trigger that began the RefundService connection hold (the partial-refund path leaking or stalling) is not yet identified; this is a deeper cause and does not block approval of the category and culprit.
- H1: **accept** - Payment-service pool utilisation climbs from 13:49Z, before the 14:00Z onset. Leak warnings attribute held connections to RefundService.processPartialRefund from 13:45Z. Pool saturation errors match exactly at 14:00:16Z, with P95, error and timeout steps at 14:00Z and flat request rate. Gateway 503s are downstream. Postgres-side utilisation is consistent with the same sessions.
- H2: **reject** - Postgres CPU (+1%), p95 latency (+0.7%) and disk IO wait (-0.8%) are flat, which contradicts DB-side saturation or lock contention. The report_rollup statements are not linked to the payment pool. The application attributes the held connections to RefundService, not to report sessions.
- H3: **reject** - No topology path exists between notification-service and payment-service or order-service. There is no metric or log evidence of shared resource impact. SMTP throttling began before the 13:54Z deployment. The timing correlation is weak and the payment-side leak evidence points elsewhere.
- pre-check blocking `correlation_only` on H3: change hypothesis supported only by the change record itself (temporal correlation); no log/metric evidence of the changed behaviour
- pre-check warning `culprit_symptom` on H3: no log/metric evidence cited for culprit notification-service
- pre-check warning `single_source` on H3: all support comes from one source type (deployment)
- alternative: report_rollup contention on Postgres (H2): contradicted by flat DB CPU, latency and IO wait.
- alternative: notification-service side effect (H3): no dependency path and no resource-level evidence.
- alternative: Organic load increase: request rate is flat, so this is contradicted.

## Probable Root Cause
ROOT CAUSE IDENTIFIED (critic-approved; still an INFERENCE from evidence): db_connection_pool_exhaustion in payment-service - Connections leaked by RefundService.processPartialRefund exhaust payment-db-pool, so checkout payment calls queue, time out and return 5xx.

## Corrective Actions
- Immediately release the connections held by RefundService.processPartialRefund (for example, recycle the payment-service instances or the affected pool connections) to restore free capacity in payment-db-pool. Confirm recovery by checking that active connections fall below 50 and waiters reach zero.
- If leaks recur, temporarily disable or throttle the partial-refund path so it stops consuming payment-db-pool connections, while keeping checkout payments running.
- Confirm which sessions hold the connections by querying pg_stat_activity during the incident window. The critic noted that exclusive attribution to RefundService was inferred from application logs and not verified (evidence gap to close).
- Watch for recovery in payment-service P95, error rate, and timeout rate, and for the api-gateway 503 rate, since these lagged the pool exhaustion.

## Preventive Actions
- Find and fix the code path in RefundService.processPartialRefund that leaves connections checked out or stalls while holding them. Make sure every connection is released in a finally block or try-with-resources, and that no external call is made while a connection is held.
- Set a maximum connection hold time and a statement or transaction timeout on the payment pool so a single caller cannot hold connections indefinitely. Consider separate pools for refund and checkout traffic so refunds cannot starve payments.
- Add regression tests or load tests for the partial-refund flow that check connections are returned after success, failure, and timeout.
- Review the report_rollup long-running statements (18 seconds in logs) separately as a performance hygiene item, even though they were not the cause of this incident.

## Monitoring Recommendations
- Alert when payment-db-pool active connections stay at or near the max (for example, above 80% for 2 minutes) or when waiting threads are above zero for more than 1 minute.
- Alert on HikariPool connection leak-detection warnings (payment-service logs), and page on any hold longer than 30 seconds attributed to RefundService.
- Track payment-service db_conn_util_pct per service and alert on a sustained rise above the roughly 35-40% baseline, since this rise preceded the latency change by about 15 minutes.
- Keep alerts on payment-service P95 latency (baseline about 150 ms), error rate (baseline about 1%), timeout rate, and api-gateway upstream 503 counts, and add a dashboard that correlates these with pool metrics.
- Log the source service or operation name on connection acquisition and timeout events, so pool owners can be identified without manual database queries.

## Evidence Gaps
- none recorded

## Limitations
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: critic verdict APPROVED

## Final Status
`ROOT_CAUSE_IDENTIFIED`

The incident is best explained by connection pool exhaustion in payment-service, caused by connections held by RefundService.processPartialRefund. The mechanism is supported by application logs, metrics, and the timing of the pool-saturation event relative to the latency and error onset. The rejected alternatives (Postgres report_rollup contention and the notification-service deployment) are contradicted by the available evidence. Two gaps remain: the trigger that began the connection hold around 13:45Z is unexplained, and connection ownership has not been verified in pg_stat_activity. Mitigation should focus on releasing the held connections and preventing recurrence through leak fixes, hold-time limits, and pool isolation for refund traffic.

## Execution Statistics
```json
{
  "rounds": 1,
  "tool_calls": 18,
  "tool_failures": 0,
  "tool_retries": 0,
  "partial_results": 0,
  "agent_failures": 0,
  "agent_retries": 0,
  "invalid_llm_outputs": 1,
  "messages_exchanged": 20,
  "evidence_records": 108,
  "duration_s": 72.78,
  "tokens": {
    "input_tokens": 46,
    "output_tokens": 23060,
    "cache_read_tokens": 30647,
    "cache_write_tokens": 65226,
    "llm_calls": 15,
    "cost_usd": 0.01999432
  },
  "tokens_by_agent": {
    "orchestrator": {
      "input_tokens": 6,
      "output_tokens": 1002,
      "cache_read_tokens": 1333,
      "cache_write_tokens": 2202,
      "llm_calls": 2,
      "cost_usd": 0.0007901799999999999
    },
    "dependency": {
      "input_tokens": 12,
      "output_tokens": 2894,
      "cache_read_tokens": 6277,
      "cache_write_tokens": 8164,
      "llm_calls": 4,
      "cost_usd": 0.00253147
    },
    "observability": {
      "input_tokens": 14,
      "output_tokens": 10739,
      "cache_read_tokens": 14743,
      "cache_write_tokens": 23982,
      "llm_calls": 5,
      "cost_usd": 0.008516079999999999
    },
    "reasoning": {
      "input_tokens": 4,
      "output_tokens": 3935,
      "cache_read_tokens": 0,
      "cache_write_tokens": 12817,
      "llm_calls": 1,
      "cost_usd": 0.003570025
    },
    "critic": {
      "input_tokens": 6,
      "output_tokens": 2324,
      "cache_read_tokens": 8294,
      "cache_write_tokens": 14273,
      "llm_calls": 2,
      "cost_usd": 0.003029665
    },
    "reporting": {
      "input_tokens": 4,
      "output_tokens": 2166,
      "cache_read_tokens": 0,
      "cache_write_tokens": 3788,
      "llm_calls": 1,
      "cost_usd": 0.0015569000000000002
    }
  }
}
```
