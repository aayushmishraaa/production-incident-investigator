"""Deterministic synthetic operational-data generator.

Produces, per incident environment:
  data/incidents/<ID>.json        incident report (visible to agents)
  data/logs/<ID>.jsonl            application/infra logs
  data/metrics/<ID>.json          1-minute metric series per service
  data/deployments/<ID>.json      deployment history
  data/configurations/<ID>.json   configuration change history
  data/failures/<ID>.json         tool fault-injection profile (environment behaviour)
  data/ground_truth/<ID>.json     ground truth -- ONLY read by app/evaluation/ground_truth.py
and global files:
  data/dependencies/service_graph.json
  data/historical_incidents/historical_incidents.json

Run:  python scripts/generate_dataset.py
"""
from __future__ import annotations

import hashlib
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "data"
UTC = timezone.utc

BASELINES = {
    "api-gateway": dict(cpu_pct=35, memory_pct=50, request_rate=1200, error_rate=0.5, p50_latency_ms=40, p95_latency_ms=120, p99_latency_ms=250, timeout_rate=0.1),
    "auth-service": dict(cpu_pct=30, memory_pct=45, request_rate=900, error_rate=0.3, p50_latency_ms=15, p95_latency_ms=45, p99_latency_ms=90, db_conn_util_pct=30, timeout_rate=0.05),
    "payment-service": dict(cpu_pct=40, memory_pct=55, request_rate=300, error_rate=0.8, p50_latency_ms=60, p95_latency_ms=150, p99_latency_ms=300, db_conn_util_pct=35, timeout_rate=0.1),
    "user-service": dict(cpu_pct=30, memory_pct=50, request_rate=500, error_rate=0.4, p50_latency_ms=25, p95_latency_ms=80, p99_latency_ms=160, db_conn_util_pct=30, timeout_rate=0.05),
    "order-service": dict(cpu_pct=45, memory_pct=55, request_rate=250, error_rate=0.6, p50_latency_ms=80, p95_latency_ms=200, p99_latency_ms=400, db_conn_util_pct=30, timeout_rate=0.1),
    "notification-service": dict(cpu_pct=20, memory_pct=40, request_rate=150, error_rate=0.2, p50_latency_ms=30, p95_latency_ms=90, p99_latency_ms=200, timeout_rate=0.05),
    "postgres": dict(cpu_pct=35, memory_pct=65, request_rate=2500, error_rate=0.05, p50_latency_ms=3, p95_latency_ms=12, p99_latency_ms=25, db_conn_util_pct=40, disk_io_wait_ms=2),
    "redis": dict(cpu_pct=15, memory_pct=60, request_rate=6000, error_rate=0.01, p50_latency_ms=0.5, p95_latency_ms=1.5, p99_latency_ms=3, cache_hit_rate=95),
    "message-queue": dict(cpu_pct=20, memory_pct=45, request_rate=400, error_rate=0.0, p50_latency_ms=4, p95_latency_ms=10, p99_latency_ms=20),
}

NOISE_LOGS = {
    "api-gateway": [("INFO", "GET /v1/health 200 3ms"), ("INFO", "Routed {n} requests in last minute"), ("WARN", "Slow client upload from 10.4.{n}.12 (1.9MB)")],
    "auth-service": [("INFO", "JWKS cache refreshed (keys=4)"), ("INFO", "Issued {n} tokens in last minute"), ("WARN", "Login rate limit hit for user id u-{n}")],
    "payment-service": [("INFO", "Processed {n} charges in last minute"), ("INFO", "Settlement batch heartbeat ok"), ("WARN", "Card network soft decline (code 05) for charge ch_{n}")],
    "user-service": [("INFO", "Served {n} profile reads in last minute"), ("INFO", "GET /v1/users/me 200 21ms"), ("WARN", "Deprecated API /v1/users/legacy called by client web-{n}")],
    "order-service": [("INFO", "Created {n} orders in last minute"), ("INFO", "Outbox relay published {n} events"), ("WARN", "Inventory reservation retry for sku-{n}")],
    "notification-service": [("INFO", "Sent {n} emails"), ("INFO", "Consumer lag 0 on topic order-events"), ("WARN", "SMTP provider throttled 1 message")],
    "postgres": [("INFO", "checkpoint complete: wrote {n} buffers"), ("INFO", "autovacuum: processing table public.orders"), ("WARN", "duration: 1{n}02 ms statement: SELECT report_rollup()")],
    "redis": [("INFO", "DB saved on disk"), ("INFO", "{n} changes in 60 seconds. Saving..."), ("INFO", "Background saving terminated with success")],
    "message-queue": [("INFO", "Queue order-events depth=0"), ("INFO", "Consumer group notif-cg rebalanced (members=3)"), ("INFO", "Published {n} messages")],
}

SERVICE_GRAPH = {
    "services": list(BASELINES.keys()),
    "versions": [
        {
            "version": "topology-v1",
            "effective_from": "2026-01-01T00:00:00Z",
            "edges": [
                ["api-gateway", "auth-service"], ["api-gateway", "payment-service"], ["api-gateway", "user-service"],
                ["api-gateway", "order-service"], ["payment-service", "auth-service"], ["payment-service", "postgres"],
                ["payment-service", "redis"], ["order-service", "payment-service"], ["order-service", "postgres"],
                ["order-service", "message-queue"], ["order-service", "user-service"], ["user-service", "postgres"],
                ["user-service", "redis"], ["auth-service", "redis"], ["auth-service", "postgres"],
                ["notification-service", "message-queue"],
            ],
        },
        {
            "version": "topology-v2",
            "effective_from": "2026-09-15T00:00:00Z",
            "edges": [
                ["api-gateway", "auth-service"], ["api-gateway", "payment-service"], ["api-gateway", "user-service"],
                ["api-gateway", "order-service"], ["payment-service", "auth-service"], ["payment-service", "postgres"],
                ["payment-service", "redis"], ["order-service", "payment-service"], ["order-service", "postgres"],
                ["order-service", "message-queue"], ["order-service", "user-service"], ["order-service", "redis"],
                ["user-service", "postgres"], ["user-service", "redis"], ["auth-service", "redis"],
                ["auth-service", "postgres"], ["notification-service", "message-queue"],
                ["notification-service", "user-service"],
            ],
        },
    ],
}

HISTORICAL = [
    dict(id="HIST-2025-014", title="Payment latency from leaked DB connections", services=["payment-service", "postgres"],
         symptoms=["high latency", "connection acquisition timeout", "db connection pool saturated", "error rate increase"],
         root_cause="Connection leak in refund path held pooled connections; pool exhausted.",
         root_cause_category="db_connection_pool_exhaustion",
         remediation=["Restart payment-service pods to release connections", "Fix leak (try-with-resources)", "Enable leak detection alerting"]),
    dict(id="HIST-2025-022", title="Auth outage after JWT library upgrade", services=["auth-service", "api-gateway"],
         symptoms=["error rate spike", "500 errors", "token validation failure", "after deployment"],
         root_cause="New release mis-parsed JWKS keys.", root_cause_category="deployment_regression",
         remediation=["Roll back auth-service", "Add contract tests for JWKS key types"]),
    dict(id="HIST-2025-031", title="Checkout slow due to slow identity calls", services=["auth-service", "payment-service"],
         symptoms=["high latency", "upstream timeout", "slow downstream calls"],
         root_cause="auth-service degraded by slow identity-provider JWKS refresh.", root_cause_category="upstream_dependency_degradation",
         remediation=["Increase JWKS cache TTL", "Add timeouts and circuit breaker around auth calls"]),
    dict(id="HIST-2025-040", title="Order service CPU saturation from batch job", services=["order-service"],
         symptoms=["high cpu", "high latency", "gc pauses", "thread pool saturation"],
         root_cause="Reconciliation batch job scheduled on serving nodes.", root_cause_category="resource_saturation",
         remediation=["Move batch jobs to dedicated workers", "Throttle batch size"]),
    dict(id="HIST-2025-047", title="Database storage latency degradation", services=["postgres", "payment-service", "order-service"],
         symptoms=["slow queries", "high latency", "statement timeout", "io wait"],
         root_cause="Cloud block storage volume degraded.", root_cause_category="infrastructure_degradation",
         remediation=["Fail over to replica", "Migrate volume", "Alert on disk IO wait"]),
    dict(id="HIST-2025-055", title="Timeouts after client timeout misconfiguration", services=["order-service", "payment-service"],
         symptoms=["timeout rate spike", "circuit breaker open", "error rate increase"],
         root_cause="Client timeout configured in seconds instead of milliseconds.", root_cause_category="configuration_regression",
         remediation=["Revert configuration", "Validate config ranges in CI"]),
    dict(id="HIST-2025-061", title="Redis evictions overloaded database", services=["redis", "postgres", "user-service"],
         symptoms=["cache hit rate drop", "evictions", "database cpu high", "high latency"],
         root_cause="Redis reached maxmemory; LRU eviction caused cache misses and DB load.", root_cause_category="cache_degradation",
         remediation=["Increase Redis memory", "Reduce cached payload size", "Alert on hit rate"]),
    dict(id="HIST-2025-068", title="Retry storm from mobile client", services=["api-gateway", "auth-service"],
         symptoms=["request rate spike", "high cpu", "429 errors", "high latency"],
         root_cause="Mobile release ignored Retry-After causing retry storm.", root_cause_category="traffic_surge",
         remediation=["Block/limit offending client version", "Enforce server-side backoff"]),
    dict(id="HIST-2025-073", title="User service DB errors from node network issue", services=["user-service", "postgres"],
         symptoms=["connection refused", "connection reset", "database errors"],
         root_cause="Node conntrack table exhaustion dropped DB packets for one service.", root_cause_category="infrastructure_degradation",
         remediation=["Raise nf_conntrack_max", "Reschedule pods", "Alert on conntrack usage"]),
    dict(id="HIST-2025-080", title="Notification backlog after deploy", services=["notification-service", "message-queue"],
         symptoms=["queue depth increase", "consumer lag"],
         root_cause="Deployment reduced consumer concurrency.", root_cause_category="deployment_regression",
         remediation=["Roll back", "Alert on consumer lag"]),
]


def hid(*parts: object) -> str:
    return hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:8]


def iso(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------- scenario specs
# effects: (service, metric, start_offset_min, ramp_min, target_value)
# events : (service, severity, message, start_offset, end_offset, count, is_key)
# gaps   : (service, metric|'*', start_offset, end_offset)

SCENARIOS = [
    dict(
        id="INC-001", t0="2026-09-02T14:00:00Z", severity="SEV2",
        title="Payment API latency spike", affected=["payment-service", "api-gateway"],
        description="Customers report checkout taking 3-5 seconds; payment API P95 latency alarm fired. Some payments failing with 5xx.",
        effects=[("payment-service", "db_conn_util_pct", -12, 10, 99), ("payment-service", "p95_latency_ms", 0, 3, 2800),
                 ("payment-service", "p99_latency_ms", 0, 3, 5200), ("payment-service", "p50_latency_ms", 0, 3, 900),
                 ("payment-service", "error_rate", 0, 3, 22), ("payment-service", "timeout_rate", 0, 3, 18),
                 ("api-gateway", "p95_latency_ms", 1, 3, 1900), ("api-gateway", "error_rate", 1, 3, 9),
                 ("postgres", "db_conn_util_pct", -10, 8, 62), ("order-service", "p95_latency_ms", 1, 4, 700)],
        events=[("payment-service", "WARN", "HikariPool-payment - Connection leak detection triggered for connection conn-{n}, held > 30000 ms by RefundService.processPartialRefund", -15, 0, 9, True),
                ("payment-service", "ERROR", "Timeout acquiring connection from pool payment-db-pool after 5000ms (active=50, idle=0, waiting={n})", 0, 25, 30, True),
                ("api-gateway", "ERROR", "Upstream payment-service responded 503 for POST /v1/payments (latency {n}ms)", 1, 25, 12, False),
                ("notification-service", "INFO", "Starting notification-service v3.4.1 (build 8812)", -6, -6, 1, False)],
        deployments=[("notification-service", -6, "3.4.0", "3.4.1", "Update email templates for receipts", "SUCCEEDED", False),
                     ("user-service", -300, "7.0.9", "7.1.0", "Profile avatar resizing", "SUCCEEDED", False)],
        configs=[("api-gateway", -180, "routes.cache_ttl_s", "30", "60", False)],
        gt=dict(category="db_connection_pool_exhaustion", service="payment-service",
                description="Connection leak in RefundService held pooled DB connections; payment-db-pool exhausted causing acquisition timeouts and latency.",
                expected_behaviour="Identify pool exhaustion in payment-service; do not blame the unrelated notification-service deployment; postgres itself healthy.",
                key_metric_prefixes=["met-payment-service-db_conn_util_pct"], decoy_category="deployment_regression",
                remediation=["Restart/scale payment-service to release leaked connections", "Fix connection leak in RefundService", "Alert on pool utilisation > 85%"])),
    dict(
        id="INC-002", t0="2026-09-05T09:30:00Z", severity="SEV1",
        title="Login and checkout failures", affected=["api-gateway", "auth-service", "payment-service"],
        description="Sharp increase in 5xx errors on login and checkout endpoints. Users being logged out.",
        effects=[("auth-service", "error_rate", -1, 1, 27), ("auth-service", "p95_latency_ms", -1, 2, 110),
                 ("api-gateway", "error_rate", -1, 2, 19), ("payment-service", "error_rate", 0, 2, 14)],
        events=[("auth-service", "ERROR", "TokenValidationException: unsupported key type 'EC' in JWKS (validator=jose-4.2, kid=k{n})", -1, 25, 28, True),
                ("auth-service", "INFO", "Starting auth-service v2.14.0 (build 4410)", -2, -2, 1, True),
                ("api-gateway", "WARN", "auth-service returned 500 for /v1/token/verify (req {n})", -1, 25, 15, False),
                ("payment-service", "ERROR", "Authorization check failed: upstream auth-service 500 (charge ch_{n})", 0, 25, 10, False),
                ("payment-service", "WARN", "Retrying request to auth-service (attempt 2/3)", 0, 25, 8, False)],
        deployments=[("auth-service", -2, "2.13.4", "2.14.0", "Migrate JWT validation to jose-4.2; refactor token cache", "SUCCEEDED", True)],
        configs=[("user-service", -20, "feature.profile_badges", "false", "true", False)],
        gt=dict(category="deployment_regression", service="auth-service",
                description="auth-service v2.14.0 broke EC JWKS key validation causing token verification errors.",
                expected_behaviour="Link the error onset (1 minute after deploy) and TokenValidationException to the auth-service release.",
                key_metric_prefixes=["met-auth-service-error_rate"], decoy_category="configuration_regression",
                remediation=["Roll back auth-service to 2.13.4", "Add JWKS key-type contract tests", "Canary deployments with error-rate gates"])),
    dict(
        id="INC-003", t0="2026-09-08T18:10:00Z", severity="SEV2",
        title="Payment service slow responses", affected=["payment-service"],
        description="Payment service latency elevated for 10+ minutes. Payment pods look healthy in the dashboard.",
        effects=[("auth-service", "p95_latency_ms", -3, 4, 2400), ("auth-service", "p99_latency_ms", -3, 4, 4000),
                 ("auth-service", "cpu_pct", -3, 4, 48), ("auth-service", "error_rate", -2, 4, 3),
                 ("payment-service", "p95_latency_ms", -1, 3, 2600), ("payment-service", "p99_latency_ms", -1, 3, 3400),
                 ("payment-service", "timeout_rate", 0, 3, 6), ("api-gateway", "p95_latency_ms", -2, 3, 1500),
                 ("order-service", "p95_latency_ms", 0, 4, 1900)],
        events=[("auth-service", "WARN", "Slow JWKS refresh from identity-provider: {n}0 ms", -4, 25, 12, True),
                ("auth-service", "WARN", "Request queue time high for /v1/token/verify: {n}00ms", -3, 25, 10, True),
                ("payment-service", "WARN", "Call to auth-service /v1/token/verify took 2{n}0ms", -1, 25, 20, True),
                ("payment-service", "ERROR", "Upstream timeout calling auth-service after 3000ms (charge ch_{n})", 0, 25, 9, False),
                ("payment-service", "DEBUG", "SQL SELECT * FROM charges WHERE id=$1 took {n}ms", -30, 25, 15, False)],
        deployments=[("order-service", -400, "4.2.0", "4.2.1", "Fix rounding in tax calc", "SUCCEEDED", False)],
        configs=[("payment-service", -35, "log.level", "INFO", "DEBUG", False)],
        gt=dict(category="upstream_dependency_degradation", service="auth-service",
                description="auth-service latency (slow JWKS refresh) propagated to payment-service, which was internally healthy.",
                expected_behaviour="Recognise payment-service resources are healthy and its latency tracks auth-service latency; ignore log-level config change.",
                key_metric_prefixes=["met-auth-service-p95_latency_ms", "met-auth-service-p99_latency_ms"], decoy_category="configuration_regression",
                remediation=["Mitigate auth-service latency (scale, raise JWKS cache TTL)", "Add circuit breaker/timeouts in payment-service auth client", "Alert on auth-service p95"])),
    dict(
        id="INC-004", t0="2026-09-11T02:15:00Z", severity="SEV2",
        title="Order API timeouts overnight", affected=["order-service"],
        description="Order creation latency high and intermittent timeouts during overnight window.",
        effects=[("order-service", "cpu_pct", -8, 7, 98), ("order-service", "p95_latency_ms", -2, 3, 3100),
                 ("order-service", "p50_latency_ms", -2, 3, 1200), ("order-service", "error_rate", 0, 3, 4),
                 ("order-service", "timeout_rate", 0, 3, 6), ("order-service", "memory_pct", -8, 8, 74),
                 ("postgres", "cpu_pct", -8, 6, 50)],
        events=[("order-service", "INFO", "Scheduled job invoice-reconciliation started (batch_size=500000, node=order-7f9c)", -10, -10, 1, True),
                ("order-service", "WARN", "GC pause {n}40ms (G1 Evacuation Pause)", -7, 25, 14, True),
                ("order-service", "WARN", "Thread pool order-worker saturated: active=200 queue=1{n}50", -3, 25, 12, True),
                ("order-service", "ERROR", "Request POST /v1/orders exceeded deadline 5000ms", 0, 25, 8, False),
                ("payment-service", "WARN", "Elevated latency on /v1/refunds p95=400ms", -40, -38, 2, False)],
        deployments=[("payment-service", -240, "5.7.2", "5.7.3", "Dependency bumps", "SUCCEEDED", False)],
        configs=[],
        gt=dict(category="resource_saturation", service="order-service",
                description="CPU saturation on order-service caused by a reconciliation batch job running on serving nodes.",
                expected_behaviour="Identify CPU saturation as cause of latency; request rate flat so not traffic surge.",
                key_metric_prefixes=["met-order-service-cpu_pct"], decoy_category="traffic_surge",
                remediation=["Stop/throttle the reconciliation job", "Move batch jobs to dedicated workers", "Alert on CPU > 85% for 5m"])),
    dict(
        id="INC-005", t0="2026-09-14T11:40:00Z", severity="SEV1",
        title="Payments slow right after release", affected=["payment-service", "order-service"],
        description="Payment and order latency degraded shortly after the payment-service 5.8.0 release. Team suspects the release.",
        effects=[("postgres", "disk_io_wait_ms", -18, 3, 140), ("postgres", "p95_latency_ms", -17, 3, 900),
                 ("postgres", "p99_latency_ms", -17, 3, 1800), ("postgres", "cpu_pct", -17, 3, 28),
                 ("postgres", "db_conn_util_pct", -15, 4, 88), ("payment-service", "p95_latency_ms", -13, 4, 2300),
                 ("payment-service", "error_rate", -12, 4, 9), ("order-service", "p95_latency_ms", -13, 4, 2100),
                 ("user-service", "p95_latency_ms", -12, 4, 900), ("payment-service", "db_conn_util_pct", -13, 4, 80)],
        events=[("postgres", "WARN", "storage: volume vol-0a3f write latency degraded (avg {n}5ms)", -19, 25, 8, True),
                ("postgres", "ERROR", "checkpoint took 4{n}.2 s; WAL write slow", -16, 25, 6, True),
                ("payment-service", "ERROR", "SQL query exceeded 2000ms statement timeout (charges.insert) req {n}", -12, 25, 18, False),
                ("order-service", "ERROR", "SQL query exceeded 2000ms statement timeout (orders.update) req {n}", -12, 25, 10, False),
                ("payment-service", "INFO", "Starting payment-service v5.8.0 (build 9921)", -8, -8, 1, False)],
        deployments=[("payment-service", -8, "5.7.3", "5.8.0", "Add idempotency-key header logging", "SUCCEEDED", False)],
        configs=[],
        gt=dict(category="infrastructure_degradation", service="postgres",
                description="Postgres storage volume latency degraded ~10 min before the payment deployment; all DB clients slowed.",
                expected_behaviour="Reject the deployment hypothesis because degradation started before deploy and affects services not deployed.",
                key_metric_prefixes=["met-postgres-disk_io_wait_ms", "met-postgres-p95_latency_ms"], decoy_category="deployment_regression",
                remediation=["Fail over postgres to healthy replica/volume", "Engage cloud provider", "Alert on disk IO wait"])),
    dict(
        id="INC-006", t0="2026-09-17T21:05:00Z", severity="SEV2",
        title="User profile errors", affected=["user-service"],
        description="User profile endpoints failing intermittently. Logs mention database errors.",
        effects=[("user-service", "error_rate", -2, 2, 31), ("user-service", "p95_latency_ms", -2, 2, 1500),
                 ("user-service", "timeout_rate", -2, 2, 9)],
        events=[("user-service", "ERROR", "PSQLException: Connection to postgres-primary:5432 refused (attempt {n})", -2, 25, 20, True),
                ("user-service", "ERROR", "I/O error: connection reset by peer (postgres-primary:5432)", -2, 25, 10, True),
                ("user-service", "WARN", "kernel: nf_conntrack: table full, dropping packet (node usr-node-3)", -3, -3, 1, True),
                ("postgres", "INFO", "metrics-agent: export queue backlog, telemetry delayed", -6, -6, 1, False)],
        gaps=[("postgres", "*", -5, 25)],
        deployments=[],
        configs=[],
        gt=dict(category="infrastructure_degradation", service="user-service",
                description="Network (conntrack) exhaustion on user-service node dropped DB connections; postgres itself healthy, its telemetry was delayed.",
                expected_behaviour="Recognise contradiction (DB error logs vs healthy/missing DB metrics, other DB clients healthy) and lower confidence; INCONCLUSIVE acceptable.",
                acceptable_inconclusive=True,
                key_metric_prefixes=["met-user-service-error_rate"], decoy_category="db_connection_pool_exhaustion",
                remediation=["Raise conntrack limits / reschedule user-service pods", "Fix postgres telemetry export lag"])),
    dict(
        id="INC-007", t0="2026-09-20T15:25:00Z", severity="SEV2",
        title="Order checkout failing", affected=["order-service"],
        description="Order checkout error rate above 25%. Payment team says their service is healthy.",
        effects=[("order-service", "timeout_rate", -2, 1, 34), ("order-service", "error_rate", -2, 1, 29),
                 ("order-service", "p95_latency_ms", -2, 1, 420), ("payment-service", "request_rate", -2, 2, 210)],
        events=[("order-service", "ERROR", "PaymentClient: request to payment-service timed out after 300ms (POST /v1/charges, req {n})", -2, 25, 30, True),
                ("order-service", "WARN", "Circuit breaker payment-service OPEN (failure ratio 0.{n})", -1, 25, 8, False),
                ("order-service", "INFO", "Configuration reloaded (version 42)", -3, -3, 1, True),
                ("order-service", "WARN", "Retry budget exhausted for payment calls", 0, 25, 6, False)],
        deployments=[("payment-service", -45, "5.8.0", "5.8.1", "Improve charge idempotency", "SUCCEEDED", False)],
        configs=[("order-service", -3, "payment_client.timeout_ms", "3000", "300", True)],
        gt=dict(category="configuration_regression", service="order-service",
                description="Config change set order-service payment_client.timeout_ms 3000->300; calls to healthy payment-service time out.",
                expected_behaviour="Tie timeout spike to config change; payment-service metrics healthy; older payment deploy unrelated.",
                key_metric_prefixes=["met-order-service-timeout_rate"], decoy_category="deployment_regression",
                remediation=["Revert payment_client.timeout_ms to 3000", "Validate timeout ranges in config CI"])),
    dict(
        id="INC-008", t0="2026-09-23T12:50:00Z", severity="SEV2",
        title="Database CPU high and slow user pages", affected=["user-service", "postgres"],
        description="Postgres CPU alarm firing and user profile pages slow. DBA suspects a bad query.",
        effects=[("redis", "memory_pct", -20, 10, 99), ("redis", "cache_hit_rate", -6, 4, 38), ("redis", "p95_latency_ms", -6, 4, 25),
                 ("redis", "cpu_pct", -6, 4, 70), ("postgres", "cpu_pct", -5, 4, 92), ("postgres", "request_rate", -5, 4, 9000),
                 ("postgres", "db_conn_util_pct", -5, 4, 85), ("user-service", "p95_latency_ms", -4, 4, 1800),
                 ("payment-service", "p95_latency_ms", -4, 4, 900), ("user-service", "error_rate", -3, 4, 5)],
        events=[("redis", "WARN", "Evicting keys: used_memory 7.9{n}G reached maxmemory 8G (policy allkeys-lru), evicted_keys=18{n}233", -7, 25, 12, True),
                ("user-service", "WARN", "Cache miss for user profile u-{n}, falling back to DB", -5, 25, 25, False),
                ("user-service", "ERROR", "Query timeout on users table after 2000ms (req {n})", -3, 25, 8, False),
                ("user-service", "INFO", "Feature flag profile_v2_cache enabled (avg cached payload 4.1x larger)", -40, -40, 1, True),
                ("postgres", "WARN", "duration: 2{n}10 ms statement: SELECT * FROM users WHERE id = $1", -4, 25, 10, False)],
        deployments=[],
        configs=[("user-service", -40, "feature.profile_v2_cache", "false", "true", True)],
        gt=dict(category="cache_degradation", service="redis",
                description="Redis hit maxmemory (larger cached payloads); evictions dropped hit rate, shifting load to postgres.",
                expected_behaviour="Identify postgres CPU as a symptom of cache degradation (hit rate drop precedes DB load).",
                key_metric_prefixes=["met-redis-cache_hit_rate", "met-redis-memory_pct"], decoy_category="resource_saturation",
                remediation=["Increase Redis maxmemory / shard", "Disable profile_v2_cache or shrink payload", "Alert on hit rate and evictions"])),
    dict(
        id="INC-009", t0="2026-09-26T08:00:00Z", severity="SEV2",
        title="User API errors during morning peak", affected=["user-service", "api-gateway"],
        description="Elevated errors on user endpoints. Observability backend reported degraded performance this morning.",
        effects=[("user-service", "error_rate", -3, 1, 24), ("user-service", "p95_latency_ms", -3, 2, 700),
                 ("api-gateway", "error_rate", -3, 2, 8)],
        events=[("user-service", "ERROR", "NullPointerException in ProfileBatchLoader.load (user-service v7.2.0) req {n}", -3, 25, 24, True),
                ("user-service", "INFO", "Starting user-service v7.2.0 (build 3307)", -4, -4, 1, True),
                ("api-gateway", "WARN", "user-service returned 500 for GET /v1/users/{n}", -3, 25, 10, False)],
        deployments=[("user-service", -4, "7.1.3", "7.2.0", "Switch ORM to batch loader", "SUCCEEDED", True)],
        configs=[],
        failures={"query_metrics": {"fail_first_n": 2, "error": "TOOL_TIMEOUT"},
                  "query_logs": {"partial": True, "drop_fraction": 0.5},
                  "get_deployments": {"fail_first_n": 1, "error": "SERVICE_UNAVAILABLE"}},
        gt=dict(category="deployment_regression", service="user-service",
                description="user-service v7.2.0 introduced NPE in ProfileBatchLoader.",
                expected_behaviour="Retry failed tools, preserve partial findings, report uncertainty from partial logs.",
                key_metric_prefixes=["met-user-service-error_rate"], decoy_category=None,
                remediation=["Roll back user-service to 7.1.3", "Add null-safety tests for batch loader"])),
    dict(
        id="INC-010", t0="2026-09-29T19:45:00Z", severity="SEV3",
        title="Intermittent gateway latency", affected=["api-gateway"],
        description="Some customers report occasional slowness. No clear alarm; P99 looks a bit higher than usual.",
        effects=[("api-gateway", "p99_latency_ms", -5, 2, 520), ("api-gateway", "p95_latency_ms", -5, 2, 150)],
        events=[("api-gateway", "INFO", "Routed {n} requests in last minute", -5, 25, 4, False)],
        gaps=[("api-gateway", "*", 2, 25), ("auth-service", "*", -10, 25), ("user-service", "*", -10, 25),
              ("payment-service", "*", -10, 25), ("order-service", "*", -10, 25)],
        deployments=[],
        configs=[],
        failures={"query_logs": {"partial": True, "drop_fraction": 0.7}},
        gt=dict(category="unknown", service=None,
                description="No determinable root cause in available data; telemetry incomplete.",
                expected_behaviour="Return INCONCLUSIVE rather than inventing a root cause.",
                expected_inconclusive=True, key_metric_prefixes=[], decoy_category=None,
                remediation=["Restore missing telemetry", "Add gateway latency breakdown tracing"])),
    dict(
        id="INC-011", t0="2026-10-02T20:00:00Z", severity="SEV2",
        title="Platform-wide slowness and 429s", affected=["api-gateway", "auth-service", "user-service"],
        description="Widespread latency and HTTP 429 errors. A user-service release went out shortly before.",
        effects=[("api-gateway", "request_rate", -5, 3, 4100), ("api-gateway", "cpu_pct", -5, 3, 88),
                 ("api-gateway", "error_rate", -4, 3, 7), ("api-gateway", "p95_latency_ms", -4, 3, 1100),
                 ("auth-service", "request_rate", -5, 3, 3000), ("auth-service", "cpu_pct", -5, 3, 78),
                 ("auth-service", "p95_latency_ms", -4, 3, 600), ("user-service", "request_rate", -5, 3, 1700),
                 ("user-service", "cpu_pct", -5, 3, 66), ("user-service", "p95_latency_ms", -4, 3, 700)],
        events=[("api-gateway", "WARN", "Rate limiter: 3{n}% of requests from client_id=mobile-ios-7.4.0 are retries (Retry-After ignored)", -5, 25, 10, True),
                ("api-gateway", "INFO", "Top client by RPS: mobile-ios-7.4.0 ({n}00 rps)", -4, 25, 6, True),
                ("api-gateway", "WARN", "429 Too Many Requests returned to client {n}", -4, 25, 10, False),
                ("user-service", "INFO", "Starting user-service v7.1.3 (build 3290)", -12, -12, 1, False)],
        deployments=[("user-service", -12, "7.1.2", "7.1.3", "Copy changes on profile page", "SUCCEEDED", False)],
        configs=[],
        gt=dict(category="traffic_surge", service="api-gateway",
                description="Retry storm from mobile-ios-7.4.0 tripled gateway traffic and saturated downstream services.",
                expected_behaviour="Identify traffic surge (request rate tripled) as cause; user-service deploy is a decoy.",
                key_metric_prefixes=["met-api-gateway-request_rate"], decoy_category="deployment_regression",
                remediation=["Rate limit / block mobile-ios-7.4.0 retries", "Ship client fix honouring Retry-After"])),
    dict(
        id="INC-012", t0="2026-10-05T10:10:00Z", severity="SEV2",
        title="Payment connection pool timeouts", affected=["payment-service"],
        description="Payment API latency and errors; logs full of connection pool timeouts. Looks like the pool exhaustion we had last year.",
        effects=[("payment-service", "db_conn_util_pct", -5, 1, 100), ("payment-service", "p95_latency_ms", -4, 2, 2400),
                 ("payment-service", "error_rate", -4, 2, 17), ("payment-service", "timeout_rate", -4, 2, 12),
                 ("postgres", "db_conn_util_pct", -5, 2, 22)],
        events=[("payment-service", "ERROR", "Timeout acquiring connection from pool payment-db-pool after 5000ms (active=10, idle=0, waiting={n})", -4, 25, 30, True),
                ("payment-service", "INFO", "Configuration reloaded: db.pool.max_size=10 (version 77)", -6, -6, 1, True)],
        deployments=[],
        configs=[("payment-service", -6, "db.pool.max_size", "50", "10", True)],
        gt=dict(category="configuration_regression", service="payment-service",
                description="db.pool.max_size reduced 50->10 by config change; pool saturates at normal load (no leak).",
                expected_behaviour="Identify the config change as the cause of pool exhaustion rather than stopping at the symptom or historical analogy.",
                key_metric_prefixes=["met-payment-service-db_conn_util_pct"], decoy_category="db_connection_pool_exhaustion",
                remediation=["Revert db.pool.max_size to 50", "Add config guardrails for pool sizes"])),
]


def ramp(value_base: float, target: float, minute: int, start: int, ramp_len: int) -> float:
    if minute < start:
        return value_base
    if ramp_len <= 0 or minute >= start + ramp_len:
        return target
    frac = (minute - start + 1) / (ramp_len + 1)
    return value_base + (target - value_base) * frac


def generate_metrics(sc: dict, rng: random.Random, t0: datetime) -> dict:
    out: dict = {}
    effects = sc.get("effects", [])
    gaps = sc.get("gaps", [])
    for svc, base in BASELINES.items():
        out[svc] = {}
        for metric, bval in base.items():
            series = []
            for minute in range(-60, 31):
                ts = t0 + timedelta(minutes=minute)
                val = float(bval)
                for (s, m, start, rl, tgt) in effects:
                    if s == svc and m == metric:
                        val = ramp(val, tgt, minute, start, rl)
                noise = rng.gauss(0, 0.04) if metric not in ("cache_hit_rate",) else rng.gauss(0, 0.005)
                val = max(0.0, val * (1 + noise))
                if metric.endswith("_pct") or metric == "cache_hit_rate":
                    val = min(val, 100.0)
                missing = any(g[0] == svc and (g[1] == "*" or g[1] == metric) and g[2] <= minute <= g[3] for g in gaps)
                series.append([iso(ts), None if missing else round(val, 3)])
            out[svc][metric] = series
    return out


def generate_logs(sc: dict, rng: random.Random, t0: datetime) -> tuple[list[dict], list[str]]:
    logs: list[dict] = []
    key_ids: list[str] = []
    for svc, templates in NOISE_LOGS.items():
        minute = -60
        while minute <= 30:
            sev, msg = rng.choice(templates)
            ts = t0 + timedelta(minutes=minute, seconds=rng.randint(0, 59))
            logs.append(dict(timestamp=iso(ts), service=svc, severity=sev, message=msg.format(n=rng.randint(10, 99))))
            minute += rng.randint(2, 5)
    for (svc, sev, msg, start, end, count, is_key) in sc.get("events", []):
        for i in range(count):
            if count == 1 or end == start:
                off_s = start * 60 + (i * 7)
            else:
                off_s = int(start * 60 + (end - start) * 60 * i / (count - 1)) + rng.randint(0, 20)
            ts = t0 + timedelta(seconds=off_s)
            rec = dict(timestamp=iso(ts), service=svc, severity=sev, message=msg.format(n=rng.randint(10, 99)))
            rec["_key"] = is_key
            logs.append(rec)
    logs.sort(key=lambda r: (r["timestamp"], r["service"], r["message"]))
    for idx, rec in enumerate(logs):
        rec["log_id"] = f"log-{hid(sc['id'], idx, rec['message'])}"
        if rec.pop("_key", False):
            key_ids.append(rec["log_id"])
    return logs, key_ids


def main() -> None:
    for sub in ["incidents", "logs", "metrics", "deployments", "configurations", "dependencies",
                "historical_incidents", "ground_truth", "failures"]:
        (ROOT / sub).mkdir(parents=True, exist_ok=True)

    (ROOT / "dependencies" / "service_graph.json").write_text(json.dumps(SERVICE_GRAPH, indent=2))
    (ROOT / "historical_incidents" / "historical_incidents.json").write_text(json.dumps(HISTORICAL, indent=2))

    for sc in SCENARIOS:
        rng = random.Random(hid(sc["id"]))
        t0 = datetime.fromisoformat(sc["t0"].replace("Z", "+00:00"))
        incident = dict(incident_id=sc["id"], title=sc["title"], description=sc["description"], severity=sc["severity"],
                        reported_at=iso(t0 + timedelta(minutes=6)), symptom_start=iso(t0),
                        affected_services=sc["affected"], reporter="on-call")
        metrics = generate_metrics(sc, rng, t0)
        logs, key_logs = generate_logs(sc, rng, t0)

        deployments, key_ids = [], list(key_logs)
        for (svc, off, frm, to, changes, status, is_key) in sc.get("deployments", []):
            did = f"dep-{hid(sc['id'], svc, to)}"
            deployments.append(dict(deployment_id=did, service=svc, timestamp=iso(t0 + timedelta(minutes=off)),
                                    from_version=frm, to_version=to, status=status, changes=changes, deployed_by="ci-pipeline"))
            if is_key:
                key_ids.append(did)
        configs = []
        for (svc, off, key, old, new, is_key) in sc.get("configs", []):
            cid = f"cfg-{hid(sc['id'], svc, key)}"
            configs.append(dict(change_id=cid, service=svc, timestamp=iso(t0 + timedelta(minutes=off)), key=key,
                                old_value=old, new_value=new, author="config-bot", ticket=f"OPS-{rng.randint(2000, 2999)}"))
            if is_key:
                key_ids.append(cid)

        gt = dict(sc["gt"])
        decoys = [d["deployment_id"] for d in deployments if d["deployment_id"] not in key_ids] + \
                 [c["change_id"] for c in configs if c["change_id"] not in key_ids]
        ground_truth = dict(incident_id=sc["id"], root_cause_category=gt["category"], culprit_service=gt["service"],
                            description=gt["description"], expected_behaviour=gt["expected_behaviour"],
                            expected_inconclusive=gt.get("expected_inconclusive", False),
                            acceptable_inconclusive=gt.get("acceptable_inconclusive", False) or gt.get("expected_inconclusive", False),
                            key_evidence_ids=key_ids, key_metric_prefixes=gt["key_metric_prefixes"],
                            decoy_evidence_ids=decoys, decoy_category=gt["decoy_category"],
                            expected_remediation=gt["remediation"])

        (ROOT / "incidents" / f"{sc['id']}.json").write_text(json.dumps(incident, indent=2))
        (ROOT / "metrics" / f"{sc['id']}.json").write_text(json.dumps(metrics))
        with open(ROOT / "logs" / f"{sc['id']}.jsonl", "w") as fh:
            for rec in logs:
                fh.write(json.dumps(rec) + "\n")
        (ROOT / "deployments" / f"{sc['id']}.json").write_text(json.dumps(deployments, indent=2))
        (ROOT / "configurations" / f"{sc['id']}.json").write_text(json.dumps(configs, indent=2))
        (ROOT / "failures" / f"{sc['id']}.json").write_text(json.dumps(sc.get("failures", {}), indent=2))
        (ROOT / "ground_truth" / f"{sc['id']}.json").write_text(json.dumps(ground_truth, indent=2))
        print(f"{sc['id']}: {len(logs)} logs, {len(deployments)} deployments, {len(configs)} config changes")


if __name__ == "__main__":
    main()
