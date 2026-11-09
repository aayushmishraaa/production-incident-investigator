# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-004
- **Title:** Order API timeouts overnight
- **Severity:** SEV2
- **Affected services:** order-service
- **Start time:** 2026-09-11T02:15:00+00:00
- **Investigation ID:** inv-923ceeea9b (multi_agent)
- **Final status:** `ROOT_CAUSE_IDENTIFIED`

## Executive Summary
INC-004 (SEV2, order-service): elevated order creation latency and intermittent timeouts on POST /v1/orders beginning around 02:15Z on 2026-09-11. Final status is ROOT_CAUSE_IDENTIFIED. The leading hypothesis (H1, confidence 0.83) is that JVM stop-the-world GC pressure in order-service exhausted its order-worker threads, causing requests to exceed the 5000ms deadline. The mechanism: 14 G1 evacuation pauses of 7-8s began at 02:08:13Z (logpat-order-service-7b888968), coinciding with CPU rising from a baseline of ~44% to a window mean of ~75% (max 100%) with onset at 02:08Z (met-order-service-cpu_pct-0145-0300). The worker pool saturated (active=200, queue=19250) from 02:12:03Z (logpat-order-service-300bdd51). Deadline-exceeded errors followed from 02:15:11Z (logpat-order-service-1c82530b), and timeout rate rose from ~0.1% to a window mean of ~3%, peaking at ~6.4% (met-order-service-timeout_rate-0145-0300). Request rate was flat (met-order-service-request_rate-0145-0300), and api-gateway timeouts did not change (met-api-gateway-timeout_rate-0145-0300). The specific allocation source of the heap pressure has not been identified.

## Incident Timeline
| Time (UTC) | Label | Event | Evidence |
|---|---|---|---|
| 2026-09-10T22:15:00Z | CONFIRMED FACT | Deployment of payment-service 5.7.2->5.7.3 at 2026-09-10T22:15:00Z (SUCCEEDED): Dependency bumps | dep-bd77b48c |
| 2026-09-11T01:47:24Z | OBSERVED EVIDENCE | First log: 8x WARN on postgres: 'duration: 19602 ms statement: SELECT report_rollup()' (first 2026-09-11T01:47:24Z, last 2026-09-11T02:38:58Z) | logpat-postgres-44883ca5 |
| 2026-09-11T01:48:19Z | OBSERVED EVIDENCE | First log: 7x WARN on order-service: 'Inventory reservation retry for sku-86' (first 2026-09-11T01:48:19Z, last 2026-09-11T02:45:37Z) | logpat-order-service-95abd1bb |
| 2026-09-11T01:48:54Z | OBSERVED EVIDENCE | First log: 4x WARN on auth-service: 'Login rate limit hit for user id u-84' (first 2026-09-11T01:48:54Z, last 2026-09-11T02:33:23Z) | logpat-auth-service-cc8d3b87 |
| 2026-09-11T01:49:41Z | OBSERVED EVIDENCE | First log: 9x WARN on payment-service: 'Card network soft decline (code 05) for charge ch_41' (first 2026-09-11T01:49:41Z, last 2026-09-11T02:37:13Z) | logpat-payment-service-7e9bf84f |
| 2026-09-11T01:50:30Z | OBSERVED EVIDENCE | First log: 7x WARN on notification-service: 'SMTP provider throttled 1 message' (first 2026-09-11T01:50:30Z, last 2026-09-11T02:36:18Z) | logpat-notification-service-54b86179 |
| 2026-09-11T01:51:47Z | OBSERVED EVIDENCE | First log: 6x WARN on api-gateway: 'Slow client upload from 10.4.54.12 (1.9MB)' (first 2026-09-11T01:51:47Z, last 2026-09-11T02:33:47Z) | logpat-api-gateway-88b04940 |
| 2026-09-11T01:52:17Z | OBSERVED EVIDENCE | First log: 6x WARN on user-service: 'Deprecated API /v1/users/legacy called by client web-56' (first 2026-09-11T01:52:17Z, last 2026-09-11T02:32:03Z) | logpat-user-service-742b555e |
| 2026-09-11T02:08:00Z | OBSERVED EVIDENCE | Anomaly onset: order-service cpu_pct: baseline 44.17 -> window mean 74.97 (max 100.0, change 69.7%), onset 2026-09-11T02:08:00Z | met-order-service-cpu_pct-0145-0300 |
| 2026-09-11T02:08:13Z | OBSERVED EVIDENCE | First log: 14x WARN on order-service: 'GC pause 8140ms (G1 Evacuation Pause)' (first 2026-09-11T02:08:13Z, last 2026-09-11T02:40:03Z) | logpat-order-service-7b888968 |
| 2026-09-11T02:12:03Z | OBSERVED EVIDENCE | First log: 12x WARN on order-service: 'Thread pool order-worker saturated: active=200 queue=19250' (first 2026-09-11T02:12:03Z, last 2026-09-11T02:40:17Z) | logpat-order-service-300bdd51 |
| 2026-09-11T02:13:00Z | OBSERVED EVIDENCE | Anomaly onset: order-service p50_latency_ms: baseline 79.95 -> window mean 655.12 (max 1314.66, change 719.4%), onset 2026-09-11T02:13:00Z | met-order-service-p50_latency_ms-0145-0300 |
| 2026-09-11T02:13:00Z | OBSERVED EVIDENCE | Anomaly onset: order-service p95_latency_ms: baseline 198.04 -> window mean 1699.48 (max 3318.85, change 758.2%), onset 2026-09-11T02:13:00Z | met-order-service-p95_latency_ms-0145-0300 |
| 2026-09-11T02:15:00Z | OBSERVED EVIDENCE | Anomaly onset: order-service timeout_rate: baseline 0.1 -> window mean 2.99 (max 6.41, change 2889.6%), onset 2026-09-11T02:15:00Z | met-order-service-timeout_rate-0145-0300 |
| 2026-09-11T02:15:00Z | OBSERVED EVIDENCE | Anomaly onset: order-service error_rate: baseline 0.61 -> window mean 2.25 (max 4.47, change 270.6%), onset 2026-09-11T02:15:00Z | met-order-service-error_rate-0145-0300 |
| 2026-09-11T02:15:00Z | CONFIRMED FACT | Reported symptom start |  |
| 2026-09-11T02:15:11Z | OBSERVED EVIDENCE | First log: 8x ERROR on order-service: 'Request POST /v1/orders exceeded deadline 5000ms' (first 2026-09-11T02:15:11Z, last 2026-09-11T02:40:12Z) | logpat-order-service-1c82530b |
| 2026-09-11T02:21:00Z | CONFIRMED FACT | Incident reported |  |

## Observed Symptoms
- **OBSERVED EVIDENCE:** order-service p50_latency_ms: baseline 79.95 -> window mean 655.12 (max 1314.66, change 719.4%), onset 2026-09-11T02:13:00Z (met-order-service-p50_latency_ms-0145-0300)
- **OBSERVED EVIDENCE:** order-service p95_latency_ms: baseline 198.04 -> window mean 1699.48 (max 3318.85, change 758.2%), onset 2026-09-11T02:13:00Z (met-order-service-p95_latency_ms-0145-0300)
- **OBSERVED EVIDENCE:** order-service timeout_rate: baseline 0.1 -> window mean 2.99 (max 6.41, change 2889.6%), onset 2026-09-11T02:15:00Z (met-order-service-timeout_rate-0145-0300)
- **OBSERVED EVIDENCE:** order-service error_rate: baseline 0.61 -> window mean 2.25 (max 4.47, change 270.6%), onset 2026-09-11T02:15:00Z (met-order-service-error_rate-0145-0300)
- **OBSERVED EVIDENCE:** order-service cpu_pct: baseline 44.17 -> window mean 74.97 (max 100.0, change 69.7%), onset 2026-09-11T02:08:00Z (met-order-service-cpu_pct-0145-0300)
- **OBSERVED EVIDENCE:** [dependency] Only deployment in the 24h before T0 (and overnight): payment-service 5.7.2 -> 5.7.3 by ci-pipeline, status SUCCEEDED, changes described as 'Dependency bumps'. It is ~4h before T0=02:15Z, which is a timing mismatch with a symptom onset at T0 unless a delayed effect exists. (dep-bd77b48c)
- **OBSERVED EVIDENCE:** [dependency] No deployments to order-service, postgres, message-queue, user-service or api-gateway appear in the 2026-09-10T02:00Z to 2026-09-11T02:40Z window. (dep-bd77b48c)
- **OBSERVED EVIDENCE:** [dependency] Dependency graph: order-service's upstream dependencies are message-queue, payment-service, postgres and user-service (with transitive auth-service, redis). Its only downstream dependent is api-gateway. The only topology change listed (order-service -> redis) is scheduled for topology-v2 effective 2026-09-15, i.e. after the incident and not a cause. (topo-order-service-both-d2)
- **OBSERVED EVIDENCE:** [dependency] payment-service metrics (error_rate, p99_latency, timeout_rate) over the requested window show no visible step at 22:15Z deploy or at T0; sampled values stay roughly flat (error ~0.8%, p99 ~300ms, timeout ~0.1%). However the returned sampled series is labelled 01:15-02:40 rather than the requested 21:45-02:40, and baseline_mean is null, so the before/after comparison around the deploy could not be made from this result. (met-payment-service-error_rate-2145-0240, met-payment-service-p99_latency_ms-2145-0240, met-payment-service-timeout_rate-2145-0240)
- **OBSERVED EVIDENCE:** [observability] p50 latency rose from baseline mean ~80ms to ~655ms window mean (max ~1315ms); p95 from ~198ms to ~1699ms (max ~3319ms). Onset detected 02:13Z for p50. Step change at the 02:15 sample (p50 928ms, p95 2313ms). (met-order-service-p50_latency_ms-0145-0300, met-order-service-p95_latency_ms-0145-0300)
- **OBSERVED EVIDENCE:** [observability] Timeout rate rose from baseline ~0.1% to mean ~2.99% (max 6.41%); onset 02:15Z, sampled 1.5% at 02:15 and ~6% from 02:20 onward. Error rate rose from ~0.61% to ~2.25% (max 4.47%), onset 02:15Z. (met-order-service-timeout_rate-0145-0300, met-order-service-error_rate-0145-0300)
- **OBSERVED EVIDENCE:** [observability] CPU rose from baseline ~44% to mean ~75% (max 100%); onset 02:08Z (sampled 70% at 02:10, 95% at 02:15, 100% at 02:30). Memory rose from ~55% to ~66% (max 80.8%), onset 02:14Z. (met-order-service-cpu_pct-0145-0300, met-order-service-memory_pct-0145-0300)
- **OBSERVED EVIDENCE:** [observability] WARN logs: GC pauses of 7-8 seconds (G1 Evacuation Pause), 14 occurrences between 02:08:13Z and 02:40:03Z; first GC pause warnings precede the latency onset by ~5 minutes. (logpat-order-service-7b888968, log-93268339, log-03898ac9)
- **OBSERVED EVIDENCE:** [observability] Thread pool order-worker saturated (active=200, queue grew to ~19250 tasks) — 12 warnings from 02:12:03Z to 02:40:17Z. (logpat-order-service-300bdd51, log-b56a8c59, log-64c998a5)
- **OBSERVED EVIDENCE:** [observability] ERROR 'Request POST /v1/orders exceeded deadline 5000ms' — 8 occurrences from 02:15:11Z to 02:40:12Z. (logpat-order-service-1c82530b, log-e84d5728, log-b3faa1a5)
- **OBSERVED EVIDENCE:** [observability] Request rate flat (baseline ~250 rps vs window ~251 rps); DB connection utilisation flat (~30%, no change); p99 latency essentially unchanged (~398ms vs ~405ms). (met-order-service-request_rate-0145-0300, met-order-service-db_conn_util_pct-0145-0300, met-order-service-p99_latency_ms-0145-0300)
- **OBSERVED EVIDENCE:** [observability] api-gateway metrics flat across the window: p50 ~40ms, p95 ~119ms, p99 ~249ms, timeout rate ~0.1%, error rate ~0.5%, request rate ~1200 rps — no change vs baseline, no onset detected. (met-api-gateway-p50_latency_ms-0145-0300, met-api-gateway-p95_latency_ms-0145-0300, met-api-gateway-p99_latency_ms-0145-0300, met-api-gateway-timeout_rate-0145-0300, met-api-gateway-error_rate-0145-0300, met-api-gateway-request_rate-0145-0300)
- **OBSERVED EVIDENCE:** [observability] Inventory reservation retry WARNs appear sporadically from 01:48:19Z (before the incident), with a retry at 02:04:28Z; count 7 across window. (logpat-order-service-95abd1bb, log-547e7507, log-1bfd390c)
- **OBSERVED EVIDENCE:** [observability] postgres cpu_pct rose from baseline mean 35.11% to window mean 43.57% (+24.1%), with detected onset at 02:11Z; sampled series goes 34.7% (02:05) -> 44.4% (02:10) -> 52.4% (02:15) and stays ~49-53% through 02:40. (met-postgres-cpu_pct-0145-0240)
- **OBSERVED EVIDENCE:** [observability] postgres db_conn_util_pct, p99_latency_ms and disk_io_wait_ms show no meaningful change (db_conn_util -1.7%, p99 -0.6%, disk_io_wait +1.4%) over the window. (met-postgres-db_conn_util_pct-0145-0240, met-postgres-p99_latency_ms-0145-0240, met-postgres-disk_io_wait_ms-0145-0240)
- **OBSERVED EVIDENCE:** [observability] postgres WARN pattern 'duration: N ms statement: SELECT report_rollup()' appeared 8 times between 01:47:24Z and 02:38:58Z, with example durations of ~19.6s and ~17.9s (log-9aca42b9, log-b4544c2f). (logpat-postgres-44883ca5, log-9aca42b9, log-b4544c2f)
- **OBSERVED EVIDENCE:** [observability] order-service ERROR 'Request POST /v1/orders exceeded deadline 5000ms' occurred 7 times, first at 02:15:11Z and last at 02:36:36Z. Also WARN 'Thread pool order-worker saturated: active=200 queue=19250' (11 times, first 02:12:03Z, last 02:37:28Z) and GC pause WARNs (13 times, first 02:08:13Z, example 8140ms). (logpat-order-service-1c82530b, logpat-order-service-300bdd51, logpat-order-service-7b888968, log-e84d5728)
- **OBSERVED EVIDENCE:** [observability] payment-service latency, error rate, timeout rate and CPU are flat versus baseline (p99 +0.6%, error_rate -0.7%, timeout_rate -0.4%, cpu -1.4%). Only WARN is 'Card network soft decline' (9 times, first 01:49:41Z), which is a non-saturation pattern. (met-payment-service-p99_latency_ms-0145-0240, met-payment-service-error_rate-0145-0240, met-payment-service-timeout_rate-0145-0240, met-payment-service-cpu_pct-0145-0240, logpat-payment-service-7e9bf84f)
- **OBSERVED EVIDENCE:** [observability] user-service p99 (-0.5%), error_rate (-0.1%), timeout_rate (+0.2%) and cpu (+0.7%) are flat vs baseline. (met-user-service-p99_latency_ms-0145-0240, met-user-service-error_rate-0145-0240, met-user-service-timeout_rate-0145-0240, met-user-service-cpu_pct-0145-0240)
- **OBSERVED EVIDENCE:** [observability] auth-service p99 (+0.5%), error_rate (+1.3%), timeout_rate (-1.0%) and cpu (+0.3%) are flat. WARN 'Login rate limit hit' (4 times) is low-volume and not a saturation signal. (met-auth-service-p99_latency_ms-0145-0240, met-auth-service-error_rate-0145-0240, met-auth-service-timeout_rate-0145-0240, met-auth-service-cpu_pct-0145-0240, logpat-auth-service-cc8d3b87)
- **ASSUMPTION:** [critic: unsupported assumption] That the 02:08Z CPU onset and GC onset are precisely aligned (5-minute resolution metrics) 
- **ASSUMPTION:** [critic: unsupported assumption] That the allocating code path is the cause of the heap pressure (not identified) 
- **ASSUMPTION:** [critic: unsupported assumption] That the flat p99 is consistent with thread-pool saturation (not explained) 

## Investigation Performed
- Round 1 | observability | completed | attempts 1 | 4 tool calls | Characterize latency, timeouts, error rates and resource saturation for order-service and api-gateway from 2026-09-11T01:45Z to 03:00Z; identify first anomalous
- Round 1 | observability | completed | attempts 1 | 7 tool calls | Check dependency health over the same window for downstream services and datastores that order-service relies on, looking for saturation or errors that precede 
- Round 1 | dependency | completed | attempts 1 | 4 tool calls | Identify deployments, configuration changes, scaling events, or infra changes to order-service and its upstream dependencies in the 24 hours before 2026-09-11T0
- Round 1 | reasoning | completed | attempts 1 | 0 tool calls | Develop and rank competing hypotheses
- Round 1 | critic | completed | attempts 1 | 3 tool calls | Independently review hypotheses
- Round 1 | reporting | completed | attempts 1 | 0 tool calls | Write final report

## Root-Cause Hypotheses (ranked by evidence strength)
### 1. H1 - `resource_saturation` in `order-service` (confidence 0.83, critic: accept)
**INFERENCE:** order-service JVM stop-the-world GC pressure exhausted its worker threads, causing deadline-exceeded timeouts on POST /v1/orders. Mechanism: Unidentified allocation/heap pressure in order-service -> repeated 7-8s G1 evacuation pauses starting 02:08:13Z -> CPU climbs to ~100% and requests queue -> order-worker pool saturates (active=200, queue ~19250) at 02:12Z -> requests exceed 5000ms deadline, producing timeouts (~0.1% -> ~6%) and errors from 02:15Z. Upstream traffic (request rate flat) and DB pool (flat) are not the trigger; api-gateway is unaffected because failures are confined to order-service's own runtime.

Confidence breakdown: base 0.10; +0.08 corroboration across >=2 independent source types; +0.78 supporting evidence (8 refs, reliability-weighted, capped); -0.10 contradicting evidence (2 refs, capped 0.45); +0.08 proposed cause (02:08) precedes/coincides with first observed anomaly (02:08); -0.08 4 acknowledged evidence gaps; +0.05 critic review adjustment; = 0.83 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-order-service-7b888968` (strong): 14x WARN on order-service: 'GC pause 8140ms (G1 Evacuation Pause)' (first 2026-09-11T02:08:13Z, last 2026-09-11T02:40:03Z)
- [OBSERVED EVIDENCE] `met-order-service-cpu_pct-0145-0300` (strong): order-service cpu_pct: baseline 44.17 -> window mean 74.97 (max 100.0, change 69.7%), onset 2026-09-11T02:08:00Z
- [OBSERVED EVIDENCE] `logpat-order-service-300bdd51` (strong): 12x WARN on order-service: 'Thread pool order-worker saturated: active=200 queue=19250' (first 2026-09-11T02:12:03Z, last 2026-09-11T02:40:17Z)
- [OBSERVED EVIDENCE] `met-order-service-memory_pct-0145-0300` (moderate): order-service memory_pct: baseline 55.25 -> window mean 66.17 (max 80.83, change 19.8%), onset 2026-09-11T02:14:00Z
- [OBSERVED EVIDENCE] `logpat-order-service-1c82530b` (strong): 8x ERROR on order-service: 'Request POST /v1/orders exceeded deadline 5000ms' (first 2026-09-11T02:15:11Z, last 2026-09-11T02:40:12Z)
- [OBSERVED EVIDENCE] `met-order-service-timeout_rate-0145-0300` (moderate): order-service timeout_rate: baseline 0.1 -> window mean 2.99 (max 6.41, change 2889.6%), onset 2026-09-11T02:15:00Z
- [OBSERVED EVIDENCE] `met-order-service-request_rate-0145-0300` (moderate): order-service request_rate: baseline 250.23 -> window mean 250.6 (max 274.8, change 0.1%), onset none detected
- [OBSERVED EVIDENCE] `met-api-gateway-timeout_rate-0145-0300` (weak): api-gateway timeout_rate: baseline 0.1 -> window mean 0.1 (max 0.11, change -0.4%), onset none detected

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-order-service-p99_latency_ms-0145-0300` (weak): order-service p99_latency_ms: baseline 397.96 -> window mean 404.53 (max 436.33, change 1.7%), onset none detected
- [OBSERVED EVIDENCE] `met-order-service-db_conn_util_pct-0145-0300` (weak): order-service db_conn_util_pct: baseline 30.08 -> window mean 29.96 (max 32.7, change -0.4%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] JVM heap occupancy and allocation-rate metrics
- [UNKNOWN] GC cause/heap-size config and any INFO-level change (deploy, restart, config reload) on order-service before 02:08Z
- [UNKNOWN] Host-level scheduled jobs (cron) on order-service nodes
- [UNKNOWN] Sub-5-minute resolution CPU/GC data to confirm the 02:08Z onset precisely

### 2. H2 - `upstream_dependency_degradation` in `postgres` (confidence 0.00, critic: reject)
**INFERENCE:** Long-running report_rollup() queries on postgres drove CPU load up, slowing order-service's DB calls and causing the deadline timeouts. Mechanism: Scheduled/ad hoc report_rollup() runs from ~01:47Z -> postgres CPU rises ~24% (onset 02:11Z) -> order-service DB-bound calls slow -> worker threads are held longer -> pool saturates and requests exceed 5000ms deadline from 02:15Z.

Confidence breakdown: base 0.10; +0.08 corroboration across >=2 independent source types; +0.36 supporting evidence (3 refs, reliability-weighted, capped); -0.45 contradicting evidence (4 refs, capped 0.45); +0.08 proposed cause (01:47) precedes/coincides with first observed anomaly (02:08); -0.06 3 acknowledged evidence gaps; -0.40 critic review adjustment; = 0.00 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-postgres-44883ca5` (moderate): 8x WARN on postgres: 'duration: 19602 ms statement: SELECT report_rollup()' (first 2026-09-11T01:47:24Z, last 2026-09-11T02:38:58Z)
- [OBSERVED EVIDENCE] `met-postgres-cpu_pct-0145-0240` (moderate): postgres cpu_pct: baseline 35.11 -> window mean 43.57 (max 54.78, change 24.1%), onset 2026-09-11T02:11:00Z
- [OBSERVED EVIDENCE] `logpat-order-service-1c82530b` (weak): 8x ERROR on order-service: 'Request POST /v1/orders exceeded deadline 5000ms' (first 2026-09-11T02:15:11Z, last 2026-09-11T02:40:12Z)

Contradicting evidence:
- [OBSERVED EVIDENCE] `logpat-order-service-7b888968` (strong): 14x WARN on order-service: 'GC pause 8140ms (G1 Evacuation Pause)' (first 2026-09-11T02:08:13Z, last 2026-09-11T02:40:03Z)
- [OBSERVED EVIDENCE] `met-postgres-p99_latency_ms-0145-0240` (moderate): postgres p99_latency_ms: baseline 25.06 -> window mean 24.92 (max 27.38, change -0.6%), onset none detected
- [OBSERVED EVIDENCE] `met-postgres-db_conn_util_pct-0145-0240` (weak): postgres db_conn_util_pct: baseline 40.18 -> window mean 39.51 (max 43.5, change -1.7%), onset none detected
- [OBSERVED EVIDENCE] `met-order-service-db_conn_util_pct-0145-0300` (moderate): order-service db_conn_util_pct: baseline 30.08 -> window mean 29.96 (max 32.7, change -0.4%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Per-bucket timing of report_rollup() vs postgres CPU
- [UNKNOWN] order-service client-side DB call latency and wait time
- [UNKNOWN] postgres lock and active-session breakdown

### 3. H3 - `deployment_regression` in `payment-service` (confidence 0.00, critic: reject)
**INFERENCE:** The payment-service 5.7.2->5.7.3 dependency bump introduced a regression that slowed payment calls from order-service. Mechanism: Deploy at 22:15Z -> delayed payment-service regression -> order-service calls to payment-service block -> threads held -> saturation and deadline timeouts.

Confidence breakdown: base 0.10; +0.12 supporting evidence (1 refs, reliability-weighted, capped); -0.45 contradicting evidence (5 refs, capped 0.45); +0.08 proposed cause (22:15) precedes/coincides with first observed anomaly (02:08); -0.04 2 acknowledged evidence gaps; -0.40 critic review adjustment; = 0.00 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [CONFIRMED FACT] `dep-bd77b48c` (moderate): Deployment of payment-service 5.7.2->5.7.3 at 2026-09-10T22:15:00Z (SUCCEEDED): Dependency bumps

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-payment-service-p99_latency_ms-0145-0240` (strong): payment-service p99_latency_ms: baseline 297.92 -> window mean 299.74 (max 328.66, change 0.6%), onset none detected
- [OBSERVED EVIDENCE] `met-payment-service-error_rate-0145-0240` (moderate): payment-service error_rate: baseline 0.81 -> window mean 0.8 (max 0.87, change -0.7%), onset none detected
- [OBSERVED EVIDENCE] `met-payment-service-timeout_rate-0145-0240` (moderate): payment-service timeout_rate: baseline 0.1 -> window mean 0.1 (max 0.11, change -0.4%), onset none detected
- [OBSERVED EVIDENCE] `met-payment-service-cpu_pct-0145-0240` (weak): payment-service cpu_pct: baseline 40.05 -> window mean 39.49 (max 43.47, change -1.4%), onset none detected
- [OBSERVED EVIDENCE] `logpat-order-service-7b888968` (moderate): 14x WARN on order-service: 'GC pause 8140ms (G1 Evacuation Pause)' (first 2026-09-11T02:08:13Z, last 2026-09-11T02:40:03Z)

Remaining uncertainties / missing evidence:
- [UNKNOWN] Payment-service metrics with a correct pre-deploy baseline (the returned window was mislabelled and baseline is null)
- [UNKNOWN] Order-service to payment-service call latency per route

### 4. H4 - `unknown` in `order-service` (confidence 0.00, critic: reject)
**INFERENCE:** A retry loop in order-service's inventory reservation path (sku-86) generates excess allocation or work that drives GC pressure and thread saturation. Mechanism: Sporadic inventory reservation retries from 01:48Z (repeated at 02:04Z) -> extra allocation and blocking work in order-service -> GC pressure and worker saturation -> deadline timeouts.

Confidence breakdown: base 0.10; +0.08 supporting evidence (2 refs, reliability-weighted, capped); -0.15 contradicting evidence (1 refs, capped 0.45); +0.08 proposed cause (01:48) precedes/coincides with first observed anomaly (02:08); -0.06 3 acknowledged evidence gaps; -0.40 critic review adjustment; = 0.00 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-order-service-95abd1bb` (weak): 7x WARN on order-service: 'Inventory reservation retry for sku-86' (first 2026-09-11T01:48:19Z, last 2026-09-11T02:45:37Z)
- [OBSERVED EVIDENCE] `log-1bfd390c` (weak): WARN order-service: Inventory reservation retry for sku-82

Contradicting evidence:
- [OBSERVED EVIDENCE] `logpat-order-service-95abd1bb` (moderate): 7x WARN on order-service: 'Inventory reservation retry for sku-86' (first 2026-09-11T01:48:19Z, last 2026-09-11T02:45:37Z)

Remaining uncertainties / missing evidence:
- [UNKNOWN] Retry rate and volume per minute
- [UNKNOWN] Inventory service call latency and error metrics
- [UNKNOWN] Allocation profile linking the retry path to heap growth

## Critic Review
- **Verdict:** `APPROVED` (rounds reviewed: 1)
- **Reasoning:** H1 (order-service JVM GC pressure exhausting order-worker threads) is the leading hypothesis and is supported by consistent timing and multiple independent sources. The first anomaly is the 14 G1 evacuation pauses of 7-8s starting 02:08:13Z (logs), which is coincident with CPU onset at 02:08Z. Worker pool saturation follows at 02:12Z, then deadline-exceeded errors and timeout onset at 02:15Z, matching the reported symptom. My own query confirms no order-service deployment or config change in 20:00-02:40Z, and no order-service WARN/ERROR before 02:08:13Z other than low-volume inventory retries. Request rate is flat, so traffic is not the trigger. Gateway and DB connection pools are flat. Alternatives: H2 (postgres report_rollup) is contradicted because postgres CPU rises at 02:11Z, after the GC onset; postgres p99 is flat and order-service DB connection utilisation is flat. H3 (payment regression) is contradicted by flat payment latency, errors, timeouts and CPU, and by the absence of any order-service anomaly for four hours after the deploy. H4 (inventory retry storm) is weak: only ~7 retry WARNs in an hour is not a retry storm, and no mechanism links them to 8s pauses. Limitations: no JVM heap or allocation-rate metrics are exposed, so the allocating code path is unidentified; the flat p99 alongside a 6% timeout rate is somewhat unusual and may reflect how timed-out requests are recorded. These are limitations, not reasons to withhold approval; the category (resource saturation / GC on order-service) and culprit (order-service) are well supported.
- H1: **accept** - GC pauses (02:08:13Z) precede CPU saturation, worker pool saturation (02:12Z), and deadline timeouts (02:15Z). No order-service deploy or config change found. Request rate, DB connections and gateway are flat, so the fault is local to order-service. Unidentified allocation source and flat p99 are limitations only.
- H2: **reject** - Postgres CPU onset (02:11Z) comes after order-service GC onset (02:08Z), so it cannot explain it. Postgres p99 is flat, order-service DB connection utilisation is flat, and no client-side DB latency shows waiting.
- H3: **reject** - Payment latency, errors, timeouts and CPU are all flat across the window. The deploy was about four hours before the first anomaly, with no order-service anomaly in between. The blocking pre-check (correlation only) is confirmed.
- H4: **reject** - Only about 7 inventory retry WARNs over roughly an hour, which is too low to drive heap pressure of 8s pauses. No allocation or latency evidence links the retries to GC. Retries may be incidental and do not explain the failure.
- pre-check blocking `correlation_only` on H3: change hypothesis supported only by the change record itself (temporal correlation); no log/metric evidence of the changed behaviour
- pre-check warning `culprit_symptom` on H3: no log/metric evidence cited for culprit payment-service
- pre-check warning `single_source` on H3: all support comes from one source type (deployment)
- pre-check warning `single_source` on H4: all support comes from one source type (log)
- alternative: Unidentified order-service heap/allocation growth (e.g., a leak or large object churn) with no visible code path in the available telemetry
- alternative: Scheduled host-level job on order-service nodes coinciding with 02:08Z (not checked; no tool exposes host cron)

## Probable Root Cause
ROOT CAUSE IDENTIFIED (critic-approved; still an INFERENCE from evidence): resource_saturation in order-service - order-service JVM stop-the-world GC pressure exhausted its worker threads, causing deadline-exceeded timeouts on POST /v1/orders.

## Corrective Actions
- Mitigate immediately by restarting or rolling order-service instances to clear heap pressure and worker saturation, while watching for recurrence of the GC pauses.
- Temporarily reduce order-service load or shed non-critical traffic if pauses recur, to keep the order-worker pool from saturating.
- Capture heap dumps or JFR/GC logs from affected instances during any recurrence to identify the allocating code path, since none is currently visible in telemetry.

## Preventive Actions
- Identify the allocation or heap-growth source in order-service (for example via heap histograms and allocation profiling) and fix it, as the root trigger is not yet confirmed.
- Review and tune the G1 configuration and heap sizing for order-service so that evacuation pauses remain well below the 5000ms request deadline.
- Add bounded queueing and fail-fast behaviour to the order-worker pool so that saturation rejects requests quickly rather than queueing ~19k requests.

## Monitoring Recommendations
- Alert on GC pause duration above 1s (or any G1 evacuation pause above 2s) for order-service, using the existing 'GC pause' log pattern (logpat-order-service-7b888968) and JVM metrics where available.
- Alert on order-worker pool saturation (active threads at max or queue depth above a threshold) for order-service (logpat-order-service-300bdd51).
- Alert on order-service cpu_pct sustained above ~70% and on timeout_rate above baseline (~0.1%), with per-minute resolution to reduce detection lag.
- Expose JVM heap usage, allocation rate and GC metrics for order-service, which are currently missing and limit root-cause confirmation.
- Track postgres report_rollup() duration and order-service DB connection utilisation to keep the rejected H2 path under watch.

## Evidence Gaps
- none recorded

## Limitations
- No JVM heap or allocation-rate metrics are available, so the allocating code path causing the heap pressure is unidentified.
- Metrics are at 5-minute resolution, so the alignment between the 02:08Z CPU onset and the 02:08:13Z GC onset is approximate.
- order-service p99 latency remained flat despite a ~6% timeout rate; this is not explained and may reflect how timed-out requests are recorded.
- Host-level scheduled jobs on order-service nodes around 02:08Z were not checked because no tool exposes host cron activity.
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: critic verdict APPROVED

## Final Status
`ROOT_CAUSE_IDENTIFIED`

The most probable root cause of INC-004 is JVM GC pressure in order-service, which exhausted its order-worker threads and produced deadline timeouts on POST /v1/orders (H1, confidence 0.83). The GC onset at 02:08:13Z precedes the worker saturation, deadline errors and timeouts, and the alternatives were rejected: postgres report_rollup() (H2) rose after GC onset with flat DB latency, the payment-service dependency bump (H3) showed no payment-side anomaly, and the inventory retry path (H4) was too low-volume to explain the pauses. The specific allocating code path is not yet identified, so the underlying heap-pressure source remains an open item to close.

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
  "evidence_records": 92,
  "duration_s": 63.1,
  "tokens": {
    "input_tokens": 40,
    "output_tokens": 20747,
    "cache_read_tokens": 23161,
    "cache_write_tokens": 59205,
    "llm_calls": 13,
    "cost_usd": 0.018009735000000002
  },
  "tokens_by_agent": {
    "orchestrator": {
      "input_tokens": 6,
      "output_tokens": 943,
      "cache_read_tokens": 1306,
      "cache_write_tokens": 1739,
      "llm_calls": 2,
      "cost_usd": 0.000702535
    },
    "dependency": {
      "input_tokens": 8,
      "output_tokens": 2401,
      "cache_read_tokens": 7203,
      "cache_write_tokens": 5478,
      "llm_calls": 3,
      "cost_usd": 0.00195808
    },
    "observability": {
      "input_tokens": 12,
      "output_tokens": 8246,
      "cache_read_tokens": 5699,
      "cache_write_tokens": 24315,
      "llm_calls": 4,
      "cost_usd": 0.007220565
    },
    "reasoning": {
      "input_tokens": 4,
      "output_tokens": 5246,
      "cache_read_tokens": 0,
      "cache_write_tokens": 13229,
      "llm_calls": 1,
      "cost_usd": 0.004277024999999999
    },
    "critic": {
      "input_tokens": 6,
      "output_tokens": 2240,
      "cache_read_tokens": 8953,
      "cache_write_tokens": 10416,
      "llm_calls": 2,
      "cost_usd": 0.00251213
    },
    "reporting": {
      "input_tokens": 4,
      "output_tokens": 1671,
      "cache_read_tokens": 0,
      "cache_write_tokens": 4028,
      "llm_calls": 1,
      "cost_usd": 0.0013394000000000001
    }
  }
}
```
