# Agent coordination: a worked example

This traces INC-005 ("Payments slow right after release"). The trap in this incident is
a payment-service deployment at T0−8m, while postgres storage actually degraded at
T0−18m.

1. **Orchestrator** reads the report and calls `get_service_dependencies(payment-service)`, which shows payment-service calls `postgres`, `redis` and `auth-service`. It then submits a plan of independent tasks. Example: observability covers payment-service, order-service and postgres; dependency covers changes across all services.
2. **TaskManager** runs both tasks in one `asyncio.gather` wave, and both agents query their tools concurrently.
   - **Observability** finds postgres `disk_io_wait_ms` onset at about 11:22 (`met-postgres-disk_io_wait_ms-…`), the WARN `storage: volume vol-0a3f write latency degraded` log (`logpat-postgres-…`), and payment and order latency rising at about 11:27–11:28. It also notes that postgres CPU went *down*, not up.
   - **Dependency** finds `dep-31448d11` (payment-service 5.8.0 at 11:32) and no config changes.
   - Both send `FINDINGS` messages to the Orchestrator.
3. **Orchestrator** checks coverage (metrics exist for each affected service?) and forwards the findings to Reasoning.
4. **Reasoning** proposes two hypotheses:
   - H1: infrastructure_degradation in postgres, cause time 11:21.
   - H2: deployment_regression in payment-service, cause time 11:32, with `met-postgres-…` as contradicting evidence.

   `scoring.py` takes 0.30 off H2 because its cause comes after the first observed anomaly.
5. **Critic** gets both hypotheses without their scores, plus the pre-checks. For H2 the pre-checks flag `temporal_precedence` (blocking) and, if only `dep-…` is cited, `correlation_only` (blocking). The Critic can run its own `query_metrics(order-service)` to confirm that a service which was not deployed also slowed down. It rejects H2 and either approves H1 or asks for more evidence about the storage volume.
6. **Orchestrator** acts on the verdict:
   - On approval, it decides the final status.
   - On NEEDS_MORE_EVIDENCE, it creates a round-2 follow-up task. Reasoning then reruns with the new evidence and the critic feedback, and the Critic re-reviews.
7. **Reporting** gets the validated payload with the status already fixed, and writes the summary and actions. `report_generator.py` assembles the labelled report.

The full message log for any run is available at `GET /investigations/{id}` (in
`state.messages`), and each step's timestamp is at `GET /investigations/{id}/timeline`.
