"""Optional MCP v2 proxy for the persistent Local System One service."""

from __future__ import annotations

import os
from typing import Any

from mcp.server import MCPServer

from .client import LocalSystemOneClient

SERVICE_URL = os.environ.get("LOCAL_SYSTEM_ONE_URL", "http://127.0.0.1:8787")
AUTH_TOKEN = os.environ.get("LOCAL_SYSTEM_ONE_AUTH_TOKEN")

client = LocalSystemOneClient(
    SERVICE_URL,
    auth_token=AUTH_TOKEN,
    timeout=10.0,
)

mcp = MCPServer(
    "Local System One",
    instructions=(
        "Local typed-decision tools for deciding whether to search, which model tier "
        "to use, and whether an agent event should notify the user. The heavy model "
        "runtime lives in a separate persistent Local System One service."
    ),
)


@mcp.tool()
def search_gate(
    task: str,
    context: Any = None,
    freshness: str = "auto",
    source_scope: str = "auto",
    external_lookup_required: bool = False,
    provided_context_sufficient: bool = False,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Decide whether an agent task should use external/current information."""
    return client.search_gate(
        task,
        context=context,
        freshness=freshness,
        source_scope=source_scope,
        external_lookup_required=external_lookup_required,
        provided_context_sufficient=provided_context_sufficient,
        request_id=request_id,
    )


@mcp.tool()
def model_tier_gate(
    task: str,
    context: Any = None,
    risk: str = "auto",
    task_type: str = "auto",
    irreversible: bool = False,
    requires_precision: bool = False,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Choose a fast or strong generative-model tier for the current task."""
    return client.model_tier_gate(
        task,
        context=context,
        risk=risk,
        task_type=task_type,
        irreversible=irreversible,
        requires_precision=requires_precision,
        request_id=request_id,
    )


@mcp.tool()
def notification_gate(
    event: str,
    context: Any = None,
    urgency: str = "auto",
    user_action_required: bool = False,
    blocking_failure: bool = False,
    routine_update: bool = False,
    deadline_minutes: int | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Choose silent, digest, or immediate notification for an agent event."""
    return client.notification_gate(
        event,
        context=context,
        urgency=urgency,
        user_action_required=user_action_required,
        blocking_failure=blocking_failure,
        routine_update=routine_update,
        deadline_minutes=deadline_minutes,
        request_id=request_id,
    )


@mcp.tool()
def system_one_health() -> dict[str, Any]:
    """Return the health state of the persistent Local System One service."""
    return client.health()


def main() -> None:
    """Run the stdio MCP proxy."""
    mcp.run()


if __name__ == "__main__":
    main()