# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-004
- **Title:** Order API timeouts overnight
- **Severity:** SEV2
- **Affected services:** order-service
- **Start time:** 2026-09-11T02:15:00+00:00
- **Investigation ID:** inv-cdcaeda48f (single_agent)
- **Final status:** `PROBABLE_ROOT_CAUSE`

## Executive Summary
INC-004: Order creation latency and timeouts began at 02:15Z. Earlier signals show the sequence: the invoice-reconciliation batch job started at 02:05Z on order-7f9c; CPU rose at 02:08Z; GC pauses of 2.6-9.7 s started at 02:08Z; memory rose from 02:10Z; the order-worker pool saturated at 02:12Z; p50 latency rose at 02:13Z; and error and timeout rates rose at 02:15Z. No deployments or config changes were recorded. Request rate was flat. Database connection utilisation was flat. Postgres CPU rose modestly (about 24%) from 02:11Z, likely a secondary effect. Status is PROBABLE because per-node and batch-job metrics are unavailable.

## Incident Timeline
| Time (UTC) | Label | Event | Evidence |
|---|---|---|---|
| 2026-09-11T01:48:19Z | OBSERVED EVIDENCE | First log: 6x WARN on order-service: 'Inventory reservation retry for sku-86' (first 2026-09-11T01:48:19Z, last 2026-09-11T02:29:28Z) | logpat-order-service-95abd1bb |
| 2026-09-11T02:08:00Z | OBSERVED EVIDENCE | Anomaly onset: order-service cpu_pct: baseline 44.17 -> window mean 73.13 (max 100.0, change 65.6%), onset 2026-09-11T02:08:00Z | met-order-service-cpu_pct-0145-0240 |
| 2026-09-11T02:08:13Z | OBSERVED EVIDENCE | First log: 13x WARN on order-service: 'GC pause 8140ms (G1 Evacuation Pause)' (first 2026-09-11T02:08:13Z, last 2026-09-11T02:37:37Z) | logpat-order-service-7b888968 |
| 2026-09-11T02:12:03Z | OBSERVED EVIDENCE | First log: 11x WARN on order-service: 'Thread pool order-worker saturated: active=200 queue=19250' (first 2026-09-11T02:12:03Z, last 2026-09-11T02:37:28Z) | logpat-order-service-300bdd51 |
| 2026-09-11T02:13:00Z | OBSERVED EVIDENCE | Anomaly onset: order-service p50_latency_ms: baseline 79.95 -> window mean 609.02 (max 1314.66, change 661.8%), onset 2026-09-11T02:13:00Z | met-order-service-p50_latency_ms-0145-0240 |
| 2026-09-11T02:15:00Z | OBSERVED EVIDENCE | Anomaly onset: order-service error_rate: baseline 0.61 -> window mean 2.1 (max 4.47, change 244.9%), onset 2026-09-11T02:15:00Z | met-order-service-error_rate-0145-0240 |
| 2026-09-11T02:15:00Z | OBSERVED EVIDENCE | Anomaly onset: order-service timeout_rate: baseline 0.1 -> window mean 2.73 (max 6.41, change 2625.3%), onset 2026-09-11T02:15:00Z | met-order-service-timeout_rate-0145-0240 |
| 2026-09-11T02:15:00Z | CONFIRMED FACT | Reported symptom start |  |
| 2026-09-11T02:15:11Z | OBSERVED EVIDENCE | First log: 7x ERROR on order-service: 'Request POST /v1/orders exceeded deadline 5000ms' (first 2026-09-11T02:15:11Z, last 2026-09-11T02:36:36Z) | logpat-order-service-1c82530b |
| 2026-09-11T02:21:00Z | CONFIRMED FACT | Incident reported |  |

## Observed Symptoms
- **OBSERVED EVIDENCE:** order-service error_rate: baseline 0.61 -> window mean 2.1 (max 4.47, change 244.9%), onset 2026-09-11T02:15:00Z (met-order-service-error_rate-0145-0240)
- **OBSERVED EVIDENCE:** order-service timeout_rate: baseline 0.1 -> window mean 2.73 (max 6.41, change 2625.3%), onset 2026-09-11T02:15:00Z (met-order-service-timeout_rate-0145-0240)
- **OBSERVED EVIDENCE:** order-service cpu_pct: baseline 44.17 -> window mean 73.13 (max 100.0, change 65.6%), onset 2026-09-11T02:08:00Z (met-order-service-cpu_pct-0145-0240)
- **OBSERVED EVIDENCE:** order-service p50_latency_ms: baseline 79.95 -> window mean 609.02 (max 1314.66, change 661.8%), onset 2026-09-11T02:13:00Z (met-order-service-p50_latency_ms-0145-0240)

## Investigation Performed

## Root-Cause Hypotheses (ranked by evidence strength)
### 1. H1 - `resource_saturation` in `order-service` (confidence 0.70, critic: n/a)
**INFERENCE:** Invoice-reconciliation batch job (batch_size=500000) started on an order-service node at 02:05Z and saturated CPU and heap, causing GC thrash and thread-pool exhaustion. Mechanism: The batch job consumes CPU and allocates heavily on a serving node; G1 evacuation pauses of 7-10 s stall request threads; the order-worker pool fills (active=200, queue ~19k); requests exceed the 5000 ms deadline.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `log-5b27294e` (strong): INFO order-service: Scheduled job invoice-reconciliation started (batch_size=500000, node=order-7f9c)
- [OBSERVED EVIDENCE] `met-order-service-cpu_pct-0145-0240` (strong): order-service cpu_pct: baseline 44.17 -> window mean 73.13 (max 100.0, change 65.6%), onset 2026-09-11T02:08:00Z
- [OBSERVED EVIDENCE] `logpat-order-service-7b888968` (strong): 13x WARN on order-service: 'GC pause 8140ms (G1 Evacuation Pause)' (first 2026-09-11T02:08:13Z, last 2026-09-11T02:37:37Z)
- [OBSERVED EVIDENCE] `logpat-order-service-300bdd51` (strong): 11x WARN on order-service: 'Thread pool order-worker saturated: active=200 queue=19250' (first 2026-09-11T02:12:03Z, last 2026-09-11T02:37:28Z)
- [OBSERVED EVIDENCE] `met-order-service-memory_pct-0145-0240` (moderate): order-service memory_pct: baseline 55.25 -> window mean 65.29 (max 80.83, change 18.2%), onset 2026-09-11T02:14:00Z
- [INFERENCE] `hist-HIST-2025-040` (moderate): Past incident HIST-2025-040 'Order service CPU saturation from batch job' (similarity 0.6): Reconciliation batch job scheduled on serving nodes.

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-order-service-request_rate-0145-0240` (weak): order-service request_rate: baseline 250.23 -> window mean 250.72 (max 274.8, change 0.2%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Per-node CPU and heap metrics for order-7f9c to confirm the batch job drove usage
- [UNKNOWN] Batch job start and finish logs and its resource profile
- [UNKNOWN] Whether the batch job runs on the same nodes that serve requests

### 2. H3 - `upstream_dependency_degradation` in `None` (confidence 0.15, critic: n/a)
**INFERENCE:** Degradation in a downstream dependency (inventory, payment, postgres) made order threads block, which then led to saturation. Mechanism: Slow dependency calls hold worker threads; the queue builds; GC pressure follows.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `met-postgres-cpu_pct-0145-0240` (weak): postgres cpu_pct: baseline 35.11 -> window mean 43.57 (max 54.78, change 24.1%), onset 2026-09-11T02:11:00Z
- [OBSERVED EVIDENCE] `logpat-order-service-95abd1bb` (weak): 6x WARN on order-service: 'Inventory reservation retry for sku-86' (first 2026-09-11T01:48:19Z, last 2026-09-11T02:29:28Z)

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-postgres-p99_latency_ms-0145-0240` (strong): postgres p99_latency_ms: baseline 25.06 -> window mean 24.92 (max 27.38, change -0.6%), onset none detected
- [OBSERVED EVIDENCE] `met-order-service-db_conn_util_pct-0145-0240` (moderate): order-service db_conn_util_pct: baseline 30.08 -> window mean 29.97 (max 32.7, change -0.4%), onset none detected
- [OBSERVED EVIDENCE] `met-order-service-cpu_pct-0145-0240` (moderate): order-service cpu_pct: baseline 44.17 -> window mean 73.13 (max 100.0, change 65.6%), onset 2026-09-11T02:08:00Z

Remaining uncertainties / missing evidence:
- [UNKNOWN] Payment and inventory service metrics for the window (not queried)

### 3. H2 - `deployment_regression` in `None` (confidence 0.10, critic: n/a)
**INFERENCE:** A code or runtime change introduced a memory leak or allocation regression in order-service, causing GC thrash. Mechanism: Increased heap pressure leads to long G1 pauses and thread saturation.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `met-order-service-memory_pct-0145-0240` (weak): order-service memory_pct: baseline 55.25 -> window mean 65.29 (max 80.83, change 18.2%), onset 2026-09-11T02:14:00Z

Contradicting evidence:
- [UNKNOWN] `get_deployments-empty` (strong): NOT FOUND in collected evidence

Remaining uncertainties / missing evidence:
- [UNKNOWN] Heap dumps or allocation profiles

## Critic Review
- **Verdict:** `NOT_RUN` (rounds reviewed: 0)
- **Reasoning:** 

## Probable Root Cause
MOST PROBABLE EXPLANATION (INFERENCE, not confirmed): resource_saturation in order-service - Invoice-reconciliation batch job (batch_size=500000) started on an order-service node at 02:05Z and saturated CPU and heap, causing GC thrash and thread-pool exhaustion.

## Corrective Actions
- Stop or throttle the invoice-reconciliation job on order-7f9c (reduce batch_size) to relieve CPU and GC pressure
- Restart or drain order-service pods showing GC thrash to restore worker threads
- Move the reconciliation job to dedicated batch workers

## Preventive Actions
- Isolate batch and scheduled jobs from request-serving nodes
- Add batch_size limits and CPU and heap guardrails to scheduled jobs
- Add a runbook step to check scheduled jobs at the start of overnight incidents

## Monitoring Recommendations
- Alert on per-node CPU above 85% and GC pause above 1 s for order-service
- Alert on order-worker queue depth and thread-pool saturation
- Track the batch job's runtime, CPU and heap usage
- Collect per-node metrics for all order-service nodes; disk_io_wait is currently not collected

## Evidence Gaps
- none recorded

## Limitations
- Timing correlation with the batch job start does not prove causation
- Aggregate metrics may hide a single hot node
- Historical match is only an analogy
- [agent-reported gap] No per-node metrics for order-service (aggregate only)
- [agent-reported gap] No batch job resource or completion logs
- [agent-reported gap] Payment and inventory services not examined
- [agent-reported gap] disk_io_wait not collected for order-service
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: agent submitted

## Final Status
`PROBABLE_ROOT_CAUSE`

Order-service overnight timeouts were most likely caused by resource saturation on order-service nodes (CPU and heap/GC thrash) that began about 02:08Z, shortly after the scheduled invoice-reconciliation batch job (batch_size=500000) started on node order-7f9c at 02:05Z. The saturation exhausted the order-worker thread pool, producing deadline-exceeded timeouts. No deployment or configuration change was recorded. The causal link to the batch job is inferred from timing and a historical analogy; the job's own resource usage is not directly measured.

## Execution Statistics
```json
{
  "rounds": 1,
  "tool_calls": 11,
  "tool_failures": 0,
  "tool_retries": 0,
  "partial_results": 0,
  "agent_failures": 0,
  "agent_retries": 0,
  "invalid_llm_outputs": 1,
  "messages_exchanged": 0,
  "evidence_records": 43,
  "duration_s": 30.71,
  "tokens": {
    "input_tokens": 12,
    "output_tokens": 7751,
    "cache_read_tokens": 41494,
    "cache_write_tokens": 17415,
    "llm_calls": 5,
    "cost_usd": 0.006468514999999999
  },
  "tokens_by_agent": {
    "single_agent": {
      "input_tokens": 12,
      "output_tokens": 7751,
      "cache_read_tokens": 41494,
      "cache_write_tokens": 17415,
      "llm_calls": 5,
      "cost_usd": 0.006468514999999999
    }
  }
}
```
