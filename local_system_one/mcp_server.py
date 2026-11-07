"""Optional MCP v2 proxy for the persistent Local System One service."""

from __future__ import annotations

import os
from typing import Any

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from .client import LocalSystemOneClient
from .security import access_token_path

SERVICE_URL = os.environ.get("LOCAL_SYSTEM_ONE_URL", "http://127.0.0.1:8787")
AUTH_TOKEN = os.environ.get("LOCAL_SYSTEM_ONE_AUTH_TOKEN")
AUTH_FILE = os.environ.get("LOCAL_SYSTEM_ONE_AUTH_TOKEN_FILE") or (str(access_token_path()) if not AUTH_TOKEN else None)

client = LocalSystemOneClient(
    SERVICE_URL,
    auth_token=AUTH_TOKEN,
    auth_token_file=AUTH_FILE,
    timeout=10.0,
)

mcp = MCPServer(
    "Local System One",
    instructions=(
        "Local typed-decision tools for deciding whether to search, which model tier "
        "to use, whether an agent event should notify the user, and advisory-only "
        "completion and retry suggestions. The heavy model "
        "runtime lives in a separate persistent Local System One service."
    ),
)


def _call(method, *args, **kwargs):
    try:
        return method(*args, **kwargs)
    except RuntimeError as error:
        message = str(error)
        status = message.removeprefix("Local System One HTTP ")
        if (message.startswith("Local System One HTTP ") and status.isascii() and status.isdigit()
                and 100 <= int(status) <= 599):
            raise ToolError(message) from None
        if message in {"Local System One access token is unavailable", "Local System One is unreachable or timed out",
                       "Local System One response is too large"}:
            raise ToolError(message) from None
        raise ToolError("Local System One is unavailable") from None
    except Exception:
        raise ToolError("Local System One returned an invalid response") from None


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
    return _call(client.search_gate,
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
    return _call(client.model_tier_gate,
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
    return _call(client.notification_gate,
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
def completion_gate(
    task: str,
    current_result: str,
    execution_state: dict[str, Any],
    request_id: str | None = None,
) -> dict[str, Any]:
    """Suggest complete, continue, or verify; never stop an agent."""
    return _call(client.completion_gate, task, current_result, execution_state, request_id=request_id)


@mcp.tool()
def retry_escalation_gate(
    failure: dict[str, Any],
    operation: dict[str, Any],
    history: dict[str, Any],
    constraints: dict[str, Any],
    backend: str = "auto",
    request_id: str | None = None,
) -> dict[str, Any]:
    """Return a constrained advisory; never retry or execute an operation."""
    return _call(client.retry_escalation_gate, failure, operation, history, constraints, backend=backend, request_id=request_id)


@mcp.tool()
def system_one_health() -> dict[str, Any]:
    """Return the health state of the persistent Local System One service."""
    return _call(client.health)


def main() -> None:
    """Run the stdio MCP proxy."""
    mcp.run()


if __name__ == "__main__":
    main()
