# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-001
- **Title:** Payment API latency spike
- **Severity:** SEV2
- **Affected services:** api-gateway, payment-service
- **Start time:** 2026-09-02T14:00:00+00:00
- **Investigation ID:** inv-a0dc22bdf0 (multi_agent)
- **Final status:** `PROBABLE_ROOT_CAUSE`

## Executive Summary
INC-001 (SEV2): customers saw checkout take 3-5 seconds, the payment API P95 latency alarm fired, and some payments failed with 5xx. Symptoms began at 14:00Z and were reported at 14:06Z. The investigation's most probable explanation (final status PROBABLE_ROOT_CAUSE, confidence 0.68, not a confirmed fact) is exhaustion of the payment-db-pool connection pool on payment-service, driven by connections held for long periods by RefundService.processPartialRefund. Pool utilisation rose from a ~35% baseline at about 13:49Z to 96% at 14:00Z and 100% at 14:05Z (met-payment-service-db_conn_util_pct-1330-1410). At 14:00:16Z new requests could not acquire a connection within 5000 ms (active=50, idle=0, waiting=46), which produced timeouts, 5xx errors and latency that propagated to api-gateway (logpat-payment-service-7d1739af, met-payment-service-timeout_rate-1330-1410, met-payment-service-p95_latency_ms-1330-1430). Leak-detection warnings attribute long holds (>30 s) to RefundService.processPartialRefund from 13:45:08Z onward (logpat-payment-service-9d1f3d29). Request rate stayed flat (met-payment-service-request_rate-1330-1400), so the saturation points to connection holding rather than traffic growth. The critic verdict was NEEDS_MORE_EVIDENCE: the refund path is plausible but has not been shown to hold the majority of the saturated pool.

## Incident Timeline
| Time (UTC) | Label | Event | Evidence |
|---|---|---|---|
| 2026-09-02T11:00:00Z | CONFIRMED FACT | Config change on api-gateway: routes.cache_ttl_s 30 -> 60 at 2026-09-02T11:00:00Z (OPS-2497) | cfg-fbdeed15 |
| 2026-09-02T13:31:28Z | OBSERVED EVIDENCE | First log: 7x WARN on postgres: 'duration: 18302 ms statement: SELECT report_rollup()' (first 2026-09-02T13:31:28Z, last 2026-09-02T14:23:09Z) | logpat-postgres-44883ca5 |
| 2026-09-02T13:49:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service db_conn_util_pct: baseline 34.95 -> window mean 62.78 (max 100.0, change 79.7%), onset 2026-09-02T13:49:00Z | met-payment-service-db_conn_util_pct-1330-1410 |
| 2026-09-02T13:50:46Z | OBSERVED EVIDENCE | First log: 6x WARN on payment-service: 'HikariPool-payment - Connection leak detection triggered for connection conn-63, held > 30000 ms by RefundService.processPartialRefund' (first 2026-09-02T13:50:46Z, last 2026-09-02T14:00:16Z) | logpat-payment-service-9d1f3d29 |
| 2026-09-02T13:54:00Z | CONFIRMED FACT | Deployment of notification-service 3.4.0->3.4.1 at 2026-09-02T13:54:00Z (SUCCEEDED): Update email templates for receipts | dep-d757f128 |
| 2026-09-02T14:00:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service p95_latency_ms: baseline 150.24 -> window mean 1434.15 (max 3018.96, change 854.6%), onset 2026-09-02T14:00:00Z | met-payment-service-p95_latency_ms-1330-1430 |
| 2026-09-02T14:00:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service p99_latency_ms: baseline 302.14 -> window mean 2662.85 (max 5545.92, change 781.3%), onset 2026-09-02T14:00:00Z | met-payment-service-p99_latency_ms-1330-1430 |
| 2026-09-02T14:00:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service error_rate: baseline 0.8 -> window mean 10.89 (max 23.67, change 1259.0%), onset 2026-09-02T14:00:00Z | met-payment-service-error_rate-1330-1430 |
| 2026-09-02T14:00:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service timeout_rate: baseline 0.1 -> window mean 8.88 (max 19.09, change 8807.1%), onset 2026-09-02T14:00:00Z | met-payment-service-timeout_rate-1330-1430 |
| 2026-09-02T14:00:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service p50_latency_ms: baseline 60.48 -> window mean 255.36 (max 980.48, change 322.2%), onset 2026-09-02T14:00:00Z | met-payment-service-p50_latency_ms-1330-1410 |
| 2026-09-02T14:00:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service error_rate: baseline 0.8 -> window mean 5.61 (max 22.31, change 600.1%), onset 2026-09-02T14:00:00Z | met-payment-service-error_rate-1330-1410 |
| 2026-09-02T14:00:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service timeout_rate: baseline 0.1 -> window mean 4.29 (max 19.0, change 4199.7%), onset 2026-09-02T14:00:00Z | met-payment-service-timeout_rate-1330-1410 |
| 2026-09-02T14:00:00Z | CONFIRMED FACT | Reported symptom start |  |
| 2026-09-02T14:00:16Z | OBSERVED EVIDENCE | First log: 7x ERROR on payment-service: 'Timeout acquiring connection from pool payment-db-pool after 5000ms (active=50, idle=0, waiting=46)' (first 2026-09-02T14:00:16Z, last 2026-09-02T14:05:16Z) | logpat-payment-service-7d1739af |
| 2026-09-02T14:01:00Z | OBSERVED EVIDENCE | Anomaly onset: api-gateway p95_latency_ms: baseline 119.71 -> window mean 952.49 (max 2004.12, change 695.6%), onset 2026-09-02T14:01:00Z | met-api-gateway-p95_latency_ms-1330-1430 |
| 2026-09-02T14:01:00Z | OBSERVED EVIDENCE | Anomaly onset: api-gateway error_rate: baseline 0.5 -> window mean 4.46 (max 9.88, change 791.9%), onset 2026-09-02T14:01:00Z | met-api-gateway-error_rate-1330-1430 |
| 2026-09-02T14:06:00Z | CONFIRMED FACT | Incident reported |  |

## Observed Symptoms
- **OBSERVED EVIDENCE:** api-gateway p95_latency_ms: baseline 119.71 -> window mean 952.49 (max 2004.12, change 695.6%), onset 2026-09-02T14:01:00Z (met-api-gateway-p95_latency_ms-1330-1430)
- **OBSERVED EVIDENCE:** api-gateway error_rate: baseline 0.5 -> window mean 4.46 (max 9.88, change 791.9%), onset 2026-09-02T14:01:00Z (met-api-gateway-error_rate-1330-1430)
- **OBSERVED EVIDENCE:** payment-service p95_latency_ms: baseline 150.24 -> window mean 1434.15 (max 3018.96, change 854.6%), onset 2026-09-02T14:00:00Z (met-payment-service-p95_latency_ms-1330-1430)
- **OBSERVED EVIDENCE:** payment-service p99_latency_ms: baseline 302.14 -> window mean 2662.85 (max 5545.92, change 781.3%), onset 2026-09-02T14:00:00Z (met-payment-service-p99_latency_ms-1330-1430)
- **OBSERVED EVIDENCE:** payment-service error_rate: baseline 0.8 -> window mean 10.89 (max 23.67, change 1259.0%), onset 2026-09-02T14:00:00Z (met-payment-service-error_rate-1330-1430)
- **OBSERVED EVIDENCE:** payment-service timeout_rate: baseline 0.1 -> window mean 8.88 (max 19.09, change 8807.1%), onset 2026-09-02T14:00:00Z (met-payment-service-timeout_rate-1330-1430)
- **OBSERVED EVIDENCE:** payment-service db_conn_util_pct: baseline 34.95 -> window mean 62.78 (max 100.0, change 79.7%), onset 2026-09-02T13:49:00Z (met-payment-service-db_conn_util_pct-1330-1410)
- **OBSERVED EVIDENCE:** payment-service p50_latency_ms: baseline 60.48 -> window mean 255.36 (max 980.48, change 322.2%), onset 2026-09-02T14:00:00Z (met-payment-service-p50_latency_ms-1330-1410)
- **OBSERVED EVIDENCE:** payment-service error_rate: baseline 0.8 -> window mean 5.61 (max 22.31, change 600.1%), onset 2026-09-02T14:00:00Z (met-payment-service-error_rate-1330-1410)
- **OBSERVED EVIDENCE:** payment-service timeout_rate: baseline 0.1 -> window mean 4.29 (max 19.0, change 4199.7%), onset 2026-09-02T14:00:00Z (met-payment-service-timeout_rate-1330-1410)
- **OBSERVED EVIDENCE:** payment-service timeout_rate: baseline 0.1 -> window mean 0.24 (max 4.58, change 145.2%), onset none detected (met-payment-service-timeout_rate-1330-1400)
- **OBSERVED EVIDENCE:** [dependency] Only deployment in 13:00Z-14:10Z across all services: notification-service 3.4.0 -> 3.4.1 (email template update), SUCCEEDED at 13:54Z. notification-service is not in the focus set and is not in payment-service's upstream or downstream graph. (dep-d757f128)
- **OBSERVED EVIDENCE:** [dependency] Dependency graph (topology-v1): payment-service upstream = auth-service, postgres, redis (transitive via auth-service to postgres and redis); downstream = api-gateway and order-service. No topology changes recorded. (topo-payment-service-both-d2)
- **OBSERVED EVIDENCE:** [observability] postgres db_conn_util_pct rose from baseline mean 40.59% to window mean 53.15% (max 67.91%), detected onset 13:55Z; sampled series steps from 41.8% (13:50) to 57.0% (13:55) and ~63-66% from 14:00 through 14:25. (met-postgres-db_conn_util_pct-1330-1425)
- **OBSERVED EVIDENCE:** [observability] postgres cpu_pct, memory_pct, disk_io_wait_ms and p95_latency_ms were flat versus baseline (changes +1.0%, -0.9%, -0.8%, +0.7%); error_rate unchanged at ~0.05%. (met-postgres-cpu_pct-1330-1425, met-postgres-memory_pct-1330-1425, met-postgres-disk_io_wait_ms-1330-1425, met-postgres-p95_latency_ms-1330-1425, met-postgres-error_rate-1330-1425)
- **OBSERVED EVIDENCE:** [observability] postgres WARN log pattern 'duration: <n> ms statement: SELECT report_rollup()' appeared 7 times between 13:31:28Z and 14:23:09Z, with durations 11.0s to 19.3s (e.g., 18302 ms at 13:31:28Z, 18402 ms at 13:55:51Z, 14902 ms at 14:23:09Z). (logpat-postgres-44883ca5, log-c7aa34d6, log-a3e067ad, log-dc6e51c3)
- **OBSERVED EVIDENCE:** [observability] redis p95_latency_ms (1.50 vs 1.49 baseline), cache_hit_rate (94.99% vs 95.01%), cpu_pct (15.0%), memory_pct (60.1% vs 59.8%) and error_rate (0.01%) were unchanged; no onset detected. (met-redis-p95_latency_ms-1330-1425, met-redis-cache_hit_rate-1330-1425, met-redis-cpu_pct-1330-1425, met-redis-memory_pct-1330-1425, met-redis-error_rate-1330-1425)
- **OBSERVED EVIDENCE:** [observability] payment-service P95 latency rose from baseline mean 150.24 ms to window mean 1434.15 ms (+854.6%); onset detected at 14:00:00Z (14:00 bucket 811 ms, 14:05 bucket 2714 ms, sustained ~2.7-2.9 s through 14:30). (met-payment-service-p95_latency_ms-1330-1430)
- **OBSERVED EVIDENCE:** [observability] payment-service P99 latency rose from baseline mean 302.14 ms to window mean 2662.85 ms (+781.3%), onset 14:00:00Z; 14:05 bucket 5219 ms, max 5546 ms. (met-payment-service-p99_latency_ms-1330-1430)
- **OBSERVED EVIDENCE:** [observability] payment-service error rate rose from baseline 0.8% to window mean 10.89% (max 23.67%), onset 14:00:00Z; sustained ~20-22% from 14:05 to 14:30. (met-payment-service-error_rate-1330-1430)
- **OBSERVED EVIDENCE:** [observability] payment-service timeout rate rose from baseline 0.1% to window mean 8.88% (max 19.09%), onset 14:00:00Z; ~18-19% from 14:05 onward. (met-payment-service-timeout_rate-1330-1430)
- **OBSERVED EVIDENCE:** [observability] payment-service request rate is flat: baseline 302.3 vs window 301.12 (-0.4%), no traffic surge preceding the degradation. (met-payment-service-request_rate-1330-1430)
- **OBSERVED EVIDENCE:** [observability] api-gateway P95 latency rose from baseline 119.71 ms to window mean 952.49 ms (+695.6%); onset 14:01:00Z, 14:05 bucket 1843 ms, sustained ~1.8-1.9 s to 14:30. (met-api-gateway-p95_latency_ms-1330-1430)
- **OBSERVED EVIDENCE:** [observability] api-gateway error rate rose from baseline 0.5% to window mean 4.46% (max 9.88%), onset 14:01:00Z; ~8-9.6% from 14:05 onward. (met-api-gateway-error_rate-1330-1430)
- **OBSERVED EVIDENCE:** [observability] api-gateway P99 latency is essentially unchanged (baseline 249.33 ms vs window 249.59 ms, +0.1%) and gateway timeout rate is unchanged (0.1% vs 0.1%); request rate -1.8% (1209.7 to 1188.0 rpm-equivalent units). (met-api-gateway-p99_latency_ms-1330-1430, met-api-gateway-timeout_rate-1330-1430, met-api-gateway-request_rate-1330-1430)
- **ASSUMPTION:** [critic: unsupported assumption] That refund-held connections constitute the majority of the 50 active pool connections (no holder attribution). 
- **ASSUMPTION:** [critic: unsupported assumption] That the refund path is the source of the leak rather than a symptom of slower refund calls. 
- **ASSUMPTION:** [critic: unsupported assumption] That pool utilisation at 13:45 (~35%) reflects a ramp caused by refunds, given that the 1-minute series is not available. 
- **ASSUMPTION:** [critic: unsupported assumption] That the request rate being flat means refund share was flat (refund volume is unmeasured). 

## Investigation Performed
- Round 1 | observability | completed | attempts 1 | 3 tool calls | Characterize latency and error patterns on the request path from 13:30Z to 14:30Z: P95/P99 latency, 5xx rate, timeouts, and traffic volume.
- Round 1 | observability | completed | attempts 1 | 4 tool calls | Check datastore and cache health (postgres, redis) for saturation or contention around the symptom start.
- Round 1 | dependency | completed | attempts 1 | 3 tool calls | Identify deployments, configuration changes, or feature flag changes to payment-service, auth-service, api-gateway, order-service, postgres, or redis in the win
- Round 1 | reasoning | completed | attempts 1 | 0 tool calls | Develop and rank competing hypotheses
- Round 1 | critic | completed | attempts 1 | 5 tool calls | Independently review hypotheses
- Round 2 | observability | completed | attempts 1 | 5 tool calls | FOLLOW-UP requested by critic: Pull ERROR/WARN logs for RefundService / processPartialRefund across 13:30-14:10Z, including leak-detection frequency and any ref
- Round 2 | dependency | completed | attempts 1 | 4 tool calls | FOLLOW-UP requested by critic: Verify the call/DB graph for RefundService and whether refund flows share the payment-db-pool and any postgres tables used by rep
- Round 2 | reasoning | completed | attempts 1 | 0 tool calls | Develop and rank competing hypotheses
- Round 2 | critic | completed | attempts 1 | 4 tool calls | Independently review hypotheses
- Round 3 | observability | completed | attempts 1 | 7 tool calls | FOLLOW-UP requested by critic: Query payment-service logs for RefundService activity 13:00-14:00Z: retry messages, refund request counts, and any feature-flag o
- Round 3 | observability | completed | attempts 1 | 3 tool calls | FOLLOW-UP requested by critic: Query payment-service metrics request_rate, db_conn_util_pct, timeout_rate for 13:30-14:00Z at 1-minute granularity, and check fo
- Round 3 | reasoning | completed | attempts 1 | 0 tool calls | Develop and rank competing hypotheses
- Round 3 | critic | completed | attempts 1 | 3 tool calls | Independently review hypotheses
- Round 3 | reporting | completed | attempts 1 | 0 tool calls | Write final report

## Root-Cause Hypotheses (ranked by evidence strength)
### 1. H1 - `db_connection_pool_exhaustion` in `payment-service` (confidence 0.68, critic: needs_evidence)
**INFERENCE:** A connection leak or long hold in RefundService.processPartialRefund consumes payment-db-pool connections, saturating the pool and causing acquire timeouts, 5xx and latency at 14:00Z. Mechanism: RefundService.processPartialRefund acquires connections from payment-db-pool and holds them beyond 30s (leak-detection WARNs from 13:45:08Z). Free connections drop, pool utilisation climbs from ~35% (13:45) to ~52% (13:50), ~78% (13:55) and ~96-100% (14:00+). At 14:00:16Z new requests cannot acquire a connection within 5000 ms (active=50, idle=0, waiting=46), so they time out, producing the timeout step (0.1% to ~4.6-19%), 5xx errors and P95/P99 latency rise on payment-service, which propagates to api-gateway at 14:01Z. Request rate is flat, so the saturation is driven by connection holding, not traffic.

Confidence breakdown: base 0.10; +0.08 corroboration across >=2 independent source types; +0.78 supporting evidence (8 refs, reliability-weighted, capped); -0.15 contradicting evidence (1 refs, capped 0.45); +0.08 proposed cause (13:45) precedes/coincides with first observed anomaly (13:49); -0.08 4 acknowledged evidence gaps; -0.05 critic review adjustment; = 0.68 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-payment-service-9d1f3d29` (moderate): 6x WARN on payment-service: 'HikariPool-payment - Connection leak detection triggered for connection conn-63, held > 30000 ms by RefundService.processPartialRefund' (first 2026-09-02T13:50:46Z, last 2026-09-02T14:00:16Z)
- [OBSERVED EVIDENCE] `met-payment-service-db_conn_util_pct-1330-1410` (strong): payment-service db_conn_util_pct: baseline 34.95 -> window mean 62.78 (max 100.0, change 79.7%), onset 2026-09-02T13:49:00Z
- [OBSERVED EVIDENCE] `logpat-payment-service-7d1739af` (strong): 7x ERROR on payment-service: 'Timeout acquiring connection from pool payment-db-pool after 5000ms (active=50, idle=0, waiting=46)' (first 2026-09-02T14:00:16Z, last 2026-09-02T14:05:16Z)
- [OBSERVED EVIDENCE] `met-payment-service-timeout_rate-1330-1410` (strong): payment-service timeout_rate: baseline 0.1 -> window mean 4.29 (max 19.0, change 4199.7%), onset 2026-09-02T14:00:00Z
- [OBSERVED EVIDENCE] `met-payment-service-error_rate-1330-1410` (strong): payment-service error_rate: baseline 0.8 -> window mean 5.61 (max 22.31, change 600.1%), onset 2026-09-02T14:00:00Z
- [OBSERVED EVIDENCE] `met-payment-service-request_rate-1330-1400` (moderate): payment-service request_rate: baseline 302.3 -> window mean 299.31 (max 330.9, change -1.0%), onset none detected
- [OBSERVED EVIDENCE] `met-payment-service-p95_latency_ms-1330-1430` (moderate): payment-service p95_latency_ms: baseline 150.24 -> window mean 1434.15 (max 3018.96, change 854.6%), onset 2026-09-02T14:00:00Z
- [OBSERVED EVIDENCE] `met-postgres-p95_latency_ms-1330-1425` (moderate): postgres p95_latency_ms: baseline 11.98 -> window mean 12.06 (max 12.83, change 0.7%), onset none detected

Contradicting evidence:
- [OBSERVED EVIDENCE] `logpat-payment-service-9d1f3d29` (moderate): 6x WARN on payment-service: 'HikariPool-payment - Connection leak detection triggered for connection conn-63, held > 30000 ms by RefundService.processPartialRefund' (first 2026-09-02T13:50:46Z, last 2026-09-02T14:00:16Z)

Remaining uncertainties / missing evidence:
- [UNKNOWN] Pool-holder attribution: how many of the ~50 active connections are held by refund calls.
- [UNKNOWN] Pool active/idle/waiting time series from 13:30 to 14:10 at 1-minute resolution (to confirm the 13:45-13:49 ramp).
- [UNKNOWN] Refund request volume and retry counts over time (no telemetry available so far).
- [UNKNOWN] Traces or thread dumps showing the refund path holding connections.

### 2. H2 - `unknown` in `payment-service` (confidence 0.23, critic: needs_evidence)
**INFERENCE:** An untracked trigger starting around 13:45Z (refund volume or retry storm, feature flag, library or infrastructure change) causes refund connections to be held longer, and the leak is the mechanism that exhausts the pool. Mechanism: A load or configuration change not in the change inventory increases refund-path holding time or concurrency around 13:45Z. Connections held >30s accumulate in the pool, utilisation rises from 13:49Z, and the pool is exhausted by 14:00Z, which causes acquire timeouts and the 5xx and latency step. The trigger is not visible in the deployment or config inventory for payment-service or its dependencies.

Confidence breakdown: base 0.10; +0.08 corroboration across >=2 independent source types; +0.28 supporting evidence (3 refs, reliability-weighted, capped); -0.10 contradicting evidence (2 refs, capped 0.45); +0.08 proposed cause (13:45) precedes/coincides with first observed anomaly (13:49); -0.08 4 acknowledged evidence gaps; -0.05 critic review adjustment; = 0.23 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-payment-service-9d1f3d29` (moderate): 6x WARN on payment-service: 'HikariPool-payment - Connection leak detection triggered for connection conn-63, held > 30000 ms by RefundService.processPartialRefund' (first 2026-09-02T13:50:46Z, last 2026-09-02T14:00:16Z)
- [OBSERVED EVIDENCE] `met-payment-service-request_rate-1330-1400` (weak): payment-service request_rate: baseline 302.3 -> window mean 299.31 (max 330.9, change -1.0%), onset none detected
- [CONFIRMED FACT] `dep-d757f128` (weak): Deployment of notification-service 3.4.0->3.4.1 at 2026-09-02T13:54:00Z (SUCCEEDED): Update email templates for receipts

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-payment-service-request_rate-1330-1400` (weak): payment-service request_rate: baseline 302.3 -> window mean 299.31 (max 330.9, change -1.0%), onset none detected
- [CONFIRMED FACT] `cfg-fbdeed15` (weak): Config change on api-gateway: routes.cache_ttl_s 30 -> 60 at 2026-09-02T11:00:00Z (OPS-2497)

Remaining uncertainties / missing evidence:
- [UNKNOWN] Refund volume and retry metrics, and feature-flag state for payment-service.
- [UNKNOWN] Infrastructure or scaling events (autoscaling, node or DB events) for payment-service.
- [UNKNOWN] Library or runtime changes that are outside the deployment inventory.
- [UNKNOWN] Deployments before 13:00Z that may have rolled out gradually.

### 3. H3 - `upstream_dependency_degradation` in `postgres` (confidence 0.00, critic: reject)
**INFERENCE:** Long-running report_rollup() statements on the shared postgres server (from 13:31Z) saturate connections or locks, slowing payment-service database calls and causing the 14:00Z timeout step. Kept as a low-ranked alternative because the mechanism is untested. Mechanism: report_rollup() runs for 11-19s, starting 13:31Z, and may hold locks or connections on postgres. Payment queries wait, pool connections are held longer, and the pool saturates at 14:00Z.

Confidence breakdown: base 0.10; +0.08 corroboration across >=2 independent source types; +0.24 supporting evidence (2 refs, reliability-weighted, capped); -0.45 contradicting evidence (4 refs, capped 0.45); +0.08 proposed cause (13:31) precedes/coincides with first observed anomaly (13:49); -0.04 2 acknowledged evidence gaps; -0.40 critic review adjustment; = 0.00 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-postgres-44883ca5` (moderate): 7x WARN on postgres: 'duration: 18302 ms statement: SELECT report_rollup()' (first 2026-09-02T13:31:28Z, last 2026-09-02T14:23:09Z)
- [OBSERVED EVIDENCE] `met-postgres-db_conn_util_pct-1330-1425` (weak): postgres db_conn_util_pct: baseline 40.59 -> window mean 53.15 (max 67.91, change 31.0%), onset 2026-09-02T13:55:00Z

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-postgres-p95_latency_ms-1330-1425` (strong): postgres p95_latency_ms: baseline 11.98 -> window mean 12.06 (max 12.83, change 0.7%), onset none detected
- [OBSERVED EVIDENCE] `met-postgres-cpu_pct-1330-1425` (moderate): postgres cpu_pct: baseline 34.63 -> window mean 34.97 (max 38.3, change 1.0%), onset none detected
- [OBSERVED EVIDENCE] `met-payment-service-db_conn_util_pct-1330-1410` (strong): payment-service db_conn_util_pct: baseline 34.95 -> window mean 62.78 (max 100.0, change 79.7%), onset 2026-09-02T13:49:00Z
- [OBSERVED EVIDENCE] `met-redis-p95_latency_ms-1330-1425` (moderate): redis p95_latency_ms: baseline 1.49 -> window mean 1.5 (max 1.61, change 0.8%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Lock-wait and active-query counts on postgres.
- [UNKNOWN] Whether report_rollup() touches the tables that payment-service uses (no graph path, so the link is unverified).

## Critic Review
- **Verdict:** `NEEDS_MORE_EVIDENCE` (rounds reviewed: 3)
- **Reasoning:** Payment-service connection-pool exhaustion is the well-supported category: pool utilisation rises from 13:49Z (35% baseline to 96% at 14:00 and 100% at 14:05), acquire timeouts with active=50/idle=0/waiting=46 start at 14:00:16Z, and timeout rate and P95/error rate step at 14:00. Postgres CPU, P95 and Redis are flat, and the postgres connection step (13:55Z) follows the payment-side rise, so H3 is weakened. Leak-detection WARNs attributed to RefundService.processPartialRefund start at 13:45:08Z (I re-queried: 9 records, 13:45:08Z to 14:00:16Z), which precedes the pool rise. The only deployment in the window (notification-service, 13:54Z) is after onset. However, the holder attribution for H1 is not yet established: only 9 connections were flagged as held >30s, while exhaustion requires ~50 active connections held. Refund-held connections therefore account for at most a fraction of the saturated pool unless the leak warnings are sampled, and this is the key gap. The refund-path culprit is plausible but not proven as the majority holder.
- H1: **needs_evidence** - Timing is consistent (refund leak WARNs 13:45:08Z precede pool rise at 13:49Z and saturation at 14:00Z) and the pool-side saturation is directly observed. But only 9 long-held connections are logged against ~50 active connections, so the claim that refund holds drive the saturation is not shown. Needs holder attribution (thread dump or HikariPool diagnostics) or refund-call concurrency/retry counts over 13:30-14:05Z to show refund share of the pool.
- H2: **needs_evidence** - No trigger is identified. Request rate is flat, and the only deployment and config change in the window are off the payment path, so an untracked trigger is possible but unsupported. Needs feature-flag and infra event checks for payment-service between 12:00Z and 14:00Z before it can be weighed against H1.
- H3: **reject** - Postgres p95 (+0.7%) and CPU (+1.0%) are flat despite slow report_rollup statements, and auth-service sharing postgres is unaffected. Payment-side pool utilisation rose at 13:49Z, before the postgres connection step at 13:55Z, so postgres cannot be the first cause. Only lock-wait data could revive it, and the existing evidence argues against it.
- alternative: Refund-related connection holds from a refund volume or retry surge (H2) that is not captured in deployments or config.
- alternative: Non-refund callers holding connections, with the refund leak as a minor contributor (the 9 leak WARNs cannot account for a fully saturated 50-connection pool).
- alternative: Sampling or logging bias in leak-detection WARNs (they may fire once per connection, undercounting long holds).

## Probable Root Cause
MOST PROBABLE EXPLANATION (INFERENCE, not confirmed): db_connection_pool_exhaustion in payment-service - A connection leak or long hold in RefundService.processPartialRefund consumes payment-db-pool connections, saturating the pool and causing acquire timeouts, 5xx and latency at 14:00Z.

## Corrective Actions
- Mitigate the pool saturation on payment-service now: restart or drain affected payment-service instances to release held connections, and monitor whether pool utilisation falls and timeouts stop.
- Temporarily reduce or pause refund processing (RefundService.processPartialRefund) to stop new long-held connections, accepting the business impact on partial refunds, until the hold path is understood.
- Consider a temporary increase in payment-db-pool max size or acquire timeout only if the database has headroom, as a short-term buffer. This does not fix the holding behaviour.
- Confirm recovery by checking that timeout_rate and error_rate return to baseline (~0.1% and ~0.8%) and P95 latency returns to ~150 ms (met-payment-service-p95_latency_ms-1330-1430).

## Preventive Actions
- Fix the connection hold or leak in RefundService.processPartialRefund: ensure connections are always released (try-with-resources or finally blocks), and keep transactions short with no external calls while a connection is held.
- Set a server-side statement or transaction timeout and a connection maximum lifetime so that no single connection can be held indefinitely.
- Add per-caller connection attribution to the pool (for example, tagging acquisitions by call site) so the share of pool connections held by each code path is directly measurable.
- Review whether refund volume or retry behaviour changed around 13:45Z, since an untracked trigger (H2) remains possible.

## Monitoring Recommendations
- Alert on payment-db-pool utilisation above 80% for more than 2 minutes, and on any pool acquire timeout (the 5000 ms ERROR, active=50 idle=0 waiting>0 pattern).
- Alert on HikariPool leak-detection WARNs for payment-service, and count them per minute. Note that warnings may undercount long holds, so pair them with a pool-held-time metric.
- Track the payment-service timeout_rate, error_rate and P95 latency with alerts at the existing thresholds, and watch api-gateway latency for propagation.
- Record pool utilisation at 1-minute granularity (the investigation lacked this for the 13:45-13:55Z ramp) and track refund request volume and retry counts alongside request rate.
- Keep postgres CPU, P95 latency and connection utilisation on dashboards to confirm the database is not the constraint (current data shows it flat).

## Evidence Gaps
- none recorded

## Limitations
- Holder attribution is unproven: only 9 leak-detection warnings were found, while saturating a 50-connection pool implies many more held connections. The refund path may be a partial contributor.
- Leak warnings may be sampled or emitted once per connection, so they may undercount long holds.
- Pool utilisation was not available at 1-minute granularity for the 13:45-13:55Z ramp, so the onset timing is approximate.
- Refund request volume and retry counts were not measured, so the statement that refund share was flat is unverified. Flat total request rate does not rule out a shift in refund traffic (H2).
- The postgres connection step at 13:55Z follows the payment-side rise, so it is treated as a consequence rather than a cause. H3 was rejected on the available evidence but its mechanism was not directly tested.
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: critic verdict NEEDS_MORE_EVIDENCE; maximum investigation rounds (3) reached

## Final Status
`PROBABLE_ROOT_CAUSE`

The most probable root cause is connection-pool exhaustion on payment-service, with long holds or leaks in RefundService.processPartialRefund as the leading mechanism. This is a PROBABLE_ROOT_CAUSE finding, not a confirmed one. The evidence supports the pool saturation, the timeout step at 14:00:16Z, and the propagation to api-gateway. It does not yet show that refund-held connections make up the majority of the 50 active connections, since only nine leak warnings were recorded. Postgres and Redis were ruled out as the primary constraint, and the notification-service deployment at 13:54Z followed the onset. Immediate mitigation should restore pool capacity and pause refund holds. Closing the holder-attribution gap should be the priority follow-up before the case is treated as confirmed.

## Execution Statistics
```json
{
  "rounds": 3,
  "tool_calls": 43,
  "tool_failures": 0,
  "tool_retries": 0,
  "partial_results": 0,
  "agent_failures": 0,
  "agent_retries": 0,
  "invalid_llm_outputs": 2,
  "messages_exchanged": 48,
  "evidence_records": 74,
  "duration_s": 180.78,
  "tokens": {
    "input_tokens": 92,
    "output_tokens": 51813,
    "cache_read_tokens": 101985,
    "cache_write_tokens": 142305,
    "llm_calls": 31,
    "cost_usd": 0.04472367500000001
  },
  "tokens_by_agent": {
    "orchestrator": {
      "input_tokens": 6,
      "output_tokens": 948,
      "cache_read_tokens": 2666,
      "cache_write_tokens": 605,
      "llm_calls": 2,
      "cost_usd": 0.000576885
    },
    "dependency": {
      "input_tokens": 12,
      "output_tokens": 4331,
      "cache_read_tokens": 6972,
      "cache_write_tokens": 9115,
      "llm_calls": 4,
      "cost_usd": 0.003375795
    },
    "observability": {
      "input_tokens": 34,
      "output_tokens": 14682,
      "cache_read_tokens": 29236,
      "cache_write_tokens": 37808,
      "llm_calls": 12,
      "cost_usd": 0.012362759999999999
    },
    "reasoning": {
      "input_tokens": 16,
      "output_tokens": 20701,
      "cache_read_tokens": 26248,
      "cache_write_tokens": 54629,
      "llm_calls": 5,
      "cost_usd": 0.017443205
    },
    "critic": {
      "input_tokens": 20,
      "output_tokens": 8932,
      "cache_read_tokens": 36863,
      "cache_write_tokens": 36205,
      "llm_calls": 7,
      "cost_usd": 0.009362255
    },
    "reporting": {
      "input_tokens": 4,
      "output_tokens": 2219,
      "cache_read_tokens": 0,
      "cache_write_tokens": 3943,
      "llm_calls": 1,
      "cost_usd": 0.001602775
    }
  }
}
```
