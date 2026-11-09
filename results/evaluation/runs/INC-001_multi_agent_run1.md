# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-001
- **Title:** Payment API latency spike
- **Severity:** SEV2
- **Affected services:** api-gateway, payment-service
- **Start time:** 2026-09-02T14:00:00+00:00
- **Investigation ID:** inv-d43141e027 (multi_agent)
- **Final status:** `PROBABLE_ROOT_CAUSE`

## Executive Summary
INC-001 (SEV2): Customers saw checkout take 3-5 seconds and some payments fail with 5xx starting around 14:00Z on 2026-09-02, affecting api-gateway and payment-service. Final status is PROBABLE_ROOT_CAUSE, not a confirmed root cause. The most probable explanation is connection pool exhaustion in payment-service (payment-db-pool, 50 connections). Pool utilisation rose from about 35% to a window mean of 66.7% (max 100%) from 13:49Z (met-payment-service-db_conn_util_pct-1340-1405). Acquisition timeouts with active=50, idle=0 began at 14:00:16Z (logpat-payment-service-7d1739af), matching the p95 latency step (baseline 150 ms to window mean 593 ms, max 2865 ms) and the timeout rate jump from 0.1 to 3.2 per window (met-payment-service-timeout_rate-1340-1405). API gateway 503s followed from 14:01:09Z (logpat-api-gateway-2be6bd23). Request rate was flat (302 to 303 req/s), so the change is not driven by traffic volume. Refund connection leaks were logged from 13:45:08Z (logpat-payment-service-9d1f3d29), but the 9 flagged RefundService connections alone cannot explain the saturation. The leading hypothesis (H2, confidence 0.78) is that unattributed connection holders in payment-service, possibly on non-refund paths or with holds below the 30s leak threshold, account for most of the pool load. Postgres was ruled out as the initiator (H3 rejected).

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
| 2026-09-02T13:49:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service db_conn_util_pct: baseline 34.95 -> window mean 72.1 (max 100.0, change 106.3%), onset 2026-09-02T13:49:00Z | met-payment-service-db_conn_util_pct-1330-1425 |
| 2026-09-02T13:49:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service db_conn_util_pct: baseline 34.95 -> window mean 59.06 (max 100.0, change 69.0%), onset 2026-09-02T13:49:00Z | met-payment-service-db_conn_util_pct-1340-1400 |
| 2026-09-02T13:49:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service db_conn_util_pct: baseline 34.95 -> window mean 66.68 (max 100.0, change 90.8%), onset 2026-09-02T13:49:00Z | met-payment-service-db_conn_util_pct-1340-1405 |
| 2026-09-02T13:54:00Z | CONFIRMED FACT | Deployment of notification-service 3.4.0->3.4.1 at 2026-09-02T13:54:00Z (SUCCEEDED): Update email templates for receipts | dep-d757f128 |
| 2026-09-02T13:54:42Z | OBSERVED EVIDENCE | First log: 4x WARN on user-service: 'Deprecated API /v1/users/legacy called by client web-86' (first 2026-09-02T13:54:42Z, last 2026-09-02T14:17:53Z) | logpat-user-service-742b555e |
| 2026-09-02T14:00:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service p95_latency_ms: baseline 150.24 -> window mean 1315.14 (max 3018.96, change 775.3%), onset 2026-09-02T14:00:00Z | met-payment-service-p95_latency_ms-1330-1425 |
| 2026-09-02T14:00:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service p99_latency_ms: baseline 302.14 -> window mean 2429.49 (max 5545.92, change 704.1%), onset 2026-09-02T14:00:00Z | met-payment-service-p99_latency_ms-1330-1425 |
| 2026-09-02T14:00:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service error_rate: baseline 0.8 -> window mean 9.93 (max 23.67, change 1139.4%), onset 2026-09-02T14:00:00Z | met-payment-service-error_rate-1330-1425 |
| 2026-09-02T14:00:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service timeout_rate: baseline 0.1 -> window mean 8.04 (max 19.09, change 7957.0%), onset 2026-09-02T14:00:00Z | met-payment-service-timeout_rate-1330-1425 |
| 2026-09-02T14:00:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service p95_latency_ms: baseline 150.24 -> window mean 593.44 (max 2865.11, change 295.0%), onset 2026-09-02T14:00:00Z | met-payment-service-p95_latency_ms-1340-1405 |
| 2026-09-02T14:00:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service timeout_rate: baseline 0.1 -> window mean 3.2 (max 19.0, change 3111.6%), onset 2026-09-02T14:00:00Z | met-payment-service-timeout_rate-1340-1405 |
| 2026-09-02T14:00:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service error_rate: baseline 0.8 -> window mean 4.39 (max 21.36, change 446.9%), onset 2026-09-02T14:00:00Z | met-payment-service-error_rate-1340-1405 |
| 2026-09-02T14:00:00Z | CONFIRMED FACT | Reported symptom start |  |
| 2026-09-02T14:00:16Z | OBSERVED EVIDENCE | First log: 29x ERROR on payment-service: 'Timeout acquiring connection from pool payment-db-pool after 5000ms (active=50, idle=0, waiting=46)' (first 2026-09-02T14:00:16Z, last 2026-09-02T14:24:16Z) | logpat-payment-service-7d1739af |
| 2026-09-02T14:01:00Z | OBSERVED EVIDENCE | Anomaly onset: api-gateway p95_latency_ms: baseline 119.71 -> window mean 868.12 (max 2004.12, change 625.2%), onset 2026-09-02T14:01:00Z | met-api-gateway-p95_latency_ms-1330-1425 |
| 2026-09-02T14:01:00Z | OBSERVED EVIDENCE | Anomaly onset: api-gateway error_rate: baseline 0.5 -> window mean 4.05 (max 9.88, change 710.4%), onset 2026-09-02T14:01:00Z | met-api-gateway-error_rate-1330-1425 |
| 2026-09-02T14:01:00Z | OBSERVED EVIDENCE | Anomaly onset: order-service p95_latency_ms: baseline 201.27 -> window mean 408.37 (max 746.73, change 102.9%), onset 2026-09-02T14:01:00Z | met-order-service-p95_latency_ms-1330-1425 |
| 2026-09-02T14:01:09Z | OBSERVED EVIDENCE | First log: 11x ERROR on api-gateway: 'Upstream payment-service responded 503 for POST /v1/payments (latency 50ms)' (first 2026-09-02T14:01:09Z, last 2026-09-02T14:23:05Z) | logpat-api-gateway-2be6bd23 |
| 2026-09-02T14:06:00Z | CONFIRMED FACT | Incident reported |  |

## Observed Symptoms
- **OBSERVED EVIDENCE:** payment-service p95_latency_ms: baseline 150.24 -> window mean 1315.14 (max 3018.96, change 775.3%), onset 2026-09-02T14:00:00Z (met-payment-service-p95_latency_ms-1330-1425)
- **OBSERVED EVIDENCE:** payment-service p99_latency_ms: baseline 302.14 -> window mean 2429.49 (max 5545.92, change 704.1%), onset 2026-09-02T14:00:00Z (met-payment-service-p99_latency_ms-1330-1425)
- **OBSERVED EVIDENCE:** payment-service error_rate: baseline 0.8 -> window mean 9.93 (max 23.67, change 1139.4%), onset 2026-09-02T14:00:00Z (met-payment-service-error_rate-1330-1425)
- **OBSERVED EVIDENCE:** payment-service timeout_rate: baseline 0.1 -> window mean 8.04 (max 19.09, change 7957.0%), onset 2026-09-02T14:00:00Z (met-payment-service-timeout_rate-1330-1425)
- **OBSERVED EVIDENCE:** payment-service db_conn_util_pct: baseline 34.95 -> window mean 72.1 (max 100.0, change 106.3%), onset 2026-09-02T13:49:00Z (met-payment-service-db_conn_util_pct-1330-1425)
- **OBSERVED EVIDENCE:** api-gateway p95_latency_ms: baseline 119.71 -> window mean 868.12 (max 2004.12, change 625.2%), onset 2026-09-02T14:01:00Z (met-api-gateway-p95_latency_ms-1330-1425)
- **OBSERVED EVIDENCE:** api-gateway error_rate: baseline 0.5 -> window mean 4.05 (max 9.88, change 710.4%), onset 2026-09-02T14:01:00Z (met-api-gateway-error_rate-1330-1425)
- **OBSERVED EVIDENCE:** order-service p95_latency_ms: baseline 201.27 -> window mean 408.37 (max 746.73, change 102.9%), onset 2026-09-02T14:01:00Z (met-order-service-p95_latency_ms-1330-1425)
- **OBSERVED EVIDENCE:** payment-service db_conn_util_pct: baseline 34.95 -> window mean 59.06 (max 100.0, change 69.0%), onset 2026-09-02T13:49:00Z (met-payment-service-db_conn_util_pct-1340-1400)
- **OBSERVED EVIDENCE:** payment-service db_conn_util_pct: baseline 34.95 -> window mean 66.68 (max 100.0, change 90.8%), onset 2026-09-02T13:49:00Z (met-payment-service-db_conn_util_pct-1340-1405)
- **OBSERVED EVIDENCE:** payment-service p95_latency_ms: baseline 150.24 -> window mean 593.44 (max 2865.11, change 295.0%), onset 2026-09-02T14:00:00Z (met-payment-service-p95_latency_ms-1340-1405)
- **OBSERVED EVIDENCE:** payment-service timeout_rate: baseline 0.1 -> window mean 3.2 (max 19.0, change 3111.6%), onset 2026-09-02T14:00:00Z (met-payment-service-timeout_rate-1340-1405)
- **OBSERVED EVIDENCE:** payment-service error_rate: baseline 0.8 -> window mean 4.39 (max 21.36, change 446.9%), onset 2026-09-02T14:00:00Z (met-payment-service-error_rate-1340-1405)
- **OBSERVED EVIDENCE:** [dependency] Only deployment in 12:00-14:10Z window: notification-service 3.4.0 -> 3.4.1 (SUCCEEDED, ci-pipeline, 'Update email templates for receipts'). No payment-path service (payment-service, auth-service, api-gateway, order-service, postgres, redis) had a deployment in this window. (dep-d757f128)
- **OBSERVED EVIDENCE:** [dependency] Dependency graph (topology-v1): payment-service upstream = auth-service, postgres, redis (auth-service also calls postgres and redis); downstream = api-gateway, order-service. No topology changes recorded. notification-service is not in payment-service's dependency graph within depth 2. (topo-payment-service-both-d2)
- **OBSERVED EVIDENCE:** [observability] payment-service p95 latency rose from baseline mean 150ms to window mean 1315ms (max 3019ms); onset 14:00Z, ~2.7-2.9s from 14:05Z. p99 rose from 302ms to 2429ms mean (max 5546ms), same onset. (met-payment-service-p95_latency_ms-1330-1425, met-payment-service-p99_latency_ms-1330-1425)
- **OBSERVED EVIDENCE:** [observability] payment-service error_rate rose from baseline 0.8% to window mean 9.9% (max 23.7%), ~20-22% from 14:05Z. timeout_rate rose from 0.1% to 8.0% mean (max 19.1%). Both onset 14:00Z. (met-payment-service-error_rate-1330-1425, met-payment-service-timeout_rate-1330-1425)
- **OBSERVED EVIDENCE:** [observability] payment-service db_conn_util_pct rose from baseline 35% to 100% (window max); onset detected 13:49Z, 52% at 13:50, 78% at 13:55, ~96% at 14:00. (met-payment-service-db_conn_util_pct-1330-1425)
- **OBSERVED EVIDENCE:** [observability] ERROR logs: 'Timeout acquiring connection from pool payment-db-pool after 5000ms (active=50, idle=0, waiting=N)', 29 occurrences from 14:00:16Z to 14:24:16Z, waiting queue 11-98. (logpat-payment-service-7d1739af, log-853bbeab, log-55cc357e, log-086e8659)
- **OBSERVED EVIDENCE:** [observability] WARN logs: HikariPool-payment connection leak detection triggered (held >30000ms) by RefundService.processPartialRefund, 9 occurrences 13:45:08Z to 14:00:16Z. (logpat-payment-service-9d1f3d29)
- **OBSERVED EVIDENCE:** [observability] payment-service request_rate is flat (baseline 302 rps, window 302 rps, -0.2%); no traffic surge in the window. (met-payment-service-request_rate-1330-1425)
- **OBSERVED EVIDENCE:** [observability] api-gateway p95 rose from baseline 120ms to window mean 868ms (max 2004ms); onset 14:01Z, ~1.85-1.9s from 14:05Z. error_rate rose from 0.5% to 4.1% mean (max 9.9%), ~8-9% from 14:05Z. (met-api-gateway-p95_latency_ms-1330-1425, met-api-gateway-error_rate-1330-1425)
- **OBSERVED EVIDENCE:** [observability] ERROR logs: 'Upstream payment-service responded 503 for POST /v1/payments' (11 occurrences, 14:01:09Z to 14:23:05Z) with low upstream latency (22-52ms). (logpat-api-gateway-2be6bd23, log-143e39ed, log-2bc4576c, log-4a95719e)
- **OBSERVED EVIDENCE:** [observability] api-gateway p99 latency flat (baseline 249ms, window 250ms), timeout_rate flat (~0.1%), request_rate -1.9%. (met-api-gateway-p99_latency_ms-1330-1425, met-api-gateway-timeout_rate-1330-1425, met-api-gateway-request_rate-1330-1425)
- **OBSERVED EVIDENCE:** [observability] order-service p95 rose from 201ms to 408ms mean (max 747ms) with onset 14:01Z, while its p99, error rate, timeout rate and request rate stayed at baseline. (met-order-service-p95_latency_ms-1330-1425, met-order-service-p99_latency_ms-1330-1425, met-order-service-error_rate-1330-1425)
- **ASSUMPTION:** [critic: unsupported assumption] Leaked refund connections are never returned to the pool (not directly shown; the leak detector may only log once per connection). 
- **ASSUMPTION:** [critic: unsupported assumption] Leak detector logging is complete (it may be rate-limited or first-flag-only), so the true number of long-held connections is unknown. 
- **ASSUMPTION:** [critic: unsupported assumption] The api-gateway 503s are caused by payment-service pool failure rather than another upstream issue (only the 503 log and its timing were checked). 

## Investigation Performed
- Round 1 | observability | completed | attempts 1 | 5 tool calls | Determine when and where latency and 5xx errors began in the payment path, from 2026-09-02T13:30Z onward.
- Round 1 | observability | completed | attempts 1 | 6 tool calls | Check datastore and cache health used by payment-service and auth-service for saturation or contention starting near 14:00Z.
- Round 1 | dependency | completed | attempts 1 | 3 tool calls | Identify deployments, configuration changes, or feature flag changes in the payment path in the window 2026-09-02T12:00Z to 14:10Z.
- Round 1 | reasoning | completed | attempts 1 | 0 tool calls | Develop and rank competing hypotheses
- Round 1 | critic | completed | attempts 1 | 2 tool calls | Independently review hypotheses
- Round 2 | observability | completed | attempts 1 | 6 tool calls | FOLLOW-UP requested by critic: Break down payment-service db connection usage by holder for 13:40-14:05Z: connections held by RefundService.processPartialRefund
- Round 2 | observability | completed | attempts 1 | 3 tool calls | FOLLOW-UP requested by critic: Pull all postgres WARN/ERROR logs 13:30-14:05Z for lock waits, blocked sessions or cancelled statements, and check whether any pa
- Round 2 | observability | completed | attempts 1 | 2 tool calls | FOLLOW-UP requested by critic: Check payment-service refund-path volume and latency: any logs or metrics for RefundService calls 13:40-14:00Z versus baseline, t
- Round 2 | reasoning | completed | attempts 1 | 0 tool calls | Develop and rank competing hypotheses
- Round 2 | critic | completed | attempts 1 | 3 tool calls | Independently review hypotheses
- Round 3 | observability | completed | attempts 1 | 3 tool calls | FOLLOW-UP requested by critic: Search payment-service logs 13:30-14:05Z for all HikariPool-payment connection-leak WARNs and any other pool/connection holder me
- Round 3 | reasoning | completed | attempts 1 | 0 tool calls | Develop and rank competing hypotheses
- Round 3 | critic | completed | attempts 1 | 3 tool calls | Independently review hypotheses
- Round 3 | reporting | completed | attempts 1 | 0 tool calls | Write final report

## Root-Cause Hypotheses (ranked by evidence strength)
### 1. H2 - `db_connection_pool_exhaustion` in `payment-service` (confidence 0.78, critic: needs_evidence)
**INFERENCE:** Pool saturation is driven by unattributed connection holders in payment-service (non-refund paths or refund holds shorter than the 30s leak threshold, or undercounted leaks), so the 9 flagged refund connections are only a visible part of the load on the pool. Mechanism: Some code path(s) acquire connections and hold them for durations below or outside the leak detector's 30s / once-per-connection logging -> ~41 of 50 active connections are held by unlogged holders -> pool drains to active=50 with idle=0 -> queueing and 5000ms acquisition timeouts from 14:00:16Z -> p95/timeout/error step and 503s at api-gateway.

Confidence breakdown: base 0.10; +0.08 corroboration across >=2 independent source types; +0.76 supporting evidence (4 refs, reliability-weighted, capped); -0.05 contradicting evidence (1 refs, capped 0.45); +0.08 proposed cause (13:49) precedes/coincides with first observed anomaly (13:49); -0.06 3 acknowledged evidence gaps; -0.05 critic review adjustment; = 0.78 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [OBSERVED EVIDENCE] `met-payment-service-db_conn_util_pct-1340-1405` (strong): payment-service db_conn_util_pct: baseline 34.95 -> window mean 66.68 (max 100.0, change 90.8%), onset 2026-09-02T13:49:00Z
- [OBSERVED EVIDENCE] `logpat-payment-service-7d1739af` (strong): 29x ERROR on payment-service: 'Timeout acquiring connection from pool payment-db-pool after 5000ms (active=50, idle=0, waiting=46)' (first 2026-09-02T14:00:16Z, last 2026-09-02T14:24:16Z)
- [OBSERVED EVIDENCE] `logpat-payment-service-9d1f3d29` (moderate): 9x WARN on payment-service: 'HikariPool-payment - Connection leak detection triggered for connection conn-98, held > 30000 ms by RefundService.processPartialRefund' (first 2026-09-02T13:45:08Z, last 2026-09-02T14:00:16Z)
- [OBSERVED EVIDENCE] `met-payment-service-timeout_rate-1340-1405` (moderate): payment-service timeout_rate: baseline 0.1 -> window mean 3.2 (max 19.0, change 3111.6%), onset 2026-09-02T14:00:00Z

Contradicting evidence:
- [OBSERVED EVIDENCE] `logpat-payment-service-9d1f3d29` (weak): 9x WARN on payment-service: 'HikariPool-payment - Connection leak detection triggered for connection conn-98, held > 30000 ms by RefundService.processPartialRefund' (first 2026-09-02T13:45:08Z, last 2026-09-02T14:00:16Z)

Remaining uncertainties / missing evidence:
- [UNKNOWN] Any log, metric or trace naming a non-refund holder of payment-db-pool connections
- [UNKNOWN] Connection hold-time distribution for holds under 30s
- [UNKNOWN] Confirmation of leak-detector rate limiting or once-per-connection behaviour

### 2. H1 - `db_connection_pool_exhaustion` in `payment-service` (confidence 0.63, critic: needs_evidence)
**INFERENCE:** RefundService.processPartialRefund holds payment-db-pool connections for more than 30s, reducing effective capacity until the 50-connection pool saturates; payment requests then queue and time out at 5000ms, surfacing as 5xx at api-gateway. Mechanism: RefundService.processPartialRefund leaks or long-holds connections (9 distinct conn IDs flagged >30s, 13:45:08Z to 14:00:16Z) -> available pool capacity falls, db_conn_util climbs from 13:49Z (35% -> 96% by 14:00) -> at 14:00:16Z active=50, idle=0 with waiting queue 11-76 -> acquisition timeouts -> payment p95/timeout/error step at 14:00Z -> api-gateway receives 503s from payment-service at 14:01Z.

Confidence breakdown: base 0.10; +0.08 corroboration across >=2 independent source types; +0.78 supporting evidence (7 refs, reliability-weighted, capped); -0.20 contradicting evidence (2 refs, capped 0.45); +0.08 proposed cause (13:45) precedes/coincides with first observed anomaly (13:49); -0.08 4 acknowledged evidence gaps; -0.05 critic review adjustment; = 0.63 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-payment-service-9d1f3d29` (strong): 9x WARN on payment-service: 'HikariPool-payment - Connection leak detection triggered for connection conn-98, held > 30000 ms by RefundService.processPartialRefund' (first 2026-09-02T13:45:08Z, last 2026-09-02T14:00:16Z)
- [OBSERVED EVIDENCE] `met-payment-service-db_conn_util_pct-1340-1405` (strong): payment-service db_conn_util_pct: baseline 34.95 -> window mean 66.68 (max 100.0, change 90.8%), onset 2026-09-02T13:49:00Z
- [OBSERVED EVIDENCE] `logpat-payment-service-7d1739af` (strong): 29x ERROR on payment-service: 'Timeout acquiring connection from pool payment-db-pool after 5000ms (active=50, idle=0, waiting=46)' (first 2026-09-02T14:00:16Z, last 2026-09-02T14:24:16Z)
- [OBSERVED EVIDENCE] `met-payment-service-p95_latency_ms-1340-1405` (strong): payment-service p95_latency_ms: baseline 150.24 -> window mean 593.44 (max 2865.11, change 295.0%), onset 2026-09-02T14:00:00Z
- [OBSERVED EVIDENCE] `met-payment-service-timeout_rate-1340-1405` (strong): payment-service timeout_rate: baseline 0.1 -> window mean 3.2 (max 19.0, change 3111.6%), onset 2026-09-02T14:00:00Z
- [OBSERVED EVIDENCE] `logpat-api-gateway-2be6bd23` (moderate): 11x ERROR on api-gateway: 'Upstream payment-service responded 503 for POST /v1/payments (latency 50ms)' (first 2026-09-02T14:01:09Z, last 2026-09-02T14:23:05Z)
- [OBSERVED EVIDENCE] `met-payment-service-request_rate-1340-1400` (moderate): payment-service request_rate: baseline 302.3 -> window mean 303.18 (max 330.9, change 0.3%), onset none detected

Contradicting evidence:
- [OBSERVED EVIDENCE] `logpat-payment-service-9d1f3d29` (moderate): 9x WARN on payment-service: 'HikariPool-payment - Connection leak detection triggered for connection conn-98, held > 30000 ms by RefundService.processPartialRefund' (first 2026-09-02T13:45:08Z, last 2026-09-02T14:00:16Z)
- [OBSERVED EVIDENCE] `met-payment-service-request_rate-1340-1400` (weak): payment-service request_rate: baseline 302.3 -> window mean 303.18 (max 330.9, change 0.3%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Per-holder pool snapshot or pg_stat_activity for 13:40-14:05Z to count active holders by code path
- [UNKNOWN] RefundService request/call counter or INFO logs to establish refund volume baseline vs incident
- [UNKNOWN] Whether leak detector is rate-limited or logs only the first flag per connection
- [UNKNOWN] Traces showing time spent waiting for pool connections by endpoint

### 3. H3 - `upstream_dependency_degradation` in `postgres` (confidence 0.00, critic: reject)
**INFERENCE:** Long-running report_rollup() statements on postgres hold locks or connections that payment-service depends on, starving payment-db-pool. Mechanism: report_rollup() runs 13-19s from 13:31Z -> holds locks or DB sessions -> payment-service queries wait -> connections held longer -> pool saturates at 14:00Z.

Confidence breakdown: base 0.10; +0.08 corroboration across >=2 independent source types; +0.24 supporting evidence (2 refs, reliability-weighted, capped); -0.45 contradicting evidence (4 refs, capped 0.45); +0.08 proposed cause (13:31) precedes/coincides with first observed anomaly (13:49); -0.04 2 acknowledged evidence gaps; -0.40 critic review adjustment; = 0.00 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-postgres-44883ca5` (moderate): 7x WARN on postgres: 'duration: 18302 ms statement: SELECT report_rollup()' (first 2026-09-02T13:31:28Z, last 2026-09-02T14:23:09Z)
- [OBSERVED EVIDENCE] `met-payment-service-db_conn_util_pct-1340-1405` (weak): payment-service db_conn_util_pct: baseline 34.95 -> window mean 66.68 (max 100.0, change 90.8%), onset 2026-09-02T13:49:00Z

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-postgres-cpu_pct-1330-1425` (strong): postgres cpu_pct: baseline 34.63 -> window mean 34.97 (max 38.3, change 1.0%), onset none detected
- [OBSERVED EVIDENCE] `met-postgres-p95_latency_ms-1330-1425` (strong): postgres p95_latency_ms: baseline 11.98 -> window mean 12.06 (max 12.83, change 0.7%), onset none detected
- [OBSERVED EVIDENCE] `met-postgres-db_conn_util_pct-1330-1425` (moderate): postgres db_conn_util_pct: baseline 40.59 -> window mean 53.15 (max 67.91, change 31.0%), onset 2026-09-02T13:55:00Z
- [OBSERVED EVIDENCE] `logpat-postgres-44883ca5` (moderate): 7x WARN on postgres: 'duration: 18302 ms statement: SELECT report_rollup()' (first 2026-09-02T13:31:28Z, last 2026-09-02T14:23:09Z)

Remaining uncertainties / missing evidence:
- [UNKNOWN] pg_stat_activity and pg_locks snapshots during 13:30-14:05Z
- [UNKNOWN] Which client connections the slow rollup sessions belong to

## Critic Review
- **Verdict:** `NEEDS_MORE_EVIDENCE` (rounds reviewed: 3)
- **Reasoning:** The payment-db-pool saturation on payment-service is the right culprit category, and the timeline holds: refund leak WARNs start at 13:45:08Z, pool utilisation rises from 13:49Z, and acquisition timeouts with active=50, idle=0 begin at 14:00:16Z, which matches the p95/timeout step. However, the 9 flagged RefundService connections cannot by themselves explain saturation. Baseline utilisation is about 35% (~17 connections), and 9 leaked connections would leave ~26 busy, well short of the 48+ needed for 96%. Something like 20 additional holders is unaccounted for, so H1 is at best a partial explanation and H2 is the only hypothesis that addresses that gap, though it currently names no path. H3 is rejected: Postgres CPU and p95 are flat, and Postgres connection use rises only after the payment-pool onset, so it cannot be the initiator. Notification-service deployment at 13:54Z is not a payment-pool holder and no payment-service config changes occurred in the window.
- H1: **needs_evidence** - Timing is consistent and the leak WARNs are specific, but 9 leaked connections (~18% of pool) do not account for the utilisation rise to 96%. Must show that refund holders make up a large share of the 50 active connections, e.g. via a pool snapshot or refund-path connection counts. Also, leak detection logs once per connection, so the true leaked count may be higher.
- H2: **needs_evidence** - The quantitative gap that H1 leaves is real, but no non-refund holder is named by any log or metric. It needs attribution, not inference from the utilisation curve alone.
- H3: **reject** - Postgres CPU (34.6 -> 35.0) and p95 (12 ms flat) show no DB-side saturation. The rollup slow-statement WARNs carry no lock-wait or blocking entries, and Postgres connection use rises at 13:55Z, after the payment-pool onset at 13:49Z. The rollups are a temporal coincidence.
- alternative: Unlogged short-hold or non-refund connection holders in payment-service growing gradually from about 13:40Z (H2), with refund leaks as a contributing factor.
- alternative: Increased per-request connection hold time from some non-refund path (e.g., a slowdown inside payment-service code), which would show up as higher utilisation without extra leaks.
- alternative: Shift in traffic mix toward refund-heavy requests at constant aggregate request rate (not excluded; refund volume baseline is unknown).

## Probable Root Cause
MOST PROBABLE EXPLANATION (INFERENCE, not confirmed): db_connection_pool_exhaustion in payment-service - Pool saturation is driven by unattributed connection holders in payment-service (non-refund paths or refund holds shorter than the 30s leak threshold, or undercounted leaks), so the 9 flagged refund connections are only a visible part of the load on the pool.

## Corrective Actions
- Mitigate pool exhaustion now: restart or drain affected payment-service instances to release held connections, and verify active/idle recovery on payment-db-pool.
- Temporarily cut refund traffic or disable the processPartialRefund path to reduce load from the 9 flagged long-held connections (logpat-payment-service-9d1f3d29).
- Increase payment-db-pool max size or lower acquisition wait only as a short-term buffer, while noting it may shift load onto Postgres.
- Shed or rate-limit non-critical payment-service traffic at api-gateway to stop 5xx cascade until the pool recovers.

## Preventive Actions
- Identify the unattributed connection holders: add per-call-site connection acquisition and hold-time instrumentation for payment-service, covering non-refund paths and holds under 30s, since the current leak detector only flags holds over 30s.
- Fix the refund path so partial-refund connections are released promptly, and verify the leak detector logs every long-held connection, not only the first per connection, as the critic noted logging completeness is unknown.
- Review and set pool sizing and timeouts against measured concurrency (about 300 req/s), and add back-pressure so queueing does not reach the 5000 ms timeout.
- Confirm the api-gateway 503s are caused by payment-service pool failure and not another upstream issue before closing the investigation.

## Monitoring Recommendations
- Alert when payment-service db_conn_util_pct exceeds 80% for 2 minutes, and when active connections reach the pool max with idle=0.
- Alert on the 'Timeout acquiring connection from pool payment-db-pool' error count greater than zero within a 5-minute window, and on p95 latency above 400 ms.
- Track refund connection leak WARN counts (HikariPool-payment) and alert on any new occurrence, with the holder method name in the log.
- Dashboard payment-service timeout_rate and api-gateway 503 rate for POST /v1/payments side by side to confirm causality during recovery.
- Monitor refund volume separately from total request rate to test whether a traffic mix shift contributed.
- Keep Postgres CPU, p95 and connection utilisation under observation to confirm they remain flat and are not a secondary effect.

## Evidence Gaps
- none recorded

## Limitations
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: critic verdict NEEDS_MORE_EVIDENCE; maximum investigation rounds (3) reached

## Final Status
`PROBABLE_ROOT_CAUSE`

The incident is most probably caused by saturation of the payment-service payment-db-pool, driven by connection holders that are not yet attributed. The 9 flagged refund leaks are a visible but partial contributor, since they cannot account for the scale of pool use. Postgres is not the initiator. This remains a probable root cause (confidence 0.78), and the unattributed holders must be identified and confirmed before the root cause can be considered established. Mitigation and instrumentation should proceed immediately.

## Execution Statistics
```json
{
  "rounds": 3,
  "tool_calls": 38,
  "tool_failures": 0,
  "tool_retries": 0,
  "partial_results": 0,
  "agent_failures": 0,
  "agent_retries": 0,
  "invalid_llm_outputs": 3,
  "messages_exchanged": 47,
  "evidence_records": 107,
  "duration_s": 167.7,
  "tokens": {
    "input_tokens": 90,
    "output_tokens": 55569,
    "cache_read_tokens": 89838,
    "cache_write_tokens": 165073,
    "llm_calls": 30,
    "cost_usd": 0.04932600500000001
  },
  "tokens_by_agent": {
    "orchestrator": {
      "input_tokens": 6,
      "output_tokens": 925,
      "cache_read_tokens": 3535,
      "cache_write_tokens": 0,
      "llm_calls": 2,
      "cost_usd": 0.00049845
    },
    "dependency": {
      "input_tokens": 6,
      "output_tokens": 1390,
      "cache_read_tokens": 3172,
      "cache_write_tokens": 3973,
      "llm_calls": 2,
      "cost_usd": 0.0012239450000000002
    },
    "observability": {
      "input_tokens": 44,
      "output_tokens": 31175,
      "cache_read_tokens": 59670,
      "cache_write_tokens": 68656,
      "llm_calls": 16,
      "cost_usd": 0.024770599999999997
    },
    "reasoning": {
      "input_tokens": 12,
      "output_tokens": 12086,
      "cache_read_tokens": 0,
      "cache_write_tokens": 55546,
      "llm_calls": 3,
      "cost_usd": 0.01298745
    },
    "critic": {
      "input_tokens": 18,
      "output_tokens": 8392,
      "cache_read_tokens": 23461,
      "cache_write_tokens": 33203,
      "llm_calls": 6,
      "cost_usd": 0.008582785
    },
    "reporting": {
      "input_tokens": 4,
      "output_tokens": 1601,
      "cache_read_tokens": 0,
      "cache_write_tokens": 3695,
      "llm_calls": 1,
      "cost_usd": 0.001262775
    }
  }
}
```
