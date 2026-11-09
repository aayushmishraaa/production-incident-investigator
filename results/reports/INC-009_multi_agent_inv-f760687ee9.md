# Production Incident Investigation Report

## Incident Information
- **Incident ID:** INC-009
- **Title:** User API errors during morning peak
- **Severity:** SEV2
- **Affected services:** api-gateway, user-service
- **Start time:** 2026-09-26T08:00:00+00:00
- **Investigation ID:** inv-f760687ee9 (multi_agent)
- **Final status:** `INCONCLUSIVE`

## Executive Summary
Stub narrative summary.

## Incident Timeline
| Time (UTC) | Label | Event | Evidence |
|---|---|---|---|
| 2026-09-26T07:10:14Z | OBSERVED EVIDENCE | First log: 5x WARN on api-gateway: 'Slow client upload from 10.4.18.12 (1.9MB)' (first 2026-09-26T07:10:14Z, last 2026-09-26T08:28:20Z) | logpat-api-gateway-88b04940 |
| 2026-09-26T07:19:22Z | OBSERVED EVIDENCE | First log: 4x WARN on user-service: 'Deprecated API /v1/users/legacy called by client web-90' (first 2026-09-26T07:19:22Z, last 2026-09-26T08:16:20Z) | logpat-user-service-742b555e |
| 2026-09-26T07:56:00Z | CONFIRMED FACT | Deployment of user-service 7.1.3->7.2.0 at 2026-09-26T07:56:00Z (SUCCEEDED): Switch ORM to batch loader | dep-c02e51b7 |
| 2026-09-26T07:57:00Z | OBSERVED EVIDENCE | Anomaly onset: api-gateway error_rate: baseline 0.5 -> window mean 4.25 (max 8.65, change 747.7%), onset 2026-09-26T07:57:00Z | met-api-gateway-error_rate-0730-0825 |
| 2026-09-26T07:57:00Z | OBSERVED EVIDENCE | Anomaly onset: user-service error_rate: baseline 0.41 -> window mean 12.5 (max 26.11, change 2984.9%), onset 2026-09-26T07:57:00Z | met-user-service-error_rate-0730-0825 |
| 2026-09-26T07:57:00Z | OBSERVED EVIDENCE | Anomaly onset: user-service p95_latency_ms: baseline 80.09 -> window mean 383.28 (max 748.48, change 378.5%), onset 2026-09-26T07:57:00Z | met-user-service-p95_latency_ms-0730-0825 |
| 2026-09-26T07:57:17Z | OBSERVED EVIDENCE | First log: 10x ERROR on user-service: 'NullPointerException in ProfileBatchLoader.load (user-service v7.2.0) req 18' (first 2026-09-26T07:57:17Z, last 2026-09-26T08:22:46Z) | logpat-user-service-2347725d |
| 2026-09-26T08:00:00Z | CONFIRMED FACT | Reported symptom start |  |
| 2026-09-26T08:06:00Z | CONFIRMED FACT | Incident reported |  |
| 2026-09-26T08:06:34Z | OBSERVED EVIDENCE | First log: 4x WARN on api-gateway: 'user-service returned 500 for GET /v1/users/62' (first 2026-09-26T08:06:34Z, last 2026-09-26T08:22:09Z) | logpat-api-gateway-c1d874f7 |

## Observed Symptoms
- **OBSERVED EVIDENCE:** api-gateway error_rate: baseline 0.5 -> window mean 4.25 (max 8.65, change 747.7%), onset 2026-09-26T07:57:00Z (met-api-gateway-error_rate-0730-0825)
- **OBSERVED EVIDENCE:** user-service error_rate: baseline 0.41 -> window mean 12.5 (max 26.11, change 2984.9%), onset 2026-09-26T07:57:00Z (met-user-service-error_rate-0730-0825)
- **OBSERVED EVIDENCE:** user-service p95_latency_ms: baseline 80.09 -> window mean 383.28 (max 748.48, change 378.5%), onset 2026-09-26T07:57:00Z (met-user-service-p95_latency_ms-0730-0825)
- **OBSERVED EVIDENCE:** [dependency] deployment user-service 7.2.0 at 2026-09-26T07:56:00Z (dep-c02e51b7)
- **OBSERVED EVIDENCE:** [observability] error_rate changed 747.7% (onset 2026-09-26T07:57:00Z) (met-api-gateway-error_rate-0730-0825)
- **OBSERVED EVIDENCE:** [observability] error_rate changed 2984.9% (onset 2026-09-26T07:57:00Z) (met-user-service-error_rate-0730-0825)
- **OBSERVED EVIDENCE:** [observability] p95_latency_ms changed 378.5% (onset 2026-09-26T07:57:00Z) (met-user-service-p95_latency_ms-0730-0825)
- **OBSERVED EVIDENCE:** [observability] 10x NullPointerException in ProfileBatchLoader.load (user-service v<n>.<n>.<n>) req <n> (logpat-user-service-2347725d)
- **OBSERVED EVIDENCE:** [observability] error_rate changed 747.7% (onset 2026-09-26T07:57:00Z) (met-api-gateway-error_rate-0730-0825)
- **OBSERVED EVIDENCE:** [observability] error_rate changed 747.7% (onset 2026-09-26T07:57:00Z) (met-api-gateway-error_rate-0730-0825)

## Investigation Performed
- Round 1 | observability | completed | attempts 1 | 4 tool calls | Compare logs/metrics of affected services vs baseline
- Round 1 | dependency | completed | attempts 1 | 3 tool calls | Review deployments, config changes and dependencies
- Round 1 | reasoning | completed | attempts 1 | 0 tool calls | Develop and rank competing hypotheses
- Round 1 | critic | completed | attempts 1 | 0 tool calls | Independently review hypotheses
- Round 2 | observability | completed | attempts 1 | 2 tool calls | FOLLOW-UP requested by critic: verify timing of earliest anomaly
- Round 2 | reasoning | completed | attempts 1 | 0 tool calls | Develop and rank competing hypotheses
- Round 2 | critic | completed | attempts 1 | 0 tool calls | Independently review hypotheses
- Round 3 | observability | completed | attempts 1 | 2 tool calls | FOLLOW-UP requested by critic: verify timing of earliest anomaly
- Round 3 | reasoning | completed | attempts 1 | 0 tool calls | Develop and rank competing hypotheses
- Round 3 | critic | completed | attempts 1 | 0 tool calls | Independently review hypotheses
- Round 3 | reporting | completed | attempts 1 | 0 tool calls | Write final report

## Root-Cause Hypotheses (ranked by evidence strength)
### 1. H1 - `deployment_regression` in `user-service` (confidence 0.12, critic: needs_evidence)
**INFERENCE:** deployment regression in user-service Mechanism: stub heuristic

Confidence breakdown: base 0.10; +0.12 supporting evidence (1 refs, reliability-weighted, capped); +0.00 no cause time given; temporal precedence unverified; -0.05 tool failures/partial data for user-service; -0.05 critic review adjustment; = 0.12 (evidence-strength score, not a calibrated probability)

Supporting evidence:
- [CONFIRMED FACT] `dep-c02e51b7` (moderate): Deployment of user-service 7.1.3->7.2.0 at 2026-09-26T07:56:00Z (SUCCEEDED): Switch ORM to batch loader

Contradicting evidence:
- none

## Critic Review
- **Verdict:** `INCONCLUSIVE` (rounds reviewed: 3)
- **Reasoning:** stub critic
- H1: **needs_evidence** - stub review
- pre-check blocking `correlation_only` on H1: change hypothesis supported only by the change record itself (temporal correlation); no log/metric evidence of the changed behaviour
- pre-check warning `cause_time` on H1: no cause time given; temporal precedence cannot be verified
- pre-check warning `culprit_symptom` on H1: no log/metric evidence cited for culprit user-service
- pre-check warning `single_source` on H1: all support comes from one source type (deployment)

## Probable Root Cause
Root cause could not be conclusively established with the available evidence.

## Corrective Actions
- Mitigate impact

## Preventive Actions
- Add tests

## Monitoring Recommendations
- Alert on p95 latency

## Evidence Gaps
- [UNKNOWN] query_logs returned incomplete data for service=api-gateway (PARTIAL_DATA)
- [UNKNOWN] query_logs returned incomplete data for service=user-service (PARTIAL_DATA)

## Limitations
- Generated by stub LLM
- 0 tool calls failed and 4 returned partial data; affected areas are treated as unknown, not healthy.
- Confidence values are rule-based evidence-strength scores, not calibrated probabilities.
- Investigation terminated because: critic verdict INCONCLUSIVE

## Final Status
`INCONCLUSIVE`

Root cause could not be conclusively established with the available evidence. See status.

## Execution Statistics
```json
{
  "rounds": 3,
  "tool_calls": 14,
  "tool_failures": 3,
  "tool_retries": 3,
  "partial_results": 4,
  "agent_failures": 0,
  "agent_retries": 0,
  "invalid_llm_outputs": 0,
  "messages_exchanged": 34,
  "evidence_records": 35,
  "duration_s": 2.19,
  "tokens": "unavailable (stub LLM: no real token usage)",
  "tokens_by_agent": null
}
```
