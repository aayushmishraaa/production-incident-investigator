# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-012
- **Title:** Payment connection pool timeouts
- **Severity:** SEV2
- **Affected services:** payment-service
- **Start time:** 2026-10-05T10:10:00+00:00
- **Investigation ID:** inv-bed276c6ef (multi_agent)
- **Final status:** `ROOT_CAUSE_IDENTIFIED`

## Executive Summary
INC-012 (SEV2) affected payment-service, with elevated latency and errors and log entries reporting connection pool timeouts, beginning around 10:04-10:06Z on 2026-10-05. The investigation status is ROOT_CAUSE_IDENTIFIED. The leading hypothesis (H1, confidence 0.85, critic-approved) is a configuration regression: change cfg-56d39584 (OPS-2669) reduced payment-service db.pool.max_size from 50 to 10 at 10:04:00Z (cfg-56d39584). A runtime reload record confirms the new cap was applied at the same instant. Pool-acquire timeouts ("Timeout acquiring connection from pool payment-db-pool after 5000ms", active=10, idle=0) first appear at 10:06:13Z, 29 times through 10:34:18Z (logpat-payment-service-7d1739af). Payment timeout rate rose from a baseline of 0.1 to a window mean of 6.3, and error rate from 0.8 to 9.17 (met-payment-service-timeout_rate-0940-1035, met-payment-service-error_rate-0940-1035). Request rate was flat (about 300 req/s), so the change in capacity, not a change in load, is the most probable explanation. This is not a confirmed fact. The symptoms resemble last year's pool exhaustion, but the evidence points away from a database-side cause (H3 rejected). The mechanism is consistent with the observed data, not independently proven at every instance.

## Incident Timeline
| Time (UTC) | Label | Event | Evidence |
|---|---|---|---|
| 2026-10-05T09:45:26Z | OBSERVED EVIDENCE | First log: 7x WARN on payment-service: 'Card network soft decline (code 05) for charge ch_98' (first 2026-10-05T09:45:26Z, last 2026-10-05T10:22:54Z) | logpat-payment-service-7e9bf84f |
| 2026-10-05T10:04:00Z | CONFIRMED FACT | Config change on payment-service: db.pool.max_size 50 -> 10 at 2026-10-05T10:04:00Z (OPS-2669) | cfg-56d39584 |
| 2026-10-05T10:05:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service db_conn_util_pct: baseline 34.95 -> window mean 69.43 (max 100.0, change 98.7%), onset 2026-10-05T10:05:00Z | met-payment-service-db_conn_util_pct-0940-1035 |
| 2026-10-05T10:06:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service error_rate: baseline 0.8 -> window mean 9.17 (max 18.85, change 1040.5%), onset 2026-10-05T10:06:00Z | met-payment-service-error_rate-0940-1035 |
| 2026-10-05T10:06:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service timeout_rate: baseline 0.1 -> window mean 6.3 (max 13.3, change 6147.1%), onset 2026-10-05T10:06:00Z | met-payment-service-timeout_rate-0940-1035 |
| 2026-10-05T10:06:13Z | OBSERVED EVIDENCE | First log: 29x ERROR on payment-service: 'Timeout acquiring connection from pool payment-db-pool after 5000ms (active=10, idle=0, waiting=29)' (first 2026-10-05T10:06:13Z, last 2026-10-05T10:34:18Z) | logpat-payment-service-7d1739af |
| 2026-10-05T10:10:00Z | CONFIRMED FACT | Reported symptom start |  |
| 2026-10-05T10:16:00Z | CONFIRMED FACT | Incident reported |  |

## Observed Symptoms
- **OBSERVED EVIDENCE:** payment-service error_rate: baseline 0.8 -> window mean 9.17 (max 18.85, change 1040.5%), onset 2026-10-05T10:06:00Z (met-payment-service-error_rate-0940-1035)
- **OBSERVED EVIDENCE:** payment-service db_conn_util_pct: baseline 34.95 -> window mean 69.43 (max 100.0, change 98.7%), onset 2026-10-05T10:05:00Z (met-payment-service-db_conn_util_pct-0940-1035)
- **OBSERVED EVIDENCE:** payment-service timeout_rate: baseline 0.1 -> window mean 6.3 (max 13.3, change 6147.1%), onset 2026-10-05T10:06:00Z (met-payment-service-timeout_rate-0940-1035)
- **OBSERVED EVIDENCE:** [observability] Redis p99 latency flat across 09:40-10:35 (window mean 2.99ms vs baseline 3.0ms, change -0.3%, no onset detected). Sampled values stay ~2.7-3.4ms around T0. (met-redis-p99_latency_ms-0940-1035)
- **OBSERVED EVIDENCE:** [observability] Redis request_rate (-0.5%), cpu_pct (-0.7%, ~15%) and error_rate (~0.01%) show no change versus baseline; no onset detected. (met-redis-request_rate-0940-1035, met-redis-cpu_pct-0940-1035, met-redis-error_rate-0940-1035)
- **OBSERVED EVIDENCE:** [observability] api-gateway error_rate (0.5% vs 0.5%, +0.9%), timeout_rate (0.1% vs 0.1%, +0.2%), p99 latency (~249ms vs 249ms, +0.2%) and request_rate (+0.8%) are flat across the window; no onset detected around T0. Gateway-level upstream timeouts to payment-service are not elevated in aggregate. (met-api-gateway-error_rate-0940-1035, met-api-gateway-timeout_rate-0940-1035, met-api-gateway-p99_latency_ms-0940-1035, met-api-gateway-request_rate-0940-1035)
- **OBSERVED EVIDENCE:** [observability] order-service error_rate (0.6% vs 0.6%, -0.5%), timeout_rate (0.1%, -0.1%), p99 latency (~399ms vs 403ms, -0.9%) and request_rate (-1.0%) show no change; no onset detected. No retry metric is available. (met-order-service-error_rate-0940-1035, met-order-service-timeout_rate-0940-1035, met-order-service-p99_latency_ms-0940-1035, met-order-service-request_rate-0940-1035)
- **OBSERVED EVIDENCE:** [dependency] Config change cfg-56d39584 (author config-bot, ticket OPS-2669) changed payment-service db.pool.max_size from 50 to 10 (ratio 0.2) at 10:04Z, six minutes before T0. (cfg-56d39584)
- **OBSERVED EVIDENCE:** [dependency] db_conn_util_pct rose from baseline mean ~35% to 63% at 10:05 and reached 93-100% from 10:10 onward. Onset detected 10:05Z. (met-payment-service-db_conn_util_pct-0940-1035)
- **OBSERVED EVIDENCE:** [dependency] timeout_rate jumped from ~0.1% to ~11-13% starting 10:06-10:10; error_rate went from ~0.8% to ~17%, onset 10:06Z. (met-payment-service-timeout_rate-0940-1035, met-payment-service-error_rate-0940-1035)
- **OBSERVED EVIDENCE:** [dependency] p99 latency was essentially flat (baseline 299ms vs window 301ms), with no detected onset. Latency did not rise as the pool/timeout symptoms did. (met-payment-service-p99_latency_ms-0940-1035)
- **OBSERVED EVIDENCE:** [dependency] Dependency graph (topology-v2) shows payment-service upstream of auth-service, postgres and redis; downstream callers are api-gateway and order-service. No topology changes recorded. (topo-payment-service-both-d2)
- **INFERENCE:** [dependency] Possible explanation: the OPS-2669 pool max_size reduction (50->10) introduced at 10:04Z reduced available DB connections and caused pool-timeouts. Alternative (not ruled out): a load increase or downstream slowness that the pool change merely exposed; request_rate was not checked. (cfg-56d39584)
- **OBSERVED EVIDENCE:** [dependency] Dependency graph (topology-v2): payment-service's direct downstream callers are api-gateway and order-service; its upstream dependencies are auth-service, postgres and redis. No topology changes recorded for payment-service. (topo-payment-service-both-d3)
- **OBSERVED EVIDENCE:** [dependency] Config change cfg-56d39584 at 2026-10-05T10:04:00Z (author config-bot, ticket OPS-2669) reduced db.pool.max_size from 50 to 10 (ratio 0.2) on payment-service. This is 6 minutes before T0 and is the only config change in the 08:40-10:35 window across all services queried. (cfg-56d39584)
- **OBSERVED EVIDENCE:** [dependency] api-gateway calls payment-service directly and also indirectly via order-service (api-gateway -> order-service -> payment-service). Its downstream dependents list is empty, so blast radius from api-gateway is its own traffic only. No config or topology changes for api-gateway in the window. (topo-api-gateway-both-d2)
- **OBSERVED EVIDENCE:** [dependency] order-service calls payment-service directly (order-service -> payment-service) and is called only by api-gateway. Topology change: order-service -> redis edge added effective 2026-09-15, well before the incident. No config changes for order-service in the window. (topo-order-service-both-d2)
- **INFERENCE:** [dependency] The 50->10 pool reduction at 10:04Z could cause connection pool timeouts in payment-service, with callers seeing elevated latency/errors; this is a correlation only and needs metric confirmation of onset relative to 10:04Z. (cfg-56d39584)
- **OBSERVED EVIDENCE:** [observability] payment-service error_rate onset at 10:06 (baseline mean 0.8% -> window mean 9.17%, max 18.85%); step to ~17% at the 10:10 sample and sustained through 10:35. (met-payment-service-error_rate-0940-1035)
- **OBSERVED EVIDENCE:** [observability] payment-service timeout_rate onset at 10:06 (baseline 0.1% -> window mean 6.3%, max 13.3%), sustained through the window. (met-payment-service-timeout_rate-0940-1035)
- **OBSERVED EVIDENCE:** [observability] payment-service db_conn_util_pct onset at 10:05 (baseline 34.95% -> 63% at 10:05, 94% at 10:10, reaching 100% at 10:20 and 10:30); window mean 69.4%. (met-payment-service-db_conn_util_pct-0940-1035)
- **OBSERVED EVIDENCE:** [observability] Repeated ERROR 'Timeout acquiring connection from pool payment-db-pool after 5000ms (active=10, idle=0, waiting=N)' — 29 occurrences from 10:06:13 to 10:34:18, waiting queue ranging ~15 to 92 across samples; active is pinned at 10 with 0 idle. (logpat-payment-service-7d1739af, log-945fe4b3, log-41cefacf, log-eaa111fa)
- **OBSERVED EVIDENCE:** [observability] payment-service p99 latency is flat versus baseline (299 ms -> 301 ms, +0.6%), request rate flat (300 -> 299 req/s), CPU flat (40% -> 40%). Error/timeout rise is not accompanied by p99 change in the aggregate. (met-payment-service-p99_latency_ms-0940-1035, met-payment-service-request_rate-0940-1035, met-payment-service-cpu_pct-0940-1035)
- **OBSERVED EVIDENCE:** [observability] postgres db_conn_util_pct DROPS at 10:07 (baseline mean 39.8% -> window mean 30.6%, ~22% from 10:10 onward), i.e. opposite direction to payment-service pool utilisation during the same period. (met-postgres-db_conn_util_pct-0940-1035)
- **OBSERVED EVIDENCE:** [observability] postgres p99 query latency (25.2 ms vs 25.2 ms baseline), CPU (35% vs 35%) and disk_io_wait (2.0 ms vs 2.0 ms) show no change in the window. (met-postgres-p99_latency_ms-0940-1035, met-postgres-cpu_pct-0940-1035, met-postgres-disk_io_wait_ms-0940-1035)
- **ASSUMPTION:** [critic: unsupported assumption] That the reload log covers every payment-service instance (only one reload record was seen). 
- **ASSUMPTION:** [critic: unsupported assumption] That failing requests are excluded from the p99 latency measure, which explains the flat latency. 

## Investigation Performed
- Round 1 | observability | completed | attempts 1 | 4 tool calls | Characterize payment-service connection pool timeouts, latency, and error rates from 2026-10-05T10:00Z onward. Determine pool saturation metrics and DB connecti
- Round 1 | observability | completed | attempts 1 | 4 tool calls | Check redis and upstream/downstream callers for correlated anomalies starting around 2026-10-05T10:10:00Z.
- Round 1 | dependency | completed | attempts 1 | 4 tool calls | Identify deployments, config changes, or feature flag/pool-size changes to payment-service and its dependencies in the window 2026-10-05T08:00Z to 10:16Z.
- Round 1 | dependency | completed | attempts 1 | 7 tool calls | Map the call graph for api-gateway and order-service to confirm blast radius and any retry amplification paths into payment-service.
- Round 1 | reasoning | completed | attempts 1 | 0 tool calls | Develop and rank competing hypotheses
- Round 1 | critic | completed | attempts 1 | 3 tool calls | Independently review hypotheses
- Round 1 | reporting | completed | attempts 1 | 0 tool calls | Write final report

## Root-Cause Hypotheses (ranked by evidence strength)
### 1. H1 - `configuration_regression` in `payment-service` (confidence 0.85, critic: accept)
**INFERENCE:** Config change cfg-56d39584 (OPS-2669) reduced payment-service db.pool.max_size from 50 to 10 at 10:04Z, starving the payment-db-pool under normal load and causing pool-acquire timeouts, errors and timeouts. Mechanism: max_size cut 50->10 (80% reduction) -> pool active pinned at 10 with idle=0 -> requests queue for connections -> acquire waits hit the 5000ms timeout -> ERROR 'Timeout acquiring connection' logs, timeout_rate ~0.1%->~12%, error_rate ~0.8%->~17%. The same cap explains the postgres-side connection utilisation falling ~22% from 10:07: payment-service now holds at most 10 DB connections instead of up to 50. Request rate is flat, so the reduced capacity alone is sufficient without any load change.

Confidence breakdown: base 0.10; +0.08 corroboration across >=2 independent source types; +0.78 supporting evidence (9 refs, reliability-weighted, capped); -0.10 contradicting evidence (2 refs, capped 0.45); +0.08 proposed cause (10:04) precedes/coincides with first observed anomaly (10:05); -0.06 3 acknowledged evidence gaps; +0.05 critic review adjustment; = 0.85 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [CONFIRMED FACT] `cfg-56d39584` (strong): Config change on payment-service: db.pool.max_size 50 -> 10 at 2026-10-05T10:04:00Z (OPS-2669)
- [OBSERVED EVIDENCE] `logpat-payment-service-7d1739af` (strong): 29x ERROR on payment-service: 'Timeout acquiring connection from pool payment-db-pool after 5000ms (active=10, idle=0, waiting=29)' (first 2026-10-05T10:06:13Z, last 2026-10-05T10:34:18Z)
- [OBSERVED EVIDENCE] `met-payment-service-db_conn_util_pct-0940-1035` (moderate): payment-service db_conn_util_pct: baseline 34.95 -> window mean 69.43 (max 100.0, change 98.7%), onset 2026-10-05T10:05:00Z
- [OBSERVED EVIDENCE] `met-payment-service-timeout_rate-0940-1035` (moderate): payment-service timeout_rate: baseline 0.1 -> window mean 6.3 (max 13.3, change 6147.1%), onset 2026-10-05T10:06:00Z
- [OBSERVED EVIDENCE] `met-payment-service-error_rate-0940-1035` (moderate): payment-service error_rate: baseline 0.8 -> window mean 9.17 (max 18.85, change 1040.5%), onset 2026-10-05T10:06:00Z
- [OBSERVED EVIDENCE] `met-postgres-db_conn_util_pct-0940-1035` (moderate): postgres db_conn_util_pct: baseline 39.83 -> window mean 30.56 (max 43.9, change -23.3%), onset 2026-10-05T10:07:00Z
- [OBSERVED EVIDENCE] `met-payment-service-request_rate-0940-1035` (moderate): payment-service request_rate: baseline 300.21 -> window mean 299.16 (max 325.13, change -0.4%), onset none detected
- [OBSERVED EVIDENCE] `met-postgres-p99_latency_ms-0940-1035` (moderate): postgres p99_latency_ms: baseline 25.15 -> window mean 25.13 (max 27.03, change -0.1%), onset none detected
- [OBSERVED EVIDENCE] `met-auth-service-error_rate-0940-1035` (weak): auth-service error_rate: baseline 0.3 -> window mean 0.3 (max 0.33, change 0.6%), onset none detected

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-payment-service-p99_latency_ms-0940-1035` (weak): payment-service p99_latency_ms: baseline 299.15 -> window mean 300.84 (max 325.6, change 0.6%), onset none detected
- [OBSERVED EVIDENCE] `met-payment-service-db_conn_util_pct-0940-1035` (weak): payment-service db_conn_util_pct: baseline 34.95 -> window mean 69.43 (max 100.0, change 98.7%), onset 2026-10-05T10:05:00Z

Remaining uncertainties / missing evidence:
- [UNKNOWN] Confirmation that cfg-56d39584 is applied on all payment-service instances (and that the running pool max is 10).
- [UNKNOWN] Direct pool gauges (max, active, idle, wait) and acquire-time histograms.
- [UNKNOWN] Whether any other config changed on payment-service or its dependencies, since config queries were not filtered per service.

### 2. H2 - `unknown` in `payment-service` (confidence 0.00, critic: reject)
**INFERENCE:** A pool-internal fault, such as connection leak or long-held connections (for example a stuck transaction or missing release in the payment code path), exhausted the pool. The 50->10 change is coincident, or merely exposed the problem. Mechanism: Connections are acquired and not returned, or held for long periods, so the pool fills regardless of DB-side load -> active pinned at max -> waiting queue grows -> acquire timeouts. The DB-side connection count falls because the leaked connections are held in the app, not executing queries, so DB load stays flat.

Confidence breakdown: base 0.10; +0.08 corroboration across >=2 independent source types; +0.36 supporting evidence (3 refs, reliability-weighted, capped); -0.20 contradicting evidence (2 refs, capped 0.45); +0.08 proposed cause (10:04) precedes/coincides with first observed anomaly (10:05); -0.04 2 acknowledged evidence gaps; -0.40 critic review adjustment; = 0.00 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-payment-service-7d1739af` (moderate): 29x ERROR on payment-service: 'Timeout acquiring connection from pool payment-db-pool after 5000ms (active=10, idle=0, waiting=29)' (first 2026-10-05T10:06:13Z, last 2026-10-05T10:34:18Z)
- [OBSERVED EVIDENCE] `met-postgres-db_conn_util_pct-0940-1035` (moderate): postgres db_conn_util_pct: baseline 39.83 -> window mean 30.56 (max 43.9, change -23.3%), onset 2026-10-05T10:07:00Z
- [OBSERVED EVIDENCE] `met-postgres-p99_latency_ms-0940-1035` (weak): postgres p99_latency_ms: baseline 25.15 -> window mean 25.13 (max 27.03, change -0.1%), onset none detected

Contradicting evidence:
- [CONFIRMED FACT] `cfg-56d39584` (moderate): Config change on payment-service: db.pool.max_size 50 -> 10 at 2026-10-05T10:04:00Z (OPS-2669)
- [OBSERVED EVIDENCE] `met-payment-service-db_conn_util_pct-0940-1035` (weak): payment-service db_conn_util_pct: baseline 34.95 -> window mean 69.43 (max 100.0, change 98.7%), onset 2026-10-05T10:05:00Z

Remaining uncertainties / missing evidence:
- [UNKNOWN] No code or deploy change was found, and no leak-specific metric (connection lifetime, checkout duration per call site) was collected.
- [UNKNOWN] No evidence of a pre-10:04 pool-utilisation drift that would indicate a slow leak.

### 3. H3 - `db_connection_pool_exhaustion` in `postgres` (confidence 0.00, critic: reject)
**INFERENCE:** Last year's pattern: postgres-side saturation or slowness causes connections to be held longer, exhausting the payment pool. The hypothesis is weakened by current telemetry. Mechanism: Postgres slowdown -> queries hold connections longer -> payment pool fills -> acquire timeouts. The reverse would be needed for the observed data.

Confidence breakdown: base 0.10; +0.04 supporting evidence (1 refs, reliability-weighted, capped); -0.45 contradicting evidence (4 refs, capped 0.45); +0.08 proposed cause (10:05) precedes/coincides with first observed anomaly (10:05); -0.02 1 acknowledged evidence gaps; -0.40 critic review adjustment; = 0.00 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [OBSERVED EVIDENCE] `met-payment-service-db_conn_util_pct-0940-1035` (weak): payment-service db_conn_util_pct: baseline 34.95 -> window mean 69.43 (max 100.0, change 98.7%), onset 2026-10-05T10:05:00Z

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-postgres-p99_latency_ms-0940-1035` (strong): postgres p99_latency_ms: baseline 25.15 -> window mean 25.13 (max 27.03, change -0.1%), onset none detected
- [OBSERVED EVIDENCE] `met-postgres-cpu_pct-0940-1035` (strong): postgres cpu_pct: baseline 35.02 -> window mean 35.11 (max 37.77, change 0.3%), onset none detected
- [OBSERVED EVIDENCE] `met-postgres-disk_io_wait_ms-0940-1035` (moderate): postgres disk_io_wait_ms: baseline 2.01 -> window mean 2.01 (max 2.23, change -0.3%), onset none detected
- [OBSERVED EVIDENCE] `met-postgres-db_conn_util_pct-0940-1035` (strong): postgres db_conn_util_pct: baseline 39.83 -> window mean 30.56 (max 43.9, change -23.3%), onset 2026-10-05T10:07:00Z

Remaining uncertainties / missing evidence:
- [UNKNOWN] Postgres ERROR/WARN logs and active-query/lock breakdown per database were not checked.

### 4. H4 - `traffic_surge` in `api-gateway` (confidence 0.00, critic: reject)
**INFERENCE:** Traffic amplification (retries from api-gateway or order-service) multiplies load on the payment pool, causing saturation. Callers could not be checked for retry configuration. Mechanism: Client retries via api-gateway and order-service multiply calls to payment-service -> the pool (max 10) is overwhelmed -> timeouts -> more retries. This requires a load increase at payment-service, or a retry-policy change.

Confidence breakdown: base 0.10; +0.04 supporting evidence (1 refs, reliability-weighted, capped); -0.45 contradicting evidence (4 refs, capped 0.45); +0.08 proposed cause (10:05) precedes/coincides with first observed anomaly (10:05); -0.02 1 acknowledged evidence gaps; -0.40 critic review adjustment; = 0.00 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [CONFIRMED FACT] `topo-api-gateway-both-d2` (weak): api-gateway depends on ['auth-service', 'order-service', 'payment-service', 'user-service']; called by [] (graph topology-v2)

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-payment-service-request_rate-0940-1035` (strong): payment-service request_rate: baseline 300.21 -> window mean 299.16 (max 325.13, change -0.4%), onset none detected
- [OBSERVED EVIDENCE] `met-api-gateway-request_rate-0940-1035` (moderate): api-gateway request_rate: baseline 1192.84 -> window mean 1202.52 (max 1292.55, change 0.8%), onset none detected
- [OBSERVED EVIDENCE] `met-order-service-request_rate-0940-1035` (moderate): order-service request_rate: baseline 251.59 -> window mean 249.17 (max 270.88, change -1.0%), onset none detected
- [OBSERVED EVIDENCE] `met-order-service-timeout_rate-0940-1035` (weak): order-service timeout_rate: baseline 0.1 -> window mean 0.1 (max 0.11, change -0.1%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Retry and timeout configuration on api-gateway and order-service calls to payment-service (current values unknown).

## Critic Review
- **Verdict:** `APPROVED` (rounds reviewed: 1)
- **Reasoning:** H1 is well supported. The config change cfg-56d39584 (db.pool.max_size 50->10, OPS-2669) is confirmed at 10:04:00Z, and a runtime 'Configuration reloaded: db.pool.max_size=10 (version 77)' INFO log appears at the same instant, so the cap was applied at runtime. Pool-acquire timeout logs (active=10, idle=0, growing waiters) start at 10:06:13Z, and payment error and timeout rates step up at 10:06. Pool utilisation rises from 10:05. Request rate is flat (300->299 req/s), there is no deployment in the window, and the only payment-service config change in 09:00-10:40 is this one. Postgres latency, CPU and disk IO are flat, which rules out a DB-side saturation story. The 1-minute lead of pool utilisation over the error onset is a minor sampling detail. Limitations: the per-instance effective value was not checked beyond the reload log, and the log count in the summary (14 pattern matches vs 29 quoted) is a minor inconsistency that does not change the conclusion.
- H1: **accept** - Config change at 10:04:00Z is confirmed by both the change record and a runtime reload log at the same time. Timeouts start at 10:06 with the capped-pool signature (active=10, idle=0, waiting queue growing). Request rate is flat and no deployment or other config change is present, so reduced capacity is the most parsimonious cause. DB-side metrics are healthy.
- H2: **reject** - A leak would not explain the sudden onset at 10:06, which lines up with the cap cut. No leak-specific evidence was found, and the 50-cap pool was not shown to be saturating before 10:04. The cut alone is sufficient, so a leak is at most a secondary contributor that is not supported by the data.
- H3: **reject** - Postgres p99 latency (25.1ms vs 25.2ms), CPU (35%), and disk IO wait are flat, and Postgres connection utilisation falls about 23%. This contradicts a DB-side slowdown holding connections longer.
- H4: **reject** - Payment request rate is flat (-0.4%), gateway and order-service request rates are flat, and there is no order-service timeout increase. There is no sign of a traffic amplification or retry storm reaching payment-service.
- pre-check warning `culprit_symptom` on H3: no log/metric evidence cited for culprit postgres
- pre-check warning `single_source` on H3: all support comes from one source type (metric)
- pre-check warning `culprit_symptom` on H4: no log/metric evidence cited for culprit api-gateway
- pre-check warning `single_source` on H4: all support comes from one source type (dependency)
- alternative: Connection leak or long-held connections in payment code, triggered by or coincident with the cap cut (H2); not excluded by data, but not needed to explain the onset.
- alternative: Per-instance divergence: if only some payment-service instances received the new value, the impact would be partial; not verified beyond the reload log.

## Probable Root Cause
ROOT CAUSE IDENTIFIED (critic-approved; still an INFERENCE from evidence): configuration_regression in payment-service - Config change cfg-56d39584 (OPS-2669) reduced payment-service db.pool.max_size from 50 to 10 at 10:04Z, starving the payment-db-pool under normal load and causing pool-acquire timeouts, errors and timeouts.

## Corrective Actions
- Revert db.pool.max_size on payment-service from 10 to 50 (rollback of cfg-56d39584 / OPS-2669), and confirm the reload log shows the restored value on all instances.
- Verify per-instance effective pool size on every payment-service instance, since only one reload record was observed (cfg-56d39584).
- Confirm recovery: payment timeout_rate and error_rate return to baseline (about 0.1% and 0.8%) and pool-acquire timeout logs stop.

## Preventive Actions
- Require review and a load-test or capacity check for any change to database pool sizing, and flag reductions above a set threshold (for example, an 80% cut) for approval.
- Add config-change validation that compares pool settings with the previous value and with expected concurrency before rollout.
- Record the ticket-to-change link (OPS-2669) in the change log so that config changes are auditable against incidents.
- Investigate the unresolved possibility of a connection leak or long-held connections in the payment code path (H2), so that a future reduction in pool size does not cause an outage on its own.

## Monitoring Recommendations
- Alert on payment-db-pool active/max ratio sustained at or near 100% with idle=0 and waiting > 0 for more than 2 minutes.
- Alert on 'Timeout acquiring connection' log rate above zero for payment-service, and on payment timeout_rate and error_rate exceeding baseline by a set margin.
- Emit and dashboard the effective db.pool.max_size per instance at each config reload, and alert on any value change outside a change window.
- Track payment request rate alongside pool utilisation so that capacity-driven saturation can be distinguished from load-driven saturation.
- Monitor postgres connection counts from payment-service and p99 latency to detect any future database-side contribution.

## Evidence Gaps
- none recorded

## Limitations
- Only one runtime reload record was observed; the effective value on each payment-service instance was not independently verified.
- The connection-leak or long-held-connection hypothesis (H2) was not excluded by the data, though it is not needed to explain the onset.
- Flat p99 latency during the incident may partly reflect failed requests being excluded from the measure; this was assumed, not verified.
- The pool utilisation metric leads error onset by about one minute; this is treated as a sampling detail.
- Callers' retry configuration (api-gateway, order-service) could not be checked; traffic amplification was rejected based on flat request rates.
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: critic verdict APPROVED

## Final Status
`ROOT_CAUSE_IDENTIFIED`

The most probable root cause of INC-012 is the reduction of payment-service db.pool.max_size from 50 to 10 by change cfg-56d39584 (OPS-2669) at 10:04Z. With request rate flat, the reduced pool capacity alone is sufficient to explain the pool-acquire timeouts, elevated error and timeout rates, and the lower postgres connection utilisation. Database-side saturation and traffic surge were ruled out by the telemetry. Remaining uncertainties are whether every instance received the new value and whether a latent connection-holding issue exists in the payment code path. Reverting the change is the primary mitigation, and the preventive and monitoring actions aim to prevent a recurrence.

## Execution Statistics
```json
{
  "rounds": 1,
  "tool_calls": 23,
  "tool_failures": 0,
  "tool_retries": 0,
  "partial_results": 0,
  "agent_failures": 0,
  "agent_retries": 0,
  "invalid_llm_outputs": 0,
  "messages_exchanged": 20,
  "evidence_records": 54,
  "duration_s": 59.72,
  "tokens": {
    "input_tokens": 48,
    "output_tokens": 20587,
    "cache_read_tokens": 31954,
    "cache_write_tokens": 55843,
    "llm_calls": 16,
    "cost_usd": 0.017598215
  },
  "tokens_by_agent": {
    "orchestrator": {
      "input_tokens": 6,
      "output_tokens": 1005,
      "cache_read_tokens": 2989,
      "cache_write_tokens": 0,
      "llm_calls": 2,
      "cost_usd": 0.00053299
    },
    "dependency": {
      "input_tokens": 16,
      "output_tokens": 4990,
      "cache_read_tokens": 14292,
      "cache_write_tokens": 11008,
      "llm_calls": 6,
      "cost_usd": 0.00401552
    },
    "observability": {
      "input_tokens": 12,
      "output_tokens": 6560,
      "cache_read_tokens": 5767,
      "cache_write_tokens": 17774,
      "llm_calls": 4,
      "cost_usd": 0.00556062
    },
    "reasoning": {
      "input_tokens": 4,
      "output_tokens": 4482,
      "cache_read_tokens": 0,
      "cache_write_tokens": 11958,
      "llm_calls": 1,
      "cost_usd": 0.00373615
    },
    "critic": {
      "input_tokens": 6,
      "output_tokens": 1848,
      "cache_read_tokens": 8906,
      "cache_write_tokens": 11211,
      "llm_calls": 2,
      "cost_usd": 0.0024150350000000003
    },
    "reporting": {
      "input_tokens": 4,
      "output_tokens": 1702,
      "cache_read_tokens": 0,
      "cache_write_tokens": 3892,
      "llm_calls": 1,
      "cost_usd": 0.0013379000000000002
    }
  }
}
```
