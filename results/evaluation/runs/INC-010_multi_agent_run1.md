# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-010
- **Title:** Intermittent gateway latency
- **Severity:** SEV3
- **Affected services:** api-gateway
- **Start time:** 2026-09-29T19:45:00+00:00
- **Investigation ID:** inv-265ac36bc1 (multi_agent)
- **Final status:** `INCONCLUSIVE`

## Executive Summary
INC-010 (SEV3, intermittent gateway latency) investigation is INCONCLUSIVE: the root cause could not be established. api-gateway p99 latency rose about 35% from a baseline of 252.9 ms to a window mean of 341.3 ms (max 557.0 ms), with onset at 19:40Z (met-api-gateway-p99_latency_ms-1930-2010). Median latency (p50 +1.2%) and request rate (-2.7%) were essentially flat, and no alarm fired. No leading hypothesis is supported. Evidence gaps are material: 24 of 41 gateway data points are missing, downstream p99 data is almost entirely absent, and deployment and config-change queries failed because the investigation tool-call budget was exhausted. Those failed queries are unverified gaps, not evidence that nothing changed.

Hypothesis status: H2 (postgres report_rollup contention) is rejected, since postgres p95, p99 and CPU were flat across the window (met-postgres-p95_latency_ms-1935-1950, met-postgres-cpu_pct-1935-1950) and the slow statement at 19:30Z precedes onset (logpat-postgres-44883ca5). H1 (slow-client uploads), H3 (upstream degradation), H4 (infrastructure event) and H5 (telemetry artifact) remain at needs_evidence with low confidence (0.0 to 0.13). The first logged slow upload (19:44Z, log-441467a5 and related) follows the 19:40Z onset, which weakens H1. H3 cannot be tested because downstream data is missing. H4 is not excluded because per-instance metrics were not pulled. H5 is plausible given the sampling gaps.

## Incident Timeline
| Time (UTC) | Label | Event | Evidence |
|---|---|---|---|
| 2026-09-29T19:30:27Z | OBSERVED EVIDENCE | First log: 3x WARN on postgres: 'duration: 11702 ms statement: SELECT report_rollup()' (first 2026-09-29T19:30:27Z, last 2026-09-29T20:03:45Z) | logpat-postgres-44883ca5 |
| 2026-09-29T19:45:00Z | CONFIRMED FACT | Reported symptom start |  |
| 2026-09-29T19:51:00Z | CONFIRMED FACT | Incident reported |  |

## Observed Symptoms
- **OBSERVED EVIDENCE:** [dependency] Upstream dependency graph (depth 2) for api-gateway: auth-service, order-service, payment-service, user-service directly; transitive via order-service -> message-queue, payment-service, user-service, and postgres/redis; auth-service -> postgres/redis. No topology changes listed between graph versions. (topo-api-gateway-upstream-d2)
- **INFERENCE:** [dependency] Based on this round, no change-based trigger is visible in the 30 minutes before T0, so the intermittent P99 latency may stem from load, dependency behaviour, or an untracked change source; metric analysis is needed to confirm onset. (topo-api-gateway-upstream-d2)
- **OBSERVED EVIDENCE:** [dependency] Dependency graph (topology-v2) shows api-gateway calls auth-service, order-service, payment-service and user-service; transitively these reach postgres, redis and message-queue. api-gateway has no downstream dependents listed and no topology changes. (topo-api-gateway-both-d2)
- **OBSERVED EVIDENCE:** [dependency] postgres has no upstream dependencies; downstream dependents are auth-service, order-service, payment-service and user-service (all potentially impacted). No topology changes recorded. (topo-postgres-both-d1)
- **OBSERVED EVIDENCE:** [dependency] redis downstream dependents are auth-service, order-service, payment-service and user-service. Topology change in topology-v2 effective 2026-09-15 (added edge order-service -> redis), i.e. two weeks before the incident, not within the window. (topo-redis-both-d1)
- **OBSERVED EVIDENCE:** [dependency] message-queue downstream dependents are notification-service and order-service. No topology changes recorded. api-gateway reaches it only via order-service. (topo-message-queue-both-d1)
- **OBSERVED EVIDENCE:** [observability] Postgres metrics over 19:15-20:10Z are flat vs baseline: cpu_pct mean 35.1 vs 35.19 baseline; memory 65.33 vs 65.23; db_conn_util 39.73 vs 40.12; p95 latency 12.03 vs 12.04 ms; p99 24.94 vs 25.14 ms; disk_io_wait 2.0 vs 1.99 ms. No onset detected on any metric. Value at 19:45 bucket: db_conn_util 36.4%, p99 25.5 ms. (met-postgres-cpu_pct-1915-2010, met-postgres-memory_pct-1915-2010, met-postgres-db_conn_util_pct-1915-2010, met-postgres-p95_latency_ms-1915-2010, met-postgres-p99_latency_ms-1915-2010, met-postgres-disk_io_wait_ms-1915-2010)
- **OBSERVED EVIDENCE:** [observability] Postgres WARN logs: 'duration: <n> ms statement: SELECT report_rollup()' appeared 3 times (durations 11.7s at 19:30:27Z, 15.8s at 19:40:44Z, 14.5s at 20:03:45Z). These are slow-statement warnings; they occur before and after T0 and are not reflected in the Postgres p95/p99 metrics. (logpat-postgres-44883ca5, log-87888189, log-13313f6d, log-cf53ce1d)
- **OBSERVED EVIDENCE:** [observability] Redis metrics flat vs baseline: cache_hit_rate 95.06% vs 94.88%; p95 1.50 vs 1.51 ms; p99 3.00 vs 3.01 ms; cpu 15.0% vs 15.0%; memory 59.6% vs 59.8%. No onset. (met-redis-cache_hit_rate-1915-2010, met-redis-p95_latency_ms-1915-2010, met-redis-p99_latency_ms-1915-2010, met-redis-cpu_pct-1915-2010, met-redis-memory_pct-1915-2010)
- **OBSERVED EVIDENCE:** [observability] Message-queue metrics flat vs baseline: request_rate 401 vs 399 msg/s; p95 10.0 vs 10.0 ms; p99 20.1 vs 20.2 ms; cpu 20.1% vs 19.8%; memory 44.7% vs 44.5%. No onset. disk_io_wait not collected for this service. (met-message-queue-request_rate-1915-2010, met-message-queue-p95_latency_ms-1915-2010, met-message-queue-p99_latency_ms-1915-2010, met-message-queue-cpu_pct-1915-2010, met-message-queue-memory_pct-1915-2010)
- **INFERENCE:** [observability] The report_rollup() slow statements may be a periodic batch job; if it holds locks or resources, it could contribute to intermittent gateway tail latency, but the telemetry here does not show a measurable effect on data-layer latency, so this is unconfirmed. 
- **OBSERVED EVIDENCE:** [observability] api-gateway error_rate (0.50% -> 0.51%), timeout_rate (0.10% -> 0.10%) and request_rate (1219.6 -> 1186.7 rps, -2.7%) were essentially unchanged versus baseline in the datapoints that exist. No 5xx or timeout spike is visible in the metrics. (met-api-gateway-error_rate-1930-2010, met-api-gateway-timeout_rate-1930-2010, met-api-gateway-request_rate-1930-2010)
- **OBSERVED EVIDENCE:** [observability] Only one WARN log in the window: 'Slow client upload from 10.4.64.12 (1.9MB)' at 19:48:39Z. No ERROR/FATAL logs from api-gateway between 19:30Z and 20:10Z. Log results are flagged as incomplete. (log-0ddc93ea, logpat-api-gateway-88b04940)
- **INFERENCE:** [observability] The p99-only elevation with flat p50/p95, flat error/timeout rates, and a single slow large upload log at 19:48Z is consistent with a small tail of slow requests (possibly large-payload or slow-client requests) rather than a broad backend degradation. This is an interpretation, not confirmed; it needs per-route data. 
- **OBSERVED EVIDENCE:** [observability] Postgres cpu_pct window mean 34.61 vs baseline 35.19 (-1.7%), max 37.12; no onset detected; 0 missing points of 16. (met-postgres-cpu_pct-1935-1950)
- **OBSERVED EVIDENCE:** [observability] Postgres disk_io_wait_ms window mean 2.00 vs baseline 1.99 (+0.5%), max 2.16; no onset detected; 0 missing points of 16. (met-postgres-disk_io_wait_ms-1935-1950)
- **OBSERVED EVIDENCE:** [observability] Postgres p95_latency_ms window mean 12.02 vs baseline 12.04 (-0.1%), max 13.2 (19:40 sample 12.55); no onset detected; 0 missing points of 16. (met-postgres-p95_latency_ms-1935-1950)
- **INFERENCE:** [observability] H2 is weakened for this window: no resource or lock signal in postgres metrics. The single slow statement near onset (per critic) would not show up in aggregate p95 or CPU, so H2 is not fully ruled out by these metrics alone. 
- **OBSERVED EVIDENCE:** [observability] api-gateway cpu_pct window mean 34.61% vs baseline mean 34.72% (-0.3%); window max 36.05%. Sampled 5-min values 33.8, 33.4, 35.4, 34.9 (19:30-19:45). No CPU step at 19:40Z. (met-api-gateway-cpu_pct-1930-1950)
- **OBSERVED EVIDENCE:** [observability] api-gateway memory_pct window mean 50.25% vs baseline 49.84% (+0.8%); window max 54.42%. Sampled values: 49.7 (19:30), 48.2 (19:35), 47.5 (19:40), 52.8 (19:45). A single-sample rise at 19:45Z; not sustained in the 5-min series. (met-api-gateway-memory_pct-1930-1950)
- **OBSERVED EVIDENCE:** [observability] api-gateway request_rate window mean 1186.7 rps vs baseline 1219.6 rps (-2.7%). Sampled values: 1151.6 (19:30), 1150.3 (19:35), 1226.0 (19:40), 1206.2 (19:45). The 19:40Z value is a single-sample step (+6.5% vs 19:35 sample) that reverts to 1206 by 19:45Z; the window mean is below baseline. (met-api-gateway-request_rate-1930-1950)
- **OBSERVED EVIDENCE:** [observability] Logs exist but are partial (is_partial=true, note says do not conclude absence): WARN 'Login rate limit hit' x2 (20:02:43Z-20:08:10Z), INFO 'Issued 23 tokens in last minute' at 19:39:16Z, INFO 'JWKS cache refreshed (keys=4)' at 19:52:04Z. (logpat-auth-service-cc8d3b87, logpat-auth-service-4abd377f, logpat-auth-service-dede43d7, log-b8f7797c, log-cef84d80, log-d12f50f4)
- **OBSERVED EVIDENCE:** [observability] Logs are partial: INFO 'Outbox relay published' at 19:38:53Z and 19:57:19Z (66 events), INFO 'Created 31 orders in last minute' at 19:50:04Z, WARN 'Inventory reservation retry' at 20:07:18Z. (logpat-order-service-6338e215, logpat-order-service-d19346d9, logpat-order-service-95abd1bb, log-d9355de5, log-b7a69f04, log-7df89df0, log-177145a1)
- **OBSERVED EVIDENCE:** [observability] Logs are partial: WARN 'Card network soft decline (code 05)' first at 19:41:36Z, last at 20:10:00Z; INFO settlement heartbeat ok at 19:38:38Z and 20:03:51Z. (logpat-payment-service-7e9bf84f, logpat-payment-service-22f3d084, log-96864060, log-98b5c9a1, log-a8a1f0b8, log-a93f8a5a)
- **OBSERVED EVIDENCE:** [observability] Logs are partial: only two INFO GET /v1/users/me 200 21ms entries (20:02:24Z, 20:05:09Z) in the window. (logpat-user-service-d218ab88, log-88277ff4, log-6739b68d)
- **ASSUMPTION:** [critic: unsupported assumption] That the 19:40Z onset is real rather than a sampling artifact 
- **ASSUMPTION:** [critic: unsupported assumption] That the slow-upload WARN logs are complete and represent the affected population 
- **ASSUMPTION:** [critic: unsupported assumption] That absent downstream data means the upstreams were healthy 
- **ASSUMPTION:** [critic: unsupported assumption] That the failed deployment and config queries would have shown no changes 

## Investigation Performed
- Round 1 | observability | completed | attempts 1 | 6 tool calls | Characterize api-gateway latency (P50/P95/P99), error rate, and request volume from 2026-09-29T19:30Z onward; identify whether the elevation is isolated to spec
- Round 1 | observability | completed | attempts 1 | 6 tool calls | Check data-layer health (postgres, redis, message-queue) for saturation or latency that coincides with the 19:45Z symptom start.
- Round 1 | dependency | completed | attempts 1 | 3 tool calls | Identify any deployments, configuration changes, or feature flag changes to api-gateway and its upstream services in the window shortly before 2026-09-29T19:45Z
- Round 1 | dependency | completed | attempts 1 | 6 tool calls | Confirm the dependency graph and check for config or deployment changes on shared infrastructure (postgres, redis, message-queue) near the symptom start.
- Round 1 | reasoning | completed | attempts 1 | 0 tool calls | Develop and rank competing hypotheses
- Round 1 | critic | completed | attempts 1 | 4 tool calls | Independently review hypotheses
- Round 2 | observability | completed | attempts 1 | 8 tool calls | FOLLOW-UP requested by critic: Re-query p99, p95, error_rate and request_rate for auth-service, order-service, payment-service and user-service over 19:35-20:10
- Round 2 | observability | completed | attempts 1 | 3 tool calls | FOLLOW-UP requested by critic: Query api-gateway cpu_pct, memory_pct and request_rate for 19:30-19:50Z, and the api-gateway logs for upstream timeout or slow-re
- Round 2 | observability | completed | attempts 1 | 3 tool calls | FOLLOW-UP requested by critic: Query postgres cpu_pct, disk_io_wait_ms and p95 for 19:35-19:50Z, plus postgres error or lock logs in that window. (reason: Confi
- Round 2 | reasoning | completed | attempts 1 | 0 tool calls | Develop and rank competing hypotheses
- Round 2 | critic | completed | attempts 1 | 4 tool calls | Independently review hypotheses
- Round 3 | observability | completed | attempts 1 | 4 tool calls | FOLLOW-UP requested by critic: Re-query p99_latency_ms, p95_latency_ms, error_rate and timeout_rate for auth-service, order-service, payment-service and user-se
- Round 3 | observability | completed | attempts 1 | 6 tool calls | FOLLOW-UP requested by critic: Re-run the api-gateway log query for 19:30-20:10Z with keywords such as 'slow', 'timeout', 'upstream', 'latency' and 'upload', an
- Round 3 | dependency | completed | attempts 1 | 6 tool calls | FOLLOW-UP requested by critic: Confirm which upstream services (auth, order, payment, user) are on the gateway request path for the affected routes, and whether
- Round 3 | reasoning | completed | attempts 1 | 0 tool calls | Develop and rank competing hypotheses
- Round 3 | critic | completed | attempts 1 | 3 tool calls | Independently review hypotheses
- Round 3 | reporting | completed | attempts 1 | 0 tool calls | Write final report

## Root-Cause Hypotheses (ranked by evidence strength)
### 1. H3 - `upstream_dependency_degradation` in `order-service` (confidence 0.13, critic: needs_evidence)
**INFERENCE:** An intermittent, unobserved degradation in one of the four gateway upstreams (order, payment, auth, or user) drives the gateway tail latency. order-service is listed first only because it has the most dependency fan-out (postgres, redis, message-queue, payment, user). Mechanism: A slow subset of upstream calls holds gateway request threads longer. Because the gateway fans out to four upstreams, a single slow upstream lifts the p99 tail while p50 is unaffected.

Confidence breakdown: base 0.10; +0.08 corroboration across >=2 independent source types; +0.24 supporting evidence (4 refs, reliability-weighted, capped); -0.05 contradicting evidence (2 refs, capped 0.45); -0.05 tool failures/partial data for order-service; -0.06 3 acknowledged evidence gaps; (reliability discount already applied: 0.08); -0.05 critic review adjustment; = 0.13 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [OBSERVED EVIDENCE] `met-api-gateway-p99_latency_ms-1930-2010` (moderate): api-gateway p99_latency_ms: baseline 252.9 -> window mean 341.26 (max 556.96, change 34.9%), onset 2026-09-29T19:40:00Z, 24 points missing
- [CONFIRMED FACT] `topo-api-gateway-upstream-d3` (weak): api-gateway depends on ['auth-service', 'order-service', 'payment-service', 'user-service']; called by ? (graph topology-v2)
- [CONFIRMED FACT] `topo-order-service-upstream-d3` (weak): order-service depends on ['message-queue', 'payment-service', 'postgres', 'redis', 'user-service']; called by ? (graph topology-v2)
- [OBSERVED EVIDENCE] `met-order-service-p99_latency_ms-1930-2010` (weak): order-service p99_latency_ms: baseline 398.55 -> window mean 394.65 (max 415.95, change -1.0%), onset none detected, 36 points missing

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-order-service-p99_latency_ms-1930-2010` (weak): order-service p99_latency_ms: baseline 398.55 -> window mean 394.65 (max 415.95, change -1.0%), onset none detected, 36 points missing
- [OBSERVED EVIDENCE] `logpat-order-service-d19346d9` (weak): 1x INFO on order-service: 'Created 31 orders in last minute' (first 2026-09-29T19:50:04Z, last 2026-09-29T19:50:04Z)

Remaining uncertainties / missing evidence:
- [UNKNOWN] Downstream p99 for auth, order, payment and user for 19:35-20:10Z (36/41 points missing in every case)
- [UNKNOWN] Upstream-side trace or span timing for gateway calls
- [UNKNOWN] Log evidence of upstream timeouts or slow calls from the gateway's perspective

### 2. H1 - `traffic_surge` in `api-gateway` (confidence 0.10, critic: needs_evidence)
**INFERENCE:** A small tail of slow requests, possibly large-payload or slow-client uploads, inflates api-gateway p99 without broad degradation. Mechanism: Large or slow-client uploads occupy gateway connections/workers for longer, so a small fraction of requests lands in the p99 tail while p50 and p95 move little. The tail rises without a sustained change in request volume.

Confidence breakdown: base 0.10; +0.08 corroboration across >=2 independent source types; +0.28 supporting evidence (6 refs, reliability-weighted, capped); -0.10 contradicting evidence (2 refs, capped 0.45); -0.05 tool failures/partial data for api-gateway; -0.08 4 acknowledged evidence gaps; (reliability discount already applied: 0.20); -0.05 critic review adjustment; = 0.10 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [OBSERVED EVIDENCE] `met-api-gateway-p99_latency_ms-1930-2010` (moderate): api-gateway p99_latency_ms: baseline 252.9 -> window mean 341.26 (max 556.96, change 34.9%), onset 2026-09-29T19:40:00Z, 24 points missing
- [OBSERVED EVIDENCE] `met-api-gateway-p50_latency_ms-1930-2010` (moderate): api-gateway p50_latency_ms: baseline 39.87 -> window mean 40.34 (max 43.69, change 1.2%), onset none detected, 24 points missing
- [OBSERVED EVIDENCE] `met-api-gateway-request_rate-1930-2010` (weak): api-gateway request_rate: baseline 1219.56 -> window mean 1186.74 (max 1227.98, change -2.7%), onset none detected, 24 points missing
- [OBSERVED EVIDENCE] `logpat-api-gateway-88b04940` (weak): 1x WARN on api-gateway: 'Slow client upload from 10.4.64.12 (1.9MB)' (first 2026-09-29T19:48:39Z, last 2026-09-29T19:48:39Z)
- [OBSERVED EVIDENCE] `log-441467a5` (weak): WARN api-gateway: Slow client upload from 10.4.65.12 (1.9MB)
- [OBSERVED EVIDENCE] `log-cedc4b69` (weak): WARN api-gateway: Slow client upload from 10.4.53.12 (1.9MB)

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-api-gateway-p99_latency_ms-1930-2010` (moderate): api-gateway p99_latency_ms: baseline 252.9 -> window mean 341.26 (max 556.96, change 34.9%), onset 2026-09-29T19:40:00Z, 24 points missing
- [OBSERVED EVIDENCE] `log-441467a5` (weak): WARN api-gateway: Slow client upload from 10.4.65.12 (1.9MB)

Remaining uncertainties / missing evidence:
- [UNKNOWN] Request-size or payload distribution for gateway requests around 19:35-19:50Z
- [UNKNOWN] Per-route p99 showing whether the tail is confined to upload routes
- [UNKNOWN] Complete (unfiltered) WARN/ERROR scan for api-gateway
- [UNKNOWN] Gateway telemetry after 19:50Z

### 3. H5 - `unknown` in `None` (confidence 0.03, critic: needs_evidence)
**INFERENCE:** The reported onset and tail shape are partly a telemetry artifact: sparse 5-minute sampling and a 60% data gap after 19:45Z may exaggerate or misplace the p99 rise, and the real impact may be smaller or unobserved. Mechanism: With only a few valid p99 points, a single noisy sample (336.9 ms at 19:40, 557 ms at 19:45) can set the detected onset. Missing points after 19:50Z mean the true end-state and peak are unknown, so the observed tail may not reflect a real, sustained condition.

Confidence breakdown: base 0.10; +0.04 supporting evidence (2 refs, reliability-weighted, capped); -0.03 contradicting evidence (1 refs, capped 0.45); +0.00 no cause time given; temporal precedence unverified; -0.04 2 acknowledged evidence gaps; (reliability discount already applied: 0.04); -0.05 critic review adjustment; = 0.03 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [OBSERVED EVIDENCE] `met-api-gateway-p99_latency_ms-1930-2010` (weak): api-gateway p99_latency_ms: baseline 252.9 -> window mean 341.26 (max 556.96, change 34.9%), onset 2026-09-29T19:40:00Z, 24 points missing
- [OBSERVED EVIDENCE] `met-auth-service-p99_latency_ms-1930-2010` (weak): auth-service p99_latency_ms: baseline 90.85 -> window mean 91.82 (max 94.96, change 1.1%), onset none detected, 36 points missing

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-api-gateway-p99_latency_ms-1930-2010` (weak): api-gateway p99_latency_ms: baseline 252.9 -> window mean 341.26 (max 556.96, change 34.9%), onset 2026-09-29T19:40:00Z, 24 points missing

Remaining uncertainties / missing evidence:
- [UNKNOWN] Raw high-resolution (sub-minute) gateway latency data
- [UNKNOWN] Explanation of the telemetry gap (pipeline outage or per-metric issue)

### 4. H4 - `infrastructure_degradation` in `api-gateway` (confidence 0.00, critic: needs_evidence)
**INFERENCE:** An untracked infrastructure event (noisy neighbour, node or network issue, or autoscaling/failover) affects a subset of api-gateway instances from about 19:40Z. Mechanism: Degraded instances (CPU steal, network, or a restart) serve a share of requests slowly. Load balancing spreads these requests across the fleet, so aggregate CPU and error metrics stay flat while the tail rises.

Confidence breakdown: base 0.10; +0.09 supporting evidence (2 refs, reliability-weighted, capped); -0.17 contradicting evidence (2 refs, capped 0.45); -0.05 tool failures/partial data for api-gateway; -0.06 3 acknowledged evidence gaps; (reliability discount already applied: 0.07); -0.05 critic review adjustment; = 0.00 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [OBSERVED EVIDENCE] `met-api-gateway-p99_latency_ms-1930-2010` (moderate): api-gateway p99_latency_ms: baseline 252.9 -> window mean 341.26 (max 556.96, change 34.9%), onset 2026-09-29T19:40:00Z, 24 points missing
- [OBSERVED EVIDENCE] `met-api-gateway-memory_pct-1930-1950` (weak): api-gateway memory_pct: baseline 49.84 -> window mean 50.25 (max 54.42, change 0.8%), onset none detected, 4 points missing

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-api-gateway-cpu_pct-1930-1950` (moderate): api-gateway cpu_pct: baseline 34.72 -> window mean 34.61 (max 36.05, change -0.3%), onset none detected, 4 points missing
- [CONFIRMED FACT] `topo-api-gateway-both-d2` (weak): api-gateway depends on ['auth-service', 'order-service', 'payment-service', 'user-service']; called by [] (graph topology-v2)

Remaining uncertainties / missing evidence:
- [UNKNOWN] Per-instance gateway latency, CPU and restart data
- [UNKNOWN] Infrastructure event logs (node, network, autoscaling, failover) for 19:30-20:10Z
- [UNKNOWN] Gateway telemetry after 19:50Z

### 5. H2 - `resource_saturation` in `postgres` (confidence 0.00, critic: reject)
**INFERENCE:** Recurring slow report_rollup() statements in postgres cause lock or resource contention that adds tail latency to gateway requests. Mechanism: A long-running report_rollup() holds locks or consumes resources, delaying queries from upstream services, which in turn lengthens the gateway's tail.

Confidence breakdown: base 0.10; +0.02 supporting evidence (1 refs, reliability-weighted, capped); -0.45 contradicting evidence (4 refs, capped 0.45); -0.05 tool failures/partial data for postgres; -0.04 2 acknowledged evidence gaps; (reliability discount already applied: 0.02); -0.40 critic review adjustment; = 0.00 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-postgres-44883ca5` (weak): 3x WARN on postgres: 'duration: 11702 ms statement: SELECT report_rollup()' (first 2026-09-29T19:30:27Z, last 2026-09-29T20:03:45Z)

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-postgres-p95_latency_ms-1935-1950` (strong): postgres p95_latency_ms: baseline 12.04 -> window mean 12.02 (max 13.2, change -0.1%), onset none detected
- [OBSERVED EVIDENCE] `met-postgres-cpu_pct-1935-1950` (moderate): postgres cpu_pct: baseline 35.19 -> window mean 34.61 (max 37.12, change -1.7%), onset none detected
- [OBSERVED EVIDENCE] `met-postgres-p99_latency_ms-1915-2010` (moderate): postgres p99_latency_ms: baseline 25.14 -> window mean 24.94 (max 26.4, change -0.8%), onset none detected
- [OBSERVED EVIDENCE] `logpat-postgres-44883ca5` (moderate): 3x WARN on postgres: 'duration: 11702 ms statement: SELECT report_rollup()' (first 2026-09-29T19:30:27Z, last 2026-09-29T20:03:45Z)

Remaining uncertainties / missing evidence:
- [UNKNOWN] Evidence that report_rollup() runs on any gateway route
- [UNKNOWN] Postgres lock-wait metrics and complete logs (log query was partial)

## Critic Review
- **Verdict:** `INCONCLUSIVE` (rounds reviewed: 3)
- **Reasoning:** No hypothesis is adequately supported. My attempts to pull deployments, config changes and gateway error/timeout metrics all failed with BUDGET_EXHAUSTED, so those are unverified evidence gaps, not evidence of health. What the existing evidence shows: api-gateway p99 rises about 35% from a 19:40Z onset while p50 and CPU are flat, and request rate is down 2.7%. The gateway tail is real in the metrics, but its cause is not identified. H2 is rejected: postgres p95, p99 and CPU are flat across the window and the 19:30Z statement precedes onset. H1 is weakened because the first logged slow upload is at 19:44Z, after the 19:40Z onset, and the upload WARN logs are partial and inconsistent between queries. H3 cannot be tested because downstream p99 is almost entirely missing (only the 19:30Z order-service point exists), so an upstream slowdown is neither confirmed nor excluded. H4 is weakened by flat aggregate CPU but not excluded, since per-instance data was never pulled. H5 (telemetry artifact) is plausible given 24 of 41 gateway points missing, but the 19:35 and 19:40 samples form a consistent step across retries. Further evidence requests cannot be executed in this final round with the tool budget exhausted.
- H1: **needs_evidence** - Onset at 19:40Z precedes the first logged slow upload at 19:44Z, so the logged uploads cannot explain the onset. The upload WARN logs are partial and disagree between queries. Per-route p99 or request-size data would be needed, and those queries could not be run.
- H3: **needs_evidence** - Plausible tail mechanism, but no upstream p99 exists for 19:35-20:10Z beyond a single baseline-level order-service point. Neither onset nor upstream culprit can be confirmed. Upstream timing or gateway-side upstream latency would be needed.
- H4: **needs_evidence** - Flat aggregate CPU argues against a broad fleet problem, but a subset-of-instances fault is not excluded. Per-instance latency and infrastructure event data were never collected, and the deployment/config check failed.
- H5: **needs_evidence** - A telemetry artifact is a real possibility given heavy sparsity after 19:45Z. However, the 19:35 and 19:40 samples show a consistent step across retries, so it is not established as an artifact. Resolving the telemetry gap is needed to settle it.
- H2: **reject** - postgres p95, p99 and CPU are flat across 19:35-20:10Z with no onset at 19:40Z. The only slow-statement evidence is weak, partial log data, and there is no evidence that any gateway route touches report_rollup().
- pre-check warning `single_source` on H4: all support comes from one source type (metric)
- pre-check warning `cause_time` on H5: no cause time given; temporal precedence cannot be verified
- pre-check warning `single_source` on H5: all support comes from one source type (metric)
- pre-check warning `single_source` on H2: all support comes from one source type (log)
- alternative: Subset-of-instance gateway degradation (H4), not yet tested per instance
- alternative: Upstream subset slowdown in auth, order, payment or user (H3), untestable with current telemetry
- alternative: Telemetry sampling or pipeline artifact exaggerating the p99 rise (H5)
- alternative: Large or slow-client uploads (H1), though onset precedes the first logged upload

## Probable Root Cause
Root cause could not be conclusively established with the available evidence.

## Corrective Actions
- Pull deployment and configuration-change history for api-gateway and its four upstreams (auth, order, payment, user) for 19:00Z to 20:00Z (re-run get_deployments and get_config_changes, which failed on budget exhaustion), and roll back any change found in that window.
- Check api-gateway per-instance p99 and CPU/memory for 19:30Z to 20:00Z to determine whether a subset of instances is degraded (H4); drain or restart any outlier instances.
- Verify whether customer slowness is ongoing; if so, apply a temporary rate limit or timeout tuning on slow-client upload paths as a stopgap, with a reversal plan.
- Re-query order-, payment-, auth- and user-service p99 and error metrics for the window to confirm or exclude an upstream slowdown (H3).

## Preventive Actions
- Add a p99-latency alert on api-gateway with a baseline-relative threshold, so that a roughly 30% tail regression is detected without relying on customer reports.
- Improve telemetry resolution and completeness: reduce sampling from 5 minutes to 1 minute for gateway and upstream latency metrics, and fix the pipeline gaps that dropped about 60% of data after 19:45Z.
- Establish per-upstream latency and error dashboards for api-gateway (auth, order, payment, user) so that dependency-level tail latency can be attributed without manual queries.
- Set a tool or investigation budget that covers the full evidence-collection plan, so that deployment and config queries are not lost in future investigations.

## Monitoring Recommendations
- Alert when api-gateway p99 exceeds about 1.25x its 7-day baseline for 5 consecutive minutes, and page on sustained p99 above 500 ms.
- Track api-gateway p99 and p50 per instance and per upstream route, to test for subset-of-instance degradation.
- Monitor count of 'Slow client upload' WARN logs and upload payload sizes, to measure whether slow uploads correlate with latency spikes (H1).
- Monitor order-, payment-, auth- and user-service p99 and error rates, plus postgres lock waits and report_rollup() duration, with explicit alerts for missing data so that gaps are visible rather than read as health.
- Monitor gateway request rate against baseline to detect traffic or routing shifts (currently -2.7%).

## Evidence Gaps
- [UNKNOWN] get_config_changes failed for all: investigation tool-call budget exhausted (BUDGET_EXHAUSTED)
- [UNKNOWN] get_deployments failed for all: investigation tool-call budget exhausted (BUDGET_EXHAUSTED)
- [UNKNOWN] query_logs returned incomplete data for service=api-gateway (PARTIAL_DATA)
- [UNKNOWN] query_logs returned incomplete data for service=api-gateway, keyword=slow (PARTIAL_DATA)
- [UNKNOWN] query_logs returned incomplete data for service=api-gateway, keyword=timeout (PARTIAL_DATA)
- [UNKNOWN] query_logs returned incomplete data for service=api-gateway, keyword=upload (PARTIAL_DATA)
- [UNKNOWN] query_logs returned incomplete data for service=api-gateway, keyword=upstream (PARTIAL_DATA)
- [UNKNOWN] query_logs returned incomplete data for service=auth-service (PARTIAL_DATA)
- [UNKNOWN] query_logs returned incomplete data for service=message-queue (PARTIAL_DATA)
- [UNKNOWN] query_logs returned incomplete data for service=order-service (PARTIAL_DATA)
- [UNKNOWN] query_logs returned incomplete data for service=payment-service (PARTIAL_DATA)
- [UNKNOWN] query_logs returned incomplete data for service=postgres (PARTIAL_DATA)
- [UNKNOWN] query_logs returned incomplete data for service=postgres, keyword=lock (PARTIAL_DATA)
- [UNKNOWN] query_logs returned incomplete data for service=redis (PARTIAL_DATA)
- [UNKNOWN] query_logs returned incomplete data for service=user-service (PARTIAL_DATA)
- [UNKNOWN] query_metrics failed for service=api-gateway, metrics=['p99_latency_ms', 'error_rate', 'timeout_rate']: investigation tool-call budget exhausted (BUDGET_EXHAUSTED)

## Limitations
- Deployment and configuration-change queries failed due to tool-budget exhaustion; deployment and config causes are unverified.
- 24 of 41 api-gateway metric points are missing, and the 19:40Z onset may partly reflect sampling artifacts.
- Downstream (auth, order, payment, user) p99 data is almost entirely missing, so upstream health could not be confirmed or excluded.
- Log queries returned incomplete data for most services; the slow-upload WARN logs may not represent the full affected population.
- No per-instance gateway metrics were analysed, so subset-of-instance degradation is not excluded.
- 3 tool calls failed and 19 returned partial data; affected areas are treated as unknown, not healthy.
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: critic verdict INCONCLUSIVE

## Final Status
`INCONCLUSIVE`

Root cause could not be conclusively established with the available evidence. INC-010 remains INCONCLUSIVE. Gateway p99 latency rose about 35% from 19:40Z while median latency and request rate were flat, and no hypothesis reached a supported status. Postgres contention has been rejected. The remaining candidates (upstream degradation, a subset-of-instance infrastructure issue, slow-client uploads, or a telemetry artifact) cannot be distinguished with current evidence, mainly because of missing downstream data and failed deployment and config queries. Priority is to close these evidence gaps (deployment/config history, per-instance metrics, and upstream latency) and to add alerting so that the next occurrence is attributable.

## Execution Statistics
```json
{
  "rounds": 3,
  "tool_calls": 60,
  "tool_failures": 0,
  "tool_retries": 0,
  "partial_results": 19,
  "agent_failures": 0,
  "agent_retries": 0,
  "invalid_llm_outputs": 0,
  "messages_exchanged": 56,
  "evidence_records": 96,
  "duration_s": 151.03,
  "tokens": {
    "input_tokens": 106,
    "output_tokens": 51950,
    "cache_read_tokens": 74884,
    "cache_write_tokens": 164974,
    "llm_calls": 35,
    "cost_usd": 0.04735619
  },
  "tokens_by_agent": {
    "orchestrator": {
      "input_tokens": 6,
      "output_tokens": 992,
      "cache_read_tokens": 1319,
      "cache_write_tokens": 1834,
      "llm_calls": 2,
      "cost_usd": 0.00073904
    },
    "dependency": {
      "input_tokens": 20,
      "output_tokens": 5534,
      "cache_read_tokens": 13851,
      "cache_write_tokens": 15101,
      "llm_calls": 7,
      "cost_usd": 0.004795135
    },
    "observability": {
      "input_tokens": 46,
      "output_tokens": 23287,
      "cache_read_tokens": 33870,
      "cache_write_tokens": 54865,
      "llm_calls": 16,
      "cost_usd": 0.018844925000000005
    },
    "reasoning": {
      "input_tokens": 12,
      "output_tokens": 12358,
      "cache_read_tokens": 0,
      "cache_write_tokens": 58120,
      "llm_calls": 3,
      "cost_usd": 0.0134452
    },
    "critic": {
      "input_tokens": 18,
      "output_tokens": 7827,
      "cache_read_tokens": 25844,
      "cache_write_tokens": 30993,
      "llm_calls": 6,
      "cost_usd": 0.008047865
    },
    "reporting": {
      "input_tokens": 4,
      "output_tokens": 1952,
      "cache_read_tokens": 0,
      "cache_write_tokens": 4061,
      "llm_calls": 1,
      "cost_usd": 0.0014840250000000001
    }
  }
}
```
