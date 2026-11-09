"""Operational tools."""
from __future__ import annotations

from datetime import datetime

from app.tools.base import BaseTool, ToolExecutor
from app.tools.configuration_tool import ConfigurationHistoryTool
from app.tools.dependency_tool import ServiceDependencyTool
from app.tools.deployment_tool import DeploymentHistoryTool
from app.tools.historical_incident_tool import HistoricalIncidentTool
from app.tools.log_tool import LogQueryTool
from app.tools.metrics_tool import MetricsQueryTool

ALL_TOOL_NAMES = ["query_logs", "query_metrics", "get_deployments", "get_config_changes",
                  "get_service_dependencies", "search_historical_incidents"]


def build_tools(reference_time: datetime | None = None) -> list[BaseTool]:
    return [LogQueryTool(), MetricsQueryTool(), DeploymentHistoryTool(), ConfigurationHistoryTool(),
            ServiceDependencyTool(reference_time), HistoricalIncidentTool()]


__all__ = ["ALL_TOOL_NAMES", "BaseTool", "ToolExecutor", "build_tools"]
