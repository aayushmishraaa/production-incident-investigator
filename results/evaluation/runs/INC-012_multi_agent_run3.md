# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-012
- **Title:** Payment connection pool timeouts
- **Severity:** SEV2
- **Affected services:** payment-service
- **Start time:** 2026-10-05T10:10:00+00:00
- **Investigation ID:** inv-d4c4127aba (multi_agent)
- **Final status:** `ROOT_CAUSE_IDENTIFIED`

## Executive Summary
INC-012 (SEV2) affected payment-service between 10:10Z and the investigation window, with elevated API latency and errors and log entries reporting connection pool timeouts. Final status is ROOT_CAUSE_IDENTIFIED. The leading hypothesis (H1, confidence 0.95) is a configuration regression: change cfg-56d39584 (OPS-2669) reduced payment-service db.pool.max_size from 50 to 10 at 10:04:00Z (cfg-56d39584). Baseline pool use (roughly 17 connections) now exceeds the cap of 10, so requests queue and time out. Pool-acquire timeouts began at 10:06:13Z with active=10 idle=0 and a growing waiting queue (logpat-payment-service-7d1739af). Timeout rate rose from a baseline of 0.1 to a window mean of 6.3 and error rate from 0.8 to 9.17, both with onset at 10:06 (met-payment-service-timeout_rate-0940-1035, met-payment-service-error_rate-0940-1035). Pool utilization rose from 34.95 to 69.43 with onset at 10:05 (met-payment-service-db_conn_util_pct-0940-1035). Request rate was flat (300 vs 299 rps), so load did not change (met-payment-service-request_rate-0940-1035). The critic approved this finding. The explanation is the most probable cause, not a confirmed fact. Two items remain unverified: the intent of OPS-2669 and whether restoring 50 clears the saturation.

## Incident Timeline
| Time (UTC) | Label | Event | Evidence |
|---|---|---|---|
| 2026-10-05T09:44:02Z | OBSERVED EVIDENCE | First log: 5x WARN on api-gateway: 'Slow client upload from 10.4.85.12 (1.9MB)' (first 2026-10-05T09:44:02Z, last 2026-10-05T10:28:03Z) | logpat-api-gateway-88b04940 |
| 2026-10-05T09:45:26Z | OBSERVED EVIDENCE | First log: 7x WARN on payment-service: 'Card network soft decline (code 05) for charge ch_98' (first 2026-10-05T09:45:26Z, last 2026-10-05T10:22:54Z) | logpat-payment-service-7e9bf84f |
| 2026-10-05T10:01:25Z | OBSERVED EVIDENCE | First log: 4x WARN on postgres: 'duration: 15802 ms statement: SELECT report_rollup()' (first 2026-10-05T10:01:25Z, last 2026-10-05T10:24:50Z) | logpat-postgres-44883ca5 |
| 2026-10-05T10:04:00Z | CONFIRMED FACT | Config change on payment-service: db.pool.max_size 50 -> 10 at 2026-10-05T10:04:00Z (OPS-2669) | cfg-56d39584 |
| 2026-10-05T10:05:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service db_conn_util_pct: baseline 34.95 -> window mean 69.43 (max 100.0, change 98.7%), onset 2026-10-05T10:05:00Z | met-payment-service-db_conn_util_pct-0940-1035 |
| 2026-10-05T10:06:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service timeout_rate: baseline 0.1 -> window mean 6.3 (max 13.3, change 6147.1%), onset 2026-10-05T10:06:00Z | met-payment-service-timeout_rate-0940-1035 |
| 2026-10-05T10:06:00Z | OBSERVED EVIDENCE | Anomaly onset: payment-service error_rate: baseline 0.8 -> window mean 9.17 (max 18.85, change 1040.5%), onset 2026-10-05T10:06:00Z | met-payment-service-error_rate-0940-1035 |
| 2026-10-05T10:06:13Z | OBSERVED EVIDENCE | First log: 29x ERROR on payment-service: 'Timeout acquiring connection from pool payment-db-pool after 5000ms (active=10, idle=0, waiting=29)' (first 2026-10-05T10:06:13Z, last 2026-10-05T10:34:18Z) | logpat-payment-service-7d1739af |
| 2026-10-05T10:10:00Z | CONFIRMED FACT | Reported symptom start |  |
| 2026-10-05T10:16:00Z | CONFIRMED FACT | Incident reported |  |

## Observed Symptoms
- **OBSERVED EVIDENCE:** payment-service db_conn_util_pct: baseline 34.95 -> window mean 69.43 (max 100.0, change 98.7%), onset 2026-10-05T10:05:00Z (met-payment-service-db_conn_util_pct-0940-1035)
- **OBSERVED EVIDENCE:** payment-service timeout_rate: baseline 0.1 -> window mean 6.3 (max 13.3, change 6147.1%), onset 2026-10-05T10:06:00Z (met-payment-service-timeout_rate-0940-1035)
- **OBSERVED EVIDENCE:** payment-service error_rate: baseline 0.8 -> window mean 9.17 (max 18.85, change 1040.5%), onset 2026-10-05T10:06:00Z (met-payment-service-error_rate-0940-1035)
- **OBSERVED EVIDENCE:** [dependency] payment-service (topology-v2, no topology changes listed) has upstream dependencies auth-service, postgres and redis (chains via auth-service to postgres and redis). Its downstream dependents are api-gateway and order-service, both listed as potentially impacted. (topo-payment-service-both-d3)
- **OBSERVED EVIDENCE:** [dependency] Downstream query for api-gateway returned no downstream dependents and no potentially impacted services, so no transitive callers of api-gateway are visible in the graph. (topo-api-gateway-downstream-d3)
- **OBSERVED EVIDENCE:** [dependency] order-service downstream dependents are api-gateway only. Topology-v2 (effective 2026-09-15T00:00:00Z) added edge order-service -> redis. (topo-order-service-downstream-d3)
- **OBSERVED EVIDENCE:** [dependency] Config change cfg-56d39584 (author config-bot, ticket OPS-2669) changed payment-service db.pool.max_size from 50 to 10 (ratio 0.2) at 10:04Z, about 6 minutes before T0. (cfg-56d39584)
- **OBSERVED EVIDENCE:** [dependency] payment-service db_conn_util_pct rose from baseline mean ~35% to ~69% in the window, onset 10:05Z, reaching 100% by 10:20Z. Sampled values: 10:00 35.8%, 10:05 63.3%, 10:10 93.9%. (met-payment-service-db_conn_util_pct-0940-1035)
- **OBSERVED EVIDENCE:** [dependency] payment-service timeout_rate and error_rate both began rising at 10:06Z (timeouts ~0.1% -> ~11% at 10:10; errors ~0.8% -> ~17%). p99 latency did not change materially (+0.6%), so the symptom is timeouts/errors rather than latency tail growth in the metrics. (met-payment-service-timeout_rate-0940-1035, met-payment-service-error_rate-0940-1035, met-payment-service-p99_latency_ms-0940-1035)
- **OBSERVED EVIDENCE:** [dependency] Config changes query for 08:10-10:35Z returned only cfg-56d39584 across all services; no config changes to auth-service, postgres or redis appeared in this window. (cfg-56d39584)
- **OBSERVED EVIDENCE:** [dependency] Dependency graph (topology-v2): payment-service upstream = auth-service, postgres, redis (plus auth-service -> postgres/redis chains); downstream = api-gateway, order-service, which are potentially impacted. No topology changes listed. (topo-payment-service-both-d2)
- **OBSERVED EVIDENCE:** [observability] Error rate flat across window: mean 0.5% vs baseline 0.5% (change 0.9%), no onset detected; max 0.54% at 10:05. No error spike at T0=10:10. (met-api-gateway-error_rate-0940-1035)
- **OBSERVED EVIDENCE:** [observability] p99 latency flat: window mean 249.6ms vs baseline 249.1ms (+0.2%), no onset; max 275.5ms. (met-api-gateway-p99_latency_ms-0940-1035)
- **OBSERVED EVIDENCE:** [observability] Request rate flat: window mean 1202.5 vs baseline 1192.8 (+0.8%), no retry-driven surge visible in 5-min samples (max 1292.6 at 09:45 and 10:35). (met-api-gateway-request_rate-0940-1035)
- **OBSERVED EVIDENCE:** [observability] Timeout rate flat at ~0.1% (baseline 0.1%, window 0.1%, change 0.2%); no timeouts calling payment-service visible at gateway level. (met-api-gateway-timeout_rate-0940-1035)
- **OBSERVED EVIDENCE:** [observability] Only WARN logs are 5 'Slow client upload' events (1.9MB uploads) between 09:44 and 10:28; no timeout, upstream error, or payment-service connection errors logged. (logpat-api-gateway-88b04940)
- **OBSERVED EVIDENCE:** [observability] Error rate flat: window mean 0.6% vs baseline 0.6% (-0.5%), no onset; p99 latency flat (399ms vs 403ms, -0.9%); timeout rate flat ~0.1%. (met-order-service-error_rate-0940-1035, met-order-service-p99_latency_ms-0940-1035, met-order-service-timeout_rate-0940-1035)
- **OBSERVED EVIDENCE:** [observability] Request rate flat: window mean 249.2 vs baseline 251.6 (-1.0%); order creation logs steady (20-76 orders/min); no retry amplification seen. (met-order-service-request_rate-0940-1035, logpat-order-service-d19346d9)
- **OBSERVED EVIDENCE:** [observability] Only one WARN in window: 'Inventory reservation retry' at 10:34:47Z (single occurrence). No payment-service timeout or connection pool errors logged in order-service. (logpat-order-service-95abd1bb, log-2c9d0f42)
- **OBSERVED EVIDENCE:** [observability] payment-service db_conn_util_pct rose from ~35% baseline to 63% at 10:05 and 94% at 10:10, reaching 100% by 10:20; first onset detected 10:05. (met-payment-service-db_conn_util_pct-0940-1035)
- **OBSERVED EVIDENCE:** [observability] payment-service error_rate went from ~0.8% baseline to ~17% (onset 10:06) and timeout_rate from ~0.1% to ~11-13% (onset 10:06), sustained through 10:35. (met-payment-service-error_rate-0940-1035, met-payment-service-timeout_rate-0940-1035)
- **OBSERVED EVIDENCE:** [observability] 29 ERROR logs 'Timeout acquiring connection from pool payment-db-pool after 5000ms (active=10, idle=0, waiting=N)' between 10:06:13 and 10:34:18; waiting count ranges ~15-92 while active=10 and idle=0, i.e. pool fully saturated at its size of 10. (logpat-payment-service-7d1739af, log-945fe4b3, log-c2630173, log-41cefacf)
- **OBSERVED EVIDENCE:** [observability] payment-service p99 latency is flat (baseline mean 299ms vs window mean 301ms) and request_rate is unchanged (300 vs 299 rps); CPU flat (~40%). (met-payment-service-p99_latency_ms-0940-1035, met-payment-service-request_rate-0940-1035, met-payment-service-cpu_pct-0940-1035)
- **OBSERVED EVIDENCE:** [observability] postgres db_conn_util_pct FELL from ~40% baseline to ~22% from 10:07 onward (-23%), i.e. postgres-side connection usage decreased while payment pool was saturated. postgres p99 latency (~25ms), CPU (~35%) and disk_io_wait (~2ms) were unchanged. (met-postgres-db_conn_util_pct-0940-1035, met-postgres-p99_latency_ms-0940-1035, met-postgres-cpu_pct-0940-1035, met-postgres-disk_io_wait_ms-0940-1035)
- **OBSERVED EVIDENCE:** [observability] postgres WARN slow statements 'SELECT report_rollup()' with durations 15.8s-18.7s, first 10:01:25, last 10:24:50 (4 occurrences, around 10:01, 10:06, 10:20, 10:24). (logpat-postgres-44883ca5, log-1d49fd67, log-03fe1680, log-48f94b94, log-8498b365)
- **ASSUMPTION:** [critic: unsupported assumption] That 10 was the intended value for OPS-2669 (intent not confirmed). 
- **ASSUMPTION:** [critic: unsupported assumption] That rolling back to 50 would clear the saturation (not yet tested). 

## Investigation Performed
- Round 1 | observability | completed | attempts 1 | 7 tool calls | Characterize pool exhaustion and latency/error patterns from 2026-10-05T10:00Z onward. Determine whether connection pool saturation is in payment-service, and w
- Round 1 | observability | completed | attempts 1 | 4 tool calls | Assess downstream impact and upstream traffic on api-gateway and order-service around the incident start, to see when errors began and whether retries amplified
- Round 1 | dependency | completed | attempts 1 | 4 tool calls | Identify deployments, configuration changes (especially pool sizes, timeouts, DB/redis settings, feature flags) to payment-service, auth-service, postgres, and 
- Round 1 | dependency | completed | attempts 1 | 3 tool calls | Confirm the dependency graph around payment-service, including transitive callers of api-gateway and order-service, to scope blast radius.
- Round 1 | reasoning | completed | attempts 1 | 0 tool calls | Develop and rank competing hypotheses
- Round 1 | critic | completed | attempts 1 | 3 tool calls | Independently review hypotheses
- Round 1 | reporting | completed | attempts 1 | 0 tool calls | Write final report

## Root-Cause Hypotheses (ranked by evidence strength)
### 1. H1 - `configuration_regression` in `payment-service` (confidence 0.95, critic: accept)
**INFERENCE:** Config change cfg-56d39584 (OPS-2669) reduced payment-service db.pool.max_size from 50 to 10 at 10:04Z, so the pool saturates under unchanged load, causing pool-acquire timeouts and errors. Mechanism: db.pool.max_size 50->10 at 10:04Z -> pool capacity drops ~5x while request rate stays ~300 rps and baseline pool use (~35% of 50, roughly 17 connections) now exceeds 10 -> requests queue (waiting up to ~92), active=10 idle=0 -> 5s acquire timeouts -> timeout_rate ~0.1%->~11-13% and error_rate ~0.8%->~17% from 10:06 -> payment API errors. Postgres connection count falling ~23% is consistent with payment-service now holding fewer connections (cap of 10), not contradictory.

Confidence breakdown: base 0.10; +0.08 corroboration across >=2 independent source types; +0.78 supporting evidence (7 refs, reliability-weighted, capped); +0.08 proposed cause (10:04) precedes/coincides with first observed anomaly (10:05); -0.06 3 acknowledged evidence gaps; +0.05 critic review adjustment; = 0.95 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [CONFIRMED FACT] `cfg-56d39584` (strong): Config change on payment-service: db.pool.max_size 50 -> 10 at 2026-10-05T10:04:00Z (OPS-2669)
- [OBSERVED EVIDENCE] `met-payment-service-db_conn_util_pct-0940-1035` (strong): payment-service db_conn_util_pct: baseline 34.95 -> window mean 69.43 (max 100.0, change 98.7%), onset 2026-10-05T10:05:00Z
- [OBSERVED EVIDENCE] `logpat-payment-service-7d1739af` (strong): 29x ERROR on payment-service: 'Timeout acquiring connection from pool payment-db-pool after 5000ms (active=10, idle=0, waiting=29)' (first 2026-10-05T10:06:13Z, last 2026-10-05T10:34:18Z)
- [OBSERVED EVIDENCE] `met-payment-service-timeout_rate-0940-1035` (moderate): payment-service timeout_rate: baseline 0.1 -> window mean 6.3 (max 13.3, change 6147.1%), onset 2026-10-05T10:06:00Z
- [OBSERVED EVIDENCE] `met-payment-service-error_rate-0940-1035` (moderate): payment-service error_rate: baseline 0.8 -> window mean 9.17 (max 18.85, change 1040.5%), onset 2026-10-05T10:06:00Z
- [OBSERVED EVIDENCE] `met-postgres-p99_latency_ms-0940-1035` (moderate): postgres p99_latency_ms: baseline 25.15 -> window mean 25.13 (max 27.03, change -0.1%), onset none detected
- [OBSERVED EVIDENCE] `met-payment-service-request_rate-0940-1035` (moderate): payment-service request_rate: baseline 300.21 -> window mean 299.16 (max 325.13, change -0.4%), onset none detected

Contradicting evidence:
- none

Remaining uncertainties / missing evidence:
- [UNKNOWN] Runtime confirmation that the effective pool max is 10 (config diff / pool gauge max)
- [UNKNOWN] Rationale for OPS-2669 and whether the change was intended
- [UNKNOWN] Per-pool wait-time time series

### 2. H2 - `db_connection_pool_exhaustion` in `postgres` (confidence 0.00, critic: reject)
**INFERENCE:** Long-running report_rollup() statements (15-19s, from 10:01) hold connections or locks that payment-service's pool depends on, causing pool saturation independent of the config change. Mechanism: report_rollup() slow statements from 10:01 -> connections/locks held for tens of seconds -> payment-service connections not returned to pool -> pool active=10 idle=0 and waiting queue grows -> timeouts.

Confidence breakdown: base 0.10; +0.08 corroboration across >=2 independent source types; +0.24 supporting evidence (2 refs, reliability-weighted, capped); -0.35 contradicting evidence (3 refs, capped 0.45); +0.08 proposed cause (10:01) precedes/coincides with first observed anomaly (10:05); -0.04 2 acknowledged evidence gaps; -0.40 critic review adjustment; = 0.00 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-postgres-44883ca5` (moderate): 4x WARN on postgres: 'duration: 15802 ms statement: SELECT report_rollup()' (first 2026-10-05T10:01:25Z, last 2026-10-05T10:24:50Z)
- [OBSERVED EVIDENCE] `met-payment-service-db_conn_util_pct-0940-1035` (weak): payment-service db_conn_util_pct: baseline 34.95 -> window mean 69.43 (max 100.0, change 98.7%), onset 2026-10-05T10:05:00Z

Contradicting evidence:
- [CONFIRMED FACT] `cfg-56d39584` (moderate): Config change on payment-service: db.pool.max_size 50 -> 10 at 2026-10-05T10:04:00Z (OPS-2669)
- [OBSERVED EVIDENCE] `met-postgres-p99_latency_ms-0940-1035` (moderate): postgres p99_latency_ms: baseline 25.15 -> window mean 25.13 (max 27.03, change -0.1%), onset none detected
- [OBSERVED EVIDENCE] `met-postgres-db_conn_util_pct-0940-1035` (weak): postgres db_conn_util_pct: baseline 39.83 -> window mean 30.56 (max 43.9, change -23.3%), onset 2026-10-05T10:07:00Z

Remaining uncertainties / missing evidence:
- [UNKNOWN] Identity of the client issuing report_rollup() (payment-service or other)
- [UNKNOWN] pg_stat_activity / lock-wait data during 10:01-10:35

### 3. H3 - `traffic_surge` in `payment-service` (confidence 0.00, critic: reject)
**INFERENCE:** Increased payment traffic or retries exhausted the pool. Mechanism: Higher request volume -> more concurrent DB checkouts -> pool of fixed size saturates -> timeouts.

Confidence breakdown: base 0.10; +0.00 supporting evidence (0 refs, reliability-weighted, capped); -0.45 contradicting evidence (2 refs, capped 0.45); +0.08 proposed cause (10:05) precedes/coincides with first observed anomaly (10:05); -0.02 1 acknowledged evidence gaps; -0.40 critic review adjustment; = 0.00 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- none

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-payment-service-request_rate-0940-1035` (strong): payment-service request_rate: baseline 300.21 -> window mean 299.16 (max 325.13, change -0.4%), onset none detected
- [OBSERVED EVIDENCE] `met-api-gateway-request_rate-0940-1035` (moderate): api-gateway request_rate: baseline 1192.84 -> window mean 1202.52 (max 1292.55, change 0.8%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Per-route payment request breakdown

### 4. H4 - `cache_degradation` in `redis` (confidence 0.00, critic: reject)
**INFERENCE:** Shared redis (used by payment-service and order-service since 2026-09-15) degraded and caused connections to be held. Mechanism: redis slowness -> payment calls hold DB connections longer -> pool exhaustion.

Confidence breakdown: base 0.10; +0.04 supporting evidence (1 refs, reliability-weighted, capped); -0.45 contradicting evidence (3 refs, capped 0.45); +0.08 proposed cause (00:00) precedes/coincides with first observed anomaly (10:05); -0.02 1 acknowledged evidence gaps; -0.40 critic review adjustment; = 0.00 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [CONFIRMED FACT] `topo-order-service-downstream-d3` (weak): order-service depends on ?; called by ['api-gateway'] (graph topology-v2)

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-redis-p99_latency_ms-0940-1035` (strong): redis p99_latency_ms: baseline 3.0 -> window mean 2.99 (max 3.35, change -0.3%), onset none detected
- [OBSERVED EVIDENCE] `met-redis-cache_hit_rate-0940-1035` (moderate): redis cache_hit_rate: baseline 95.14 -> window mean 94.94 (max 95.98, change -0.2%), onset none detected
- [OBSERVED EVIDENCE] `met-auth-service-p99_latency_ms-0940-1035` (weak): auth-service p99_latency_ms: baseline 90.34 -> window mean 89.6 (max 101.39, change -0.8%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Redis timeout_rate (not collected)

## Critic Review
- **Verdict:** `APPROVED` (rounds reviewed: 1)
- **Reasoning:** H1 is well supported and consistent in time. Config change cfg-56d39584 (db.pool.max_size 50->10, OPS-2669) is the only change in the window, and the payment-service log confirms the reload to max_size=10 at 10:04:00Z. Pool-acquire timeouts appear from 10:06:13Z with active=10 idle=0 and a growing waiting queue, meaning the pool is exactly at its new cap. Timeout and error rates move at 10:06, after the reload. Request rate is flat (300 vs 299 rps), so load did not change. Postgres latency is flat and Postgres connection usage fell, which fits an application-side cap rather than a database slowdown. Caveat: the rollback test (restore 50 and check recovery) and the OPS-2669 intent are not yet confirmed. These do not block approval. H2, H3 and H4 are rejected, as detailed below.
- H1: **accept** - Config reload to max_size=10 is confirmed in payment-service logs at 10:04:00Z. Pool timeouts start at 10:06:13Z with active=10, idle=0, waiting up to 78, which matches a pool saturated at the new cap. Timeout and error rate onsets follow. Load is flat and Postgres p99 is flat, which rules out a load or DB-slowness cause. The rollback test is still a useful confirmation but is not required for approval.
- H2: **reject** - report_rollup() slow statements started at 10:01, but payment pool utilisation was at baseline (~35%) until 10:05, and no pool errors appeared until 10:06, after the config reload at 10:04. Postgres p99, CPU and connection usage show no lock or IO pressure, and Postgres connections fell rather than rose. The rollup is at most a background factor and does not explain the saturation timing. Caller identity is also unknown.
- H3: **reject** - Payment request rate is flat (300 vs 299 rps) and upstream api-gateway rate is flat. No surge or retry amplification is evident. The pre-check already flags no valid supporting evidence.
- H4: **reject** - Redis p99 (3.0 vs 2.99 ms) and cache hit rate are flat. The only support is a topology edge added 2026-09-15, which is structural and not an anomaly. No redis log or timeout evidence exists. The cited evidence is not a symptom of degradation.
- pre-check blocking `has_support` on H3: no valid supporting evidence
- pre-check warning `culprit_symptom` on H4: no log/metric evidence cited for culprit redis
- pre-check warning `single_source` on H4: all support comes from one source type (dependency)
- alternative: Report_rollup() lock or connection holds in Postgres contributing to pool pressure (H2). Not supported by timing or DB metrics, but not fully excluded without pg_stat_activity data.
- alternative: Traffic surge (H3): contradicted by flat request rates.
- alternative: Redis degradation (H4): contradicted by flat redis latency and hit rate.

## Probable Root Cause
ROOT CAUSE IDENTIFIED (critic-approved; still an INFERENCE from evidence): configuration_regression in payment-service - Config change cfg-56d39584 (OPS-2669) reduced payment-service db.pool.max_size from 50 to 10 at 10:04Z, so the pool saturates under unchanged load, causing pool-acquire timeouts and errors.

## Corrective Actions
- Restore payment-service db.pool.max_size to 50 (the pre-change value) as the immediate mitigation, after confirming the intended value with the OPS-2669 owner (cfg-56d39584).
- Verify recovery after the rollback: confirm the waiting queue drains, timeout_rate and error_rate return toward baseline (~0.1% and ~0.8%), and db_conn_util_pct stabilizes.
- Record the rollback test result in the incident timeline so the hypothesis is confirmed or refuted by outcome rather than inference alone.
- If rollback does not clear saturation, collect pg_stat_activity and pool metrics to test the unexcluded alternative of report_rollup() holding connections (H2).

## Preventive Actions
- Require review and a staged rollout for changes to database pool settings, including a documented expected value and a check of current pool demand against the new cap.
- Add config-change validation that compares proposed db.pool.max_size against observed peak connection demand and rejects values that would saturate the pool at current traffic.
- Tie every config change to its ticket (OPS-2669) with a stated intent, so that unintended values can be detected in review.
- Review the earlier pool-exhaustion incident from last year to determine whether the same class of config-driven cause was missed and whether the runbook should check config changes first.

## Monitoring Recommendations
- Alert when payment-service db_conn_util_pct stays above 80% for 5 minutes or when the pool waiting count is greater than 0 for more than 1 minute.
- Alert on any payment-service timeout log matching 'Timeout acquiring connection from pool payment-db-pool' and on timeout_rate above 1% for 5 minutes.
- Emit an event or alert on every config reload that changes db.pool.* values, including old value, new value, and change ticket.
- Track pool active and idle counts and waiting queue length as dashboard metrics, and keep Postgres report_rollup() duration (logpat-postgres-44883ca5) under alert as a secondary signal.

## Evidence Gaps
- none recorded

## Limitations
- The rollback test (restoring 50 and observing recovery) has not yet been performed, so the causal link is inferred from timing and metrics rather than confirmed by outcome.
- The intent behind OPS-2669 (whether 10 was the intended value) has not been confirmed.
- Without pg_stat_activity data, the possibility that report_rollup() lock or connection holds contributed to pool pressure (H2) is not fully excluded, though timing and database metrics do not support it.
- Redis and auth-service metrics were used to reject H4; the analysis covers only the metrics available in the investigation window.
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: critic verdict APPROVED

## Final Status
`ROOT_CAUSE_IDENTIFIED`

The most probable root cause of INC-012 is configuration regression: the reduction of payment-service db.pool.max_size from 50 to 10 under cfg-56d39584 (OPS-2669) at 10:04Z. Under unchanged request load (about 300 rps), the pool cannot serve baseline demand, which produces acquire timeouts and elevated errors from 10:06Z. Traffic surge, Redis degradation, and Postgres-side saturation were rejected on the evidence (H2, H3, H4). The rollback test and confirmation of intent for OPS-2669 remain outstanding and should be completed to fully close the investigation.

## Execution Statistics
```json
{
  "rounds": 1,
  "tool_calls": 22,
  "tool_failures": 0,
  "tool_retries": 0,
  "partial_results": 0,
  "agent_failures": 0,
  "agent_retries": 0,
  "invalid_llm_outputs": 0,
  "messages_exchanged": 20,
  "evidence_records": 96,
  "duration_s": 62.41,
  "tokens": {
    "input_tokens": 48,
    "output_tokens": 20240,
    "cache_read_tokens": 37171,
    "cache_write_tokens": 58163,
    "llm_calls": 16,
    "cost_usd": 0.017766885
  },
  "tokens_by_agent": {
    "orchestrator": {
      "input_tokens": 6,
      "output_tokens": 1032,
      "cache_read_tokens": 2989,
      "cache_write_tokens": 0,
      "llm_calls": 2,
      "cost_usd": 0.00054649
    },
    "dependency": {
      "input_tokens": 14,
      "output_tokens": 3980,
      "cache_read_tokens": 10350,
      "cache_write_tokens": 9504,
      "llm_calls": 5,
      "cost_usd": 0.0032829
    },
    "observability": {
      "input_tokens": 14,
      "output_tokens": 7279,
      "cache_read_tokens": 16242,
      "cache_write_tokens": 23212,
      "llm_calls": 5,
      "cost_usd": 0.00670482
    },
    "reasoning": {
      "input_tokens": 4,
      "output_tokens": 3978,
      "cache_read_tokens": 0,
      "cache_write_tokens": 12387,
      "llm_calls": 1,
      "cost_usd": 0.003537775
    },
    "critic": {
      "input_tokens": 6,
      "output_tokens": 2211,
      "cache_read_tokens": 7590,
      "cache_write_tokens": 9537,
      "llm_calls": 2,
      "cost_usd": 0.0023741250000000004
    },
    "reporting": {
      "input_tokens": 4,
      "output_tokens": 1760,
      "cache_read_tokens": 0,
      "cache_write_tokens": 3523,
      "llm_calls": 1,
      "cost_usd": 0.0013207750000000002
    }
  }
}
```
