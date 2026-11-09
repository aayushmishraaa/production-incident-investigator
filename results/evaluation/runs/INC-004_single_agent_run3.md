# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-004
- **Title:** Order API timeouts overnight
- **Severity:** SEV2
- **Affected services:** order-service
- **Start time:** 2026-09-11T02:15:00+00:00
- **Investigation ID:** inv-633b75c918 (single_agent)
- **Final status:** `PROBABLE_ROOT_CAUSE`

## Executive Summary
INC-004: Order API timeouts from 02:15Z were caused by order-service exhausting CPU and heap, which triggered long GC pauses and worker-thread saturation. Upstream dependencies and request volume were flat, and no deploys or config changes were recorded. The trigger of the resource growth is still unknown; it needs host/process-level verification.

## Incident Timeline
| Time (UTC) | Label | Event | Evidence |
|---|---|---|---|
| 2026-09-11T01:48:19Z | OBSERVED EVIDENCE | First log: 6x WARN on order-service: 'Inventory reservation retry for sku-86' (first 2026-09-11T01:48:19Z, last 2026-09-11T02:29:28Z) | logpat-order-service-95abd1bb |
| 2026-09-11T02:08:00Z | OBSERVED EVIDENCE | Anomaly onset: order-service cpu_pct: baseline 44.17 -> window mean 73.13 (max 100.0, change 65.6%), onset 2026-09-11T02:08:00Z | met-order-service-cpu_pct-0145-0240 |
| 2026-09-11T02:08:13Z | OBSERVED EVIDENCE | First log: 13x WARN on order-service: 'GC pause 8140ms (G1 Evacuation Pause)' (first 2026-09-11T02:08:13Z, last 2026-09-11T02:37:37Z) | logpat-order-service-7b888968 |
| 2026-09-11T02:12:03Z | OBSERVED EVIDENCE | First log: 11x WARN on order-service: 'Thread pool order-worker saturated: active=200 queue=19250' (first 2026-09-11T02:12:03Z, last 2026-09-11T02:37:28Z) | logpat-order-service-300bdd51 |
| 2026-09-11T02:13:00Z | OBSERVED EVIDENCE | Anomaly onset: order-service p95_latency_ms: baseline 198.04 -> window mean 1574.52 (max 3318.85, change 695.1%), onset 2026-09-11T02:13:00Z | met-order-service-p95_latency_ms-0145-0240 |
| 2026-09-11T02:15:00Z | OBSERVED EVIDENCE | Anomaly onset: order-service timeout_rate: baseline 0.1 -> window mean 2.73 (max 6.41, change 2625.3%), onset 2026-09-11T02:15:00Z | met-order-service-timeout_rate-0145-0240 |
| 2026-09-11T02:15:00Z | OBSERVED EVIDENCE | Anomaly onset: order-service error_rate: baseline 0.61 -> window mean 2.1 (max 4.47, change 244.9%), onset 2026-09-11T02:15:00Z | met-order-service-error_rate-0145-0240 |
| 2026-09-11T02:15:00Z | CONFIRMED FACT | Reported symptom start |  |
| 2026-09-11T02:15:11Z | OBSERVED EVIDENCE | First log: 7x ERROR on order-service: 'Request POST /v1/orders exceeded deadline 5000ms' (first 2026-09-11T02:15:11Z, last 2026-09-11T02:36:36Z) | logpat-order-service-1c82530b |
| 2026-09-11T02:21:00Z | CONFIRMED FACT | Incident reported |  |

## Observed Symptoms
- **OBSERVED EVIDENCE:** order-service timeout_rate: baseline 0.1 -> window mean 2.73 (max 6.41, change 2625.3%), onset 2026-09-11T02:15:00Z (met-order-service-timeout_rate-0145-0240)
- **OBSERVED EVIDENCE:** order-service error_rate: baseline 0.61 -> window mean 2.1 (max 4.47, change 244.9%), onset 2026-09-11T02:15:00Z (met-order-service-error_rate-0145-0240)
- **OBSERVED EVIDENCE:** order-service cpu_pct: baseline 44.17 -> window mean 73.13 (max 100.0, change 65.6%), onset 2026-09-11T02:08:00Z (met-order-service-cpu_pct-0145-0240)
- **OBSERVED EVIDENCE:** order-service p95_latency_ms: baseline 198.04 -> window mean 1574.52 (max 3318.85, change 695.1%), onset 2026-09-11T02:13:00Z (met-order-service-p95_latency_ms-0145-0240)

## Investigation Performed

## Root-Cause Hypotheses (ranked by evidence strength)
### 1. H1 - `resource_saturation` in `order-service` (confidence 0.60, critic: n/a)
**INFERENCE:** Resource saturation inside order-service (CPU and heap pressure from a co-located batch job or a memory leak) causing GC thrashing and worker-pool exhaustion. Mechanism: Memory climbs from ~02:10, GC pauses start at 02:08 (up to 9.7s), CPU reaches ~100%, the order-worker pool saturates (active=200, queue ~19k), and requests exceed the 5s deadline, producing timeouts and errors.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- [OBSERVED EVIDENCE] `met-order-service-cpu_pct-0145-0240` (strong): order-service cpu_pct: baseline 44.17 -> window mean 73.13 (max 100.0, change 65.6%), onset 2026-09-11T02:08:00Z
- [OBSERVED EVIDENCE] `met-order-service-memory_pct-0145-0240` (strong): order-service memory_pct: baseline 55.25 -> window mean 65.29 (max 80.83, change 18.2%), onset 2026-09-11T02:14:00Z
- [OBSERVED EVIDENCE] `logpat-order-service-7b888968` (strong): 13x WARN on order-service: 'GC pause 8140ms (G1 Evacuation Pause)' (first 2026-09-11T02:08:13Z, last 2026-09-11T02:37:37Z)
- [OBSERVED EVIDENCE] `logpat-order-service-300bdd51` (strong): 11x WARN on order-service: 'Thread pool order-worker saturated: active=200 queue=19250' (first 2026-09-11T02:12:03Z, last 2026-09-11T02:37:28Z)
- [OBSERVED EVIDENCE] `logpat-order-service-1c82530b` (strong): 7x ERROR on order-service: 'Request POST /v1/orders exceeded deadline 5000ms' (first 2026-09-11T02:15:11Z, last 2026-09-11T02:36:36Z)
- [OBSERVED EVIDENCE] `met-order-service-timeout_rate-0145-0240` (strong): order-service timeout_rate: baseline 0.1 -> window mean 2.73 (max 6.41, change 2625.3%), onset 2026-09-11T02:15:00Z
- [OBSERVED EVIDENCE] `met-order-service-p95_latency_ms-0145-0240` (moderate): order-service p95_latency_ms: baseline 198.04 -> window mean 1574.52 (max 3318.85, change 695.1%), onset 2026-09-11T02:13:00Z

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-order-service-request_rate-0145-0240` (moderate): order-service request_rate: baseline 250.23 -> window mean 250.72 (max 274.8, change 0.2%), onset none detected
- [OBSERVED EVIDENCE] `met-order-service-db_conn_util_pct-0145-0240` (moderate): order-service db_conn_util_pct: baseline 30.08 -> window mean 29.97 (max 32.7, change -0.4%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Process-level heap/GC data and thread dumps
- [UNKNOWN] Identity of the process or job driving CPU and memory growth in the 02:00-02:10 window
- [UNKNOWN] Host-level CPU breakdown (co-tenant vs application)

### 2. H2 - `upstream_dependency_degradation` in `payment-service` (confidence 0.10, critic: n/a)
**INFERENCE:** Upstream payment-service degradation causing order-worker threads to block. Mechanism: Slow calls to payment or its dependencies would hold worker threads and drive timeouts.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- none

Contradicting evidence:
- [OBSERVED EVIDENCE] `met-payment-service-p99_latency_ms-0145-0240` (strong): payment-service p99_latency_ms: baseline 297.92 -> window mean 299.74 (max 328.66, change 0.6%), onset none detected
- [OBSERVED EVIDENCE] `met-payment-service-timeout_rate-0145-0240` (moderate): payment-service timeout_rate: baseline 0.1 -> window mean 0.1 (max 0.11, change -0.4%), onset none detected
- [OBSERVED EVIDENCE] `met-payment-service-error_rate-0145-0240` (moderate): payment-service error_rate: baseline 0.81 -> window mean 0.8 (max 0.87, change -0.7%), onset none detected

Remaining uncertainties / missing evidence:
- [UNKNOWN] Calls from order-service to payment-service in the window

### 3. H3 - `configuration_regression` in `order-service` (confidence 0.05, critic: n/a)
**INFERENCE:** Configuration or deployment change in order-service or its dependencies. Mechanism: A config or deploy change would have to precede the 02:08 onset.

Confidence breakdown: self-reported by the single agent

Supporting evidence:
- none

Contradicting evidence:
- [OBSERVED EVIDENCE] `logpat-order-service-7b888968` (weak): 13x WARN on order-service: 'GC pause 8140ms (G1 Evacuation Pause)' (first 2026-09-11T02:08:13Z, last 2026-09-11T02:37:37Z)

Remaining uncertainties / missing evidence:
- [UNKNOWN] Confirmation that the config service logs all changes

## Critic Review
- **Verdict:** `NOT_RUN` (rounds reviewed: 0)
- **Reasoning:** 

## Probable Root Cause
MOST PROBABLE EXPLANATION (INFERENCE, not confirmed): resource_saturation in order-service - Resource saturation inside order-service (CPU and heap pressure from a co-located batch job or a memory leak) causing GC thrashing and worker-pool exhaustion.

## Corrective Actions
- Immediately restart or drain order-service instances showing GC thrashing and saturated worker pools, or scale out to restore capacity.
- Identify and stop/throttle any batch or background process running on order-service nodes from ~02:00Z.
- Shed or bound the order-worker queue so it cannot grow to ~19k, with fast-fail on overload.

## Preventive Actions
- Isolate batch/reconciliation workloads from serving nodes (see hist-HIST-2025-040).
- Set heap and GC alerting thresholds, and cap the worker queue size.
- Add memory-growth leak detection for order-service.

## Monitoring Recommendations
- Alert on GC pause >1s and on order-worker queue depth >100.
- Alert on order-service CPU >85% for 5 min and memory >75%.
- Track the order-service timeout rate and p95 against the 200ms baseline.

## Evidence Gaps
- none recorded

## Limitations
- Historical analogy HIST-2025-040 (batch job) is a similarity match only, not confirmation.
- Metrics are sampled at 5-minute resolution, so the exact trigger ordering within 02:00-02:15 is uncertain.
- [agent-reported gap] No process-level heap, GC, or thread dump data.
- [agent-reported gap] disk_io_wait_ms is not collected for order-service.
- [agent-reported gap] No per-process or per-host CPU attribution.
- [agent-reported gap] No order-to-payment call trace data.
- [agent-reported gap] Inventory reservation retry warnings are present but low volume; their role is not evaluated.
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: agent submitted

## Final Status
`PROBABLE_ROOT_CAUSE`

order-service became resource-saturated on the JVM/host level starting ~02:08Z: CPU rose to ~100% and memory climbed from ~55% to ~80%, with G1 pauses of 2.6–9.7s. Thread pool order-worker saturated (active=200, queue up to ~19k), causing requests to exceed the 5000ms deadline and timeouts to rise from 0.1% to ~6%. Upstream payment-service and postgres-related signals are flat, no deployments or config changes occurred, and the cause of the memory/CPU growth is not yet identified. The most likely explanation is a local resource-saturation event inside order-service (possibly an unscheduled batch/background job or a memory leak); this is unconfirmed.

## Execution Statistics
```json
{
  "rounds": 1,
  "tool_calls": 9,
  "tool_failures": 0,
  "tool_retries": 0,
  "partial_results": 0,
  "agent_failures": 0,
  "agent_retries": 0,
  "invalid_llm_outputs": 0,
  "messages_exchanged": 0,
  "evidence_records": 39,
  "duration_s": 20.51,
  "tokens": {
    "input_tokens": 10,
    "output_tokens": 4429,
    "cache_read_tokens": 30955,
    "cache_write_tokens": 8660,
    "llm_calls": 4,
    "cost_usd": 0.00360755
  },
  "tokens_by_agent": {
    "single_agent": {
      "input_tokens": 10,
      "output_tokens": 4429,
      "cache_read_tokens": 30955,
      "cache_write_tokens": 8660,
      "llm_calls": 4,
      "cost_usd": 0.00360755
    }
  }
}
```
