# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-004
- **Title:** Order API timeouts overnight
- **Severity:** SEV2
- **Affected services:** order-service
- **Start time:** 2026-09-11T02:15:00+00:00
- **Investigation ID:** inv-3ac77d0b4e (single_agent)
- **Final status:** `PROBABLE_ROOT_CAUSE`

## Executive Summary
Order API timeouts began at 02:15Z. The order-service was CPU- and memory-starved, with GC pauses and thread-pool saturation starting before the errors. The invoice-reconciliation batch (batch_size=500000) was started on order-7f9c at 02:05Z, and the resource saturation followed at 02:08-02:12Z. No deployments or config changes touched order-service, traffic was flat, and upstream payment was healthy. The batch job is the most likely trigger, but co-location of the batch with serving capacity is inferred, not confirmed.

## Incident Timeline
| Time (UTC) | Label | Event | Evidence |
|---|---|---|---|
| 2026-09-10T22:15:00Z | CONFIRMED FACT | Deployment of payment-service 5.7.2->5.7.3 at 2026-09-10T22:15:00Z (SUCCEEDED): Dependency bumps | dep-bd77b48c |
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
### 1. H1 - `resource_saturation` in `order-service` (confidence 0.80, critic: n/a)
**INFERENCE:** Scheduled invoice-reconciliation batch (batch_size=500000) started on order-service node order-7f9c at 02:05 and exhausted CPU/heap on the serving instances, causing GC storms, order-worker thread-pool saturation, and request deadline timeouts. Mechanism: Batch started 02:05 -> CPU rises from 02:08 (42% to 70-100%) and memory climbs from 02:10 -> G1 pauses of 2.6-9.7s from 02:08 -> order-worker pool saturated (active=200, queue up to 19k) from 02:12 -> p50 latency jumps at 02:13 and error/timeout rate at 02:15 as requests exceed the 5000ms deadline. Persisting until the window end, consistent with a long-running batch.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `logpat-order-service-f3a6bc4b` (strong): 1x INFO on order-service: 'Scheduled job invoice-reconciliation started (batch_size=500000, node=order-7f9c)' (first 2026-09-11T02:05:00Z, last 2026-09-11T02:05:00Z)
- [OBSERVED EVIDENCE] `met-order-service-cpu_pct-0145-0240` (strong): order-service cpu_pct: baseline 44.17 -> window mean 73.13 (max 100.0, change 65.6%), onset 2026-09-11T02:08:00Z
- [OBSERVED EVIDENCE] `logpat-order-service-7b888968` (strong): 13x WARN on order-service: 'GC pause 8140ms (G1 Evacuation Pause)' (first 2026-09-11T02:08:13Z, last 2026-09-11T02:37:37Z)
- [OBSERVED EVIDENCE] `logpat-order-service-300bdd51` (strong): 11x WARN on order-service: 'Thread pool order-worker saturated: active=200 queue=19250' (first 2026-09-11T02:12:03Z, last 2026-09-11T02:37:28Z)
- [OBSERVED EVIDENCE] `met-order-service-p50_latency_ms-0145-0240` (moderate): order-service p50_latency_ms: baseline 79.95 -> window mean 609.02 (max 1314.66, change 661.8%), onset 2026-09-11T02:13:00Z
- [OBSERVED EVIDENCE] `met-order-service-memory_pct-0145-0240` (moderate): order-service memory_pct: baseline 55.25 -> window mean 65.29 (max 80.83, change 18.2%), onset 2026-09-11T02:14:00Z
- [OBSERVED EVIDENCE] `met-order-service-error_rate-0145-0240` (strong): order-service error_rate: baseline 0.61 -> window mean 2.1 (max 4.47, change 244.9%), onset 2026-09-11T02:15:00Z
- [OBSERVED EVIDENCE] `met-order-service-timeout_rate-0145-0240` (strong): order-service timeout_rate: baseline 0.1 -> window mean 2.73 (max 6.41, change 2625.3%), onset 2026-09-11T02:15:00Z
- [OBSERVED EVIDENCE] `logpat-order-service-1c82530b` (strong): 7x ERROR on order-service: 'Request POST /v1/orders exceeded deadline 5000ms' (first 2026-09-11T02:15:11Z, last 2026-09-11T02:36:36Z)
- [INFERENCE] `hist-HIST-2025-040` (weak): Past incident HIST-2025-040 'Order service CPU saturation from batch job' (similarity 0.58): Reconciliation batch job scheduled on serving nodes.

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-order-service-request_rate-0145-0240` (moderate): order-service request_rate: baseline 250.23 -> window mean 250.72 (max 274.8, change 0.2%), onset none detected
- [OBSERVED EVIDENCE] `met-payment-service-p99_latency_ms-0145-0240` (moderate): payment-service p99_latency_ms: baseline 297.92 -> window mean 299.74 (max 328.66, change 0.6%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Per-node metrics confirming the batch is co-located on the serving nodes that handle requests
- [UNKNOWN] Batch job's own logs or completion/duration status
- [UNKNOWN] Heap dump or GC cause confirmation

### 2. H2 - `upstream_dependency_degradation` in `payment-service` (confidence 0.05, critic: n/a)
**INFERENCE:** Degradation in payment-service or its downstream chain caused order-service worker threads to block. Mechanism: Blocked outbound calls would tie up order-worker threads and produce timeouts.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- none

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-payment-service-p99_latency_ms-0145-0240` (strong): payment-service p99_latency_ms: baseline 297.92 -> window mean 299.74 (max 328.66, change 0.6%), onset none detected
- [OBSERVED EVIDENCE] `met-payment-service-error_rate-0145-0240` (strong): payment-service error_rate: baseline 0.81 -> window mean 0.8 (max 0.87, change -0.7%), onset none detected
- [OBSERVED EVIDENCE] `met-order-service-db_conn_util_pct-0145-0240` (moderate): order-service db_conn_util_pct: baseline 30.08 -> window mean 29.97 (max 32.7, change -0.4%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Direct downstream latency for message-queue and inventory calls from order-service

## Critic Review
- **Verdict:** `NOT_RUN` (rounds reviewed: 0)
- **Reasoning:** 

## Probable Root Cause
MOST PROBABLE EXPLANATION (INFERENCE, not confirmed): resource_saturation in order-service - Scheduled invoice-reconciliation batch (batch_size=500000) started on order-service node order-7f9c at 02:05 and exhausted CPU/heap on the serving instances, causing GC storms, order-worker thread-pool saturation, and request deadline timeouts.

## Corrective Actions
- Stop or throttle the invoice-reconciliation job immediately and reduce its batch size.
- Move the reconciliation job to dedicated workers, off the order-serving pool.
- Verify the impact on order-7f9c and restore the order-worker pool capacity.

## Preventive Actions
- Enforce resource isolation (separate deployment or node pool) for batch jobs.
- Cap batch_size and add backpressure/chunking to the reconciliation job.
- Add a pre-run check that blocks batch jobs during serving-capacity pressure.

## Monitoring Recommendations
- Alert on per-instance CPU and heap above 80% and on GC pause duration above 1s.
- Alert on order-worker queue depth and on the timeout_rate exceeding 1%.
- Track job start/end events for invoice-reconciliation alongside order latency.

## Evidence Gaps
- none recorded

## Limitations
- Metrics are service-aggregate, so the single-node attribution is not verified.
- Historical match is an analogy only.
- [agent-reported gap] No per-instance metrics or node-level mapping for order-7f9c.
- [agent-reported gap] No logs from the batch job itself to confirm progress or completion.
- [agent-reported gap] disk_io_wait_ms not collected for order-service.
- [agent-reported gap] Did not check message-queue or inventory latency directly.
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: agent submitted

## Final Status
`PROBABLE_ROOT_CAUSE`

The most likely root cause is the invoice-reconciliation batch job started at 02:05Z, which saturated order-service resources and caused the timeouts. Final confirmation needs per-node metrics showing the batch is co-located on the serving instances.

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
  "invalid_llm_outputs": 0,
  "messages_exchanged": 0,
  "evidence_records": 46,
  "duration_s": 21.0,
  "tokens": {
    "input_tokens": 10,
    "output_tokens": 4521,
    "cache_read_tokens": 26085,
    "cache_write_tokens": 14208,
    "llm_calls": 4,
    "cost_usd": 0.00429835
  },
  "tokens_by_agent": {
    "single_agent": {
      "input_tokens": 10,
      "output_tokens": 4521,
      "cache_read_tokens": 26085,
      "cache_write_tokens": 14208,
      "llm_calls": 4,
      "cost_usd": 0.00429835
    }
  }
}
```
