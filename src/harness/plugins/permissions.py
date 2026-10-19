"""Permissions plugin — intercepts tool calls for human-in-the-loop confirmation.

This is the first "framework true increment": LangGraph's interrupt() gives us
a native way to pause the graph, ask the user for permission, and resume —
something that's painful to implement correctly in a bare while True loop.

The plugin hooks into PRE_TOOL_CALL, checks a permission policy, and if the
tool requires confirmation, uses LangGraph's interrupt() to pause.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from harness.core.plugin import HookPoint, HookSpec, Plugin


class PermissionLevel(str, Enum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


DEFAULT_POLICY: dict[str, PermissionLevel] = {
    "read_file": PermissionLevel.ALLOW,
    "list_files": PermissionLevel.ALLOW,
    "write_file": PermissionLevel.ASK,
    "bash": PermissionLevel.ASK,
}


class PermissionsPlugin(Plugin):
    """HITL permission gate using LangGraph interrupt().

    Before each tool call, checks the policy. If ASK, raises an interrupt
    that pauses the graph until the user approves or denies.
    """

    def __init__(self, policy: dict[str, PermissionLevel] | None = None) -> None:
        self._policy = {**DEFAULT_POLICY, **(policy or {})}

    @property
    def name(self) -> str:
        return "permissions"

    @property
    def priority(self) -> int:
        return 90

    def hooks(self) -> list[HookSpec]:
        return [
            HookSpec(
                point=HookPoint.PRE_TOOL_CALL,
                fn=self._check_permission,
            ),
        ]

    async def _check_permission(self, state: dict[str, Any], tool_name: str, tool_input: dict) -> dict[str, Any] | None:
        level = self._policy.get(tool_name, PermissionLevel.ASK)

        if level == PermissionLevel.DENY:
            return {"blocked": True, "reason": f"Tool '{tool_name}' is denied by policy"}

        if level == PermissionLevel.ASK:
            from langgraph.types import interrupt
            decision = interrupt({
                "type": "permission_request",
                "tool": tool_name,
                "input": tool_input,
                "message": f"Allow tool '{tool_name}' with input {tool_input}?",
            })
            if not decision.get("approved"):
                return {"blocked": True, "reason": "User denied the tool call"}

        return None
