# API examples (real run)

These requests and responses were captured from a live server (`uvicorn app.main:app --port 8765`) running Claude Haiku 5.5 on 2026-11-09. Long payloads are truncated.

This run of INC-007 ended **INCONCLUSIVE**. The Critic kept asking for more evidence until the round limit was reached, and the leading hypothesis (the correct one) scored below the probable-root-cause threshold. The same thing happened in 1 of the 3 evaluation runs for this incident. It shows the system declining to force a winner; see docs/evaluation.md.

## GET /health
```json
{
  "status": "ok",
  "llm_provider": "anthropic",
  "model": "claude-haiku-5-5",
  "incidents_available": 12
}
```

## GET /incidents (first 2)
```json
[
  {
    "incident_id": "INC-001",
    "title": "Payment API latency spike",
    "description": "Customers report checkout taking 3-5 seconds; payment API P95 latency alarm fired. Some payments failing with 5xx.",
    "severity": "SEV2",
    "reported_at": "2026-09-02T14:06:00Z",
    "symptom_start": "2026-09-02T14:00:00Z",
    "affected_services": [
      "payment-service",
      "api-gateway"
    ],
    "reporter": "on-call"
  },
  {
    "incident_id": "INC-002",
    "title": "Login and checkout failures",
    "description": "Sharp increase in 5xx errors on login and checkout endpoints. Users being logged out.",
    "severity": "SEV1",
    "reported_at": "2026-09-05T09:36:00Z",
    "symptom_start": "2026-09-05T09:30:00Z",
    "affected_services": [
      "api-gateway",
      "auth-service",
      "payment-service"
    ],
    "reporter": "on-call"
  }
]
```

## POST /investigate
```bash
curl -s -X POST localhost:8765/investigate -H 'content-type: application/json' -d '{"incident_id":"INC-007"}'
```
Response `202`:
```json
{
  "investigation_id": "inv-397cac0379",
  "status": "RUNNING",
  "incident_id": "INC-007",
  "system": "multi_agent",
  "execution": {
    "mode": "background",
    "poll": "/investigations/inv-397cac0379",
    "config": {
      "max_rounds": 3,
      "max_tool_calls": 60,
      "max_tool_retries": 2,
      "max_agent_retries": 1,
      "max_agent_steps": 6,
      "tool_timeout_s": 2.0,
      "investigation_timeout_s": 300.0,
      "max_llm_calls": 80,
      "max_cost_usd": 0.25,
      "approve_confidence": 0.6,
      "parallelism": 4,
      "random_failure_rate": 0.0,
      "seed": 7
    }
  }
}
```

## GET /investigations/{id} (after completion, excerpt)
While the investigation is running, `status` is `RUNNING`. It changes only once the report exists.
```json
{
  "investigation_id": "inv-397cac0379",
  "status": "INCONCLUSIVE",
  "round": 3,
  "state (excerpt)": {
    "tasks": [
      {
        "task_id": "task-9146ce5606",
        "agent": "observability",
        "round": 1,
        "status": "completed",
        "depends_on": [],
        "attempts": 1
      },
      {
        "task_id": "task-56c53f5b67",
        "agent": "observability",
        "round": 1,
        "status": "completed",
        "depends_on": [],
        "attempts": 1
      },
      {
        "task_id": "task-24aee59dea",
        "agent": "dependency",
        "round": 1,
        "status": "completed",
        "depends_on": [],
        "attempts": 1
      },
      {
        "task_id": "task-5b41659704",
        "agent": "reasoning",
        "round": 1,
        "status": "completed",
        "depends_on": [
          "task-9146ce5606",
          "task-56c53f5b67",
          "task-24aee59dea"
        ],
        "attempts": 1
      },
      {
        "task_id": "task-5df07d27c3",
        "agent": "critic",
        "round": 1,
        "status": "completed",
        "depends_on": [
          "task-5b41659704"
        ],
        "attempts": 1
      },
      {
        "task_id": "task-36aca76e20",
        "agent": "observability",
        "round": 2,
        "status": "completed",
        "depends_on": [
          "task-5df07d27c3"
        ],
        "attempts": 1
      }
    ],
    "messages (first 5 of 51)": [
      {
        "sender": "orchestrator",
        "recipient": "observability",
        "message_type": "task_assignment",
        "status": "delivered"
      },
      {
        "sender": "orchestrator",
        "recipient": "observability",
        "message_type": "task_assignment",
        "status": "delivered"
      },
      {
        "sender": "orchestrator",
        "recipient": "dependency",
        "message_type": "task_assignment",
        "status": "delivered"
      },
      {
        "sender": "dependency",
        "recipient": "orchestrator",
        "message_type": "findings",
        "status": "consumed"
      },
      {
        "sender": "observability",
        "recipient": "orchestrator",
        "message_type": "findings",
        "status": "consumed"
      }
    ],
    "stats": {
      "tool_calls": 43,
      "tool_failures": 0,
      "tool_retries": 0,
      "partial_results": 0,
      "agent_failures": 0,
      "invalid_llm_outputs": 0,
      "termination_reason": "critic verdict INCONCLUSIVE"
    }
  }
}
```

## GET /investigations/{id}/report (excerpt)
```json
{
  "investigation_id": "inv-397cac0379",
  "incident_id": "INC-007",
  "final_status": "INCONCLUSIVE",
  "root_cause_statement": "Root cause could not be conclusively established with the available evidence.",
  "executive_summary": "INC-007 (SEV2): order checkout error rate rose above 25% starting around 15:25Z, with symptoms beginning 15:25Z and the incident reported at 15:31Z. Affected service: order-service. The final status is INCONCLUSIVE. The root cause could not be established, and no leading hypothesis is confirmed.\n\nThe strongest candidate under investigation is H1 (confidence 0.48, status needs_evidence). It links a config change on order-service, cfg-7f81d14a (payment_client.timeout_ms 3000 -> 300, applied 15:22:00Z, config reload logged as version 42 (log-827fcb9e)), to order-side payment timeouts. Supporting evidence includes \"timed out after 300ms\" errors on POST /v1/charges starting 15:23:20Z (logpat-order-service-f003ad98), an order timeout_rate rise from a 0.1% baseline to about 35% with onset at 15:23Z (met-order-service-timeout_rate-1515-1550), a circuit breaker opening at 15:24:10Z (logpat-order-service-e2b30f44), and retry budget exhaustion from 15:25:13Z (logpat-order-service-809f4936). H1 is not confirmed. Payment's own latency and error rate stay flat (met-payment-service-p95_latency_ms-1510-1540, met-payment-service-error_rate-1515-1540), which is consistent with payment being healthy. Payment inbound request rate falls from about 298 to 250 req/s on window mean (met-payment-service-request_rate-1510-1540). The timing of that drop is not resolved at the available resolution.\n\nH2 (network/LB path fault) and H3 (payment 5.8.1 deployment regression, dep-7cf38f2d) are both rejected. The payment-side regression is contradicted by flat payment latency and error rate.",
  "corrective_actions": [
    "Mitigate customer impact now. Because H1 is the best-supported candidate, the order-service owner should evaluate reverting payment_client.timeout_ms from 300ms to the prior 3000ms (cfg-7f81d14a) and confirm whether checkout error rate recovers. This is a mitigation step, not a confirmed fix.",
    "Once the timeout is reverted or otherwise changed, watch the breaker state and retry budget. The breaker should close and the 'Retry budget exhausted' warnings should stop (logpat-order-service-809f4936).",
    "Keep the payment team engaged to confirm payment capacity and error rates during and after the mitigation, so that payment is not scaled or changed without evidence."
  ],
  "limitations": [
    "Payment request_rate is sampled at 5-minute resolution. The exact start of the inbound drop relative to the 15:22Z config change cannot be determined. The summary metric reports onset at 15:37Z, while log-level and critic evidence describe a decline from about 15:20-15:25Z; this discrepancy is unresolved.",
    "Breaker short-circuiting as the cause of the payment inbound drop is inferred from timing, not from a rejected-call counter.",
    "Order p95 latency above 300ms is not directly verified against per-attempt timing.",
    "Network/LB path faults (H2) cannot be fully excluded without path-level telemetry.",
    "The reason the timeout was set to 300ms is outside the scope of this investigation.",
    "Confidence values are rule-based evidence-strength scores, not calibrated probabilities.",
    "Investigation terminated because: critic verdict INCONCLUSIVE"
  ],
  "hypotheses (top 2)": [
    {
      "rank": 1,
      "category": "configuration_regression",
      "culprit_service": "order-service",
      "confidence": 0.48,
      "critic_decision": "needs_evidence",
      "confidence_explanation": [
        "base 0.10",
        "+0.08 corroboration across >=2 independent source types",
        "+0.78 supporting evidence (7 refs, reliability-weighted, capped)",
        "-0.30 contradicting evidence (3 refs, capped 0.45)",
        "+0.08 proposed cause (15:22) precedes/coincides with first observed anomaly (15:23)",
        "-0.05 1 cited evidence id(s) do not exist",
        "-0.08 5 acknowledged evidence gaps",
        "-0.05 critic review adjustment",
        "= 0.48 (evidence-strength score, not a calibrated probability)"
      ]
    },
    {
      "rank": 2,
      "category": "upstream_dependency_degradation",
      "culprit_service": "payment-service",
      "confidence": 0.0,
      "critic_decision": "reject",
      "confidence_explanation": [
        "base 0.10",
        "+0.28 supporting evidence (3 refs, reliability-weighted, capped)",
        "-0.30 contradicting evidence (3 refs, capped 0.45)",
        "+0.08 proposed cause (15:20) precedes/coincides with first observed anomaly (15:23)",
        "-0.05 1 cited evidence id(s) do not exist",
        "-0.06 3 acknowledged evidence gaps",
        "-0.40 critic review adjustment",
        "= 0.00 (evidence-strength score, not a calibrated probability)"
      ]
    }
  ],
  "critic_review": {
    "verdict": "INCONCLUSIVE",
    "summary": "H1 is the leading and best-supported hypothesis: order-service config change payment_client.timeout_ms 3000->300 (cfg-7f81d14a, applied 15:22:00Z, config reload logged at 15:22:00Z) is the only change in the window. Order timeout errors (\"timed out after 300ms\", POST /v1/charges) begin 15:23:20Z, timeout_rate jumps from 0.1% to ~35% with onset 15:23Z, the breaker opens 15:24:10Z, and retry budget exhaustion follows at 15:25:13Z. Payment's own p95 latency (~151ms) and error rate (0.8%) stay flat through the window, consistent with payment being healthy and order abandoning slow calls on its side. Payment inbound request rate drops from ~297 to ~207/s between the 15:20 and 15:25 samples, which is consistent with breaker short-circuiting after 15:24:10. Corrected evidence: the payment request_rate series is now verified as met-payment-service-request_rate-1515-1540 (replacing the citation to a non-existent ID) and its sampled values match the claims. Limitations: (1) the payment inbound dip begins around 15:20-15:22 (281/s at 15:20, near baseline), so the exact start of the drop relative to the 15:22 change is not resolved at 5-minute resolution; (2) order p95 (~370-450ms) exceeds the 300ms per-attempt timeout, which is plausibly explained by retries accumulating across attempts (retry budget logs support this) and by client-side measurement, but was not directly verified; (3) the deeper reason the timeout was set to 300ms is outside scope. [verdict changed from APPROVED by enforcement rules]",
    "rounds_reviewed": 3
  }
}
```

## GET /investigations/{id}/evidence (excerpt)
```json
{
  "count": 155,
  "evidence (first 3)": [
    {
      "evidence_id": "topo-order-service-both-d2",
      "source_type": "dependency",
      "source_id": "graph:topology-v2",
      "timestamp": "2026-09-20T15:25:00Z",
      "description": "order-service depends on ['message-queue', 'payment-service', 'postgres', 'redis', 'user-service']; called by ['api-gateway'] (graph topology-v2)",
      "value": {
        "service": "order-service",
        "graph_version": "topology-v2",
        "upstream_dependencies": [
          "message-queue",
          "payment-service",
          "postgres",
          "redis",
          "user-service"
        ],
        "upstream_chains": [
          "order-service -> message-queue",
          "order-service -> payment-service",
          "order-service -> postgres",
          "order-service -> redis",
          "order-service -> user-service",
          "order-service -> payment-service -> auth-service",
          "order-service -> payment-service -> postgres",
          "order-service -> payment-service -> redis",
          "order-service -> user-service -> postgres",
          "order-service -> user-service -> redis"
        ],
        "downstream_dependents": [
          "api-gateway"
        ],
        "potentially_impacted": [
          "api-gateway"
        ],
        "topology_changes": [
          {
            "version": "topology-v2",
            "effective_from": "2026-09-15T00:00:00Z",
            "added_edge": "order-service -> redis"
          }
        ],
        "evidence_id": "topo-order-service-both-d2"
      },
      "reliability": "high",
      "service": "order-service",
      "task_id": null,
      "collected_by": "orchestrator",
      "tool_call_id": "call-9f8e5e87"
    },
    {
      "evidence_id": "dep-7cf38f2d",
      "source_type": "deployment",
      "source_id": "dep-7cf38f2d",
      "timestamp": "2026-09-20T14:40:00Z",
      "description": "Deployment of payment-service 5.8.0->5.8.1 at 2026-09-20T14:40:00Z (SUCCEEDED): Improve charge idempotency",
      "value": {
        "deployment_id": "dep-7cf38f2d",
        "service": "payment-service",
        "timestamp": "2026-09-20T14:40:00Z",
        "from_version": "5.8.0",
        "to_version": "5.8.1",
        "status": "SUCCEEDED",
        "changes": "Improve charge idempotency",
        "deployed_by": "ci-pipeline"
      },
      "reliability": "high",
      "service": "payment-service",
      "task_id": "task-24aee59dea",
      "collected_by": "dependency",
      "tool_call_id": "call-98e32c4a"
    },
    {
      "evidence_id": "cfg-7f81d14a",
      "source_type": "config",
      "source_id": "cfg-7f81d14a",
      "timestamp": "2026-09-20T15:22:00Z",
      "description": "Config change on order-service: payment_client.timeout_ms 3000 -> 300 at 2026-09-20T15:22:00Z (OPS-2375)",
      "value": {
        "change_id": "cfg-7f81d14a",
        "service": "order-service",
        "timestamp": "2026-09-20T15:22:00Z",
        "key": "payment_client.timeout_ms",
        "old_value": "3000",
        "new_value": "300",
        "author": "config-bot",
        "ticket": "OPS-2375",
        "diff": {
          "changed_setting": "payment_client.timeout_ms",
          "before": "3000",
          "after": "300",
          "numeric_ratio_after_over_before": 0.1
        }
      },
      "reliability": "high",
      "service": "order-service",
      "task_id": "task-24aee59dea",
      "collected_by": "dependency",
      "tool_call_id": "call-65a0
  ... (truncated)
```

## GET /investigations/{id}/timeline (excerpt)
```json
{
  "investigation_timeline (first 6)": [
    {
      "timestamp": "2026-11-09T18:26:26.904277Z",
      "actor": "orchestrator",
      "event": "investigation_started",
      "detail": {
        "incident": "INC-007"
      }
    },
    {
      "timestamp": "2026-11-09T18:26:32.269197Z",
      "actor": "orchestrator",
      "event": "message:task_assignment",
      "detail": {
        "to": "observability",
        "message_id": "msg-068158bad7"
      }
    },
    {
      "timestamp": "2026-11-09T18:26:32.269226Z",
      "actor": "orchestrator",
      "event": "message:task_assignment",
      "detail": {
        "to": "observability",
        "message_id": "msg-2d62077cfa"
      }
    },
    {
      "timestamp": "2026-11-09T18:26:32.269240Z",
      "actor": "orchestrator",
      "event": "message:task_assignment",
      "detail": {
        "to": "dependency",
        "message_id": "msg-23df63b277"
      }
    },
    {
      "timestamp": "2026-11-09T18:26:32.269246Z",
      "actor": "orchestrator",
      "event": "plan_created",
      "detail": {
        "tasks": 3,
        "parallel": true
      }
    },
    {
      "timestamp": "2026-11-09T18:26:32.270984Z",
      "actor": "orchestrator",
      "event": "wave_started",
      "detail": {
        "tasks": [
          "task-9146ce5606",
          "task-56c53f5b67",
          "task-24aee59dea"
        ]
      }
    }
  ],
  "incident_timeline (first 6)": [
    {
      "time": "2026-09-20T14:40:00Z",
      "label": "CONFIRMED FACT",
      "event": "Deployment of payment-service 5.8.0->5.8.1 at 2026-09-20T14:40:00Z (SUCCEEDED): Improve charge idempotency",
      "evidence_id": "dep-7cf38f2d"
    },
    {
      "time": "2026-09-20T14:56:04Z",
      "label": "OBSERVED EVIDENCE",
      "event": "First log: 6x WARN on notification-service: 'SMTP provider throttled 1 message' (first 2026-09-20T14:56:04Z, last 2026-09-20T15:47:49Z)",
      "evidence_id": "logpat-notification-service-54b86179"
    },
    {
      "time": "2026-09-20T14:56:51Z",
      "label": "OBSERVED EVIDENCE",
      "event": "First log: 7x WARN on auth-service: 'Login rate limit hit for user id u-49' (first 2026-09-20T14:56:51Z, last 2026-09-20T15:48:51Z)",
      "evidence_id": "logpat-auth-service-cc8d3b87"
    },
    {
      "time": "2026-09-20T15:00:17Z",
      "label": "OBSERVED EVIDENCE",
      "event": "First log: 3x WARN on payment-service: 'Card network soft decline (code 05) for charge ch_30' (first 2026-09-20T15:00:17Z, last 2026-09-20T15:37:11Z)",
      "evidence_id": "logpat-payment-service-7e9bf84f"
    },
    {
      "time": "2026-09-20T15:07:41Z",
      "label": "OBSERVED EVIDENCE",
      "event": "First log: 3x WARN on postgres: 'duration: 13302 ms statement: SELECT report_rollup()' (first 2026-09-20T15:07:41Z, last 2026-09-20T15:42:35Z)",
      "evidence_id": "logpat-postgres-44883ca5"
    },
    {
      "time": "2026-09-20T15:19:12Z",
      "label": "OBSERVED EVIDENCE",
      "event": "First log: 7x WARN on user-service: 'Deprecated API /v1/users/legacy called by client web-38' (first 2026-09-20T15:19:12Z, last 2026-09-20T15:49:40Z)",
      "evidence_id": "logpat-user-service-742b555e"
    }
  ]
}
```

## GET /evaluate/results (excerpt)
```json
{
  "status": "idle",
  "conditions": {
    "provider": "anthropic",
    "model": "claude-haiku-5-5",
    "effort": "low",
    "runs_per_incident": 3,
    "incidents": [
      "INC-001",
      "INC-002",
      "INC-003",
      "INC-004",
      "INC-005",
      "INC-006",
      "INC-007",
      "INC-008",
      "INC-009",
      "INC-010",
      "INC-011",
      "INC-012"
    ],
    "concurrency": 6,
    "config": {
      "max_rounds": 3,
      "max_tool_calls": 60,
      "max_tool_retries": 2,
      "max_agent_retries": 1,
      "max_agent_steps": 6,
      "tool_timeout_s": 2.0,
      "investigation_timeout_s": 300.0,
      "max_llm_calls": 80,
      "max_cost_usd": 0.25,
      "approve_confidence": 0.6,
      "parallelism": 4,
      "random_failure_rate": 0.0,
      "seed": 7
    },
    "wall_clock_s": 904.6,
    "global_spend_usd_after": 1.4489,
    "token_note": null
  },
  "skipped": []
}
```

## Error responses
Unknown incident, `POST /investigate {"incident_id":"INC-999"}`, returns `404`:
```json
{
  "detail": "Unknown incident INC-999"
}
```
Invalid config, `{"config":{"max_rounds":0}}`, returns `422`:
```json
{
  "detail": [
    {
      "type": "greater_than_equal",
      "loc": [
        "body",
        "config",
        "max_rounds"
      ],
      "msg": "Input should be greater than or equal to 1",
      "input": 0,
      "ctx": {
        "ge": 1
      }
    }
  ]
}
```
