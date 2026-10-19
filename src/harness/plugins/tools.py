"""Tools plugin — registers callable tools and contributes the tool node.

This is the most fundamental plugin: it provides the tools the LLM can invoke.
Built-in tools include read_file, write_file, edit_file, bash — the minimal
set a coding agent needs. Additional tools can be added by other plugins.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from harness.core.plugin import HookPoint, HookSpec, NodeSpec, Plugin, ToolSpec


class ToolsPlugin(Plugin):
    """Provides core file-system and shell tools for the coding agent."""

    def __init__(self, workspace: str | Path = ".") -> None:
        self._workspace = Path(workspace).resolve()

    @property
    def name(self) -> str:
        return "tools"

    @property
    def priority(self) -> int:
        return 100

    def tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="read_file",
                description="Read the contents of a file at the given path.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative path to the file"},
                    },
                    "required": ["path"],
                },
                handler=self._read_file,
            ),
            ToolSpec(
                name="write_file",
                description="Write content to a file, creating it if it doesn't exist.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative path to the file"},
                        "content": {"type": "string", "description": "Content to write"},
                    },
                    "required": ["path", "content"],
                },
                handler=self._write_file,
            ),
            ToolSpec(
                name="list_files",
                description="List files and directories at the given path.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative directory path", "default": "."},
                    },
                },
                handler=self._list_files,
            ),
            ToolSpec(
                name="bash",
                description="Execute a shell command in the workspace directory.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "Shell command to execute"},
                    },
                    "required": ["command"],
                },
                handler=self._bash,
            ),
        ]

    async def _read_file(self, path: str) -> str:
        full = self._workspace / path
        if not full.is_file():
            return f"Error: file not found: {path}"
        return full.read_text(encoding="utf-8")

    async def _write_file(self, path: str, content: str) -> str:
        full = self._workspace / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
        return f"Written {len(content)} bytes to {path}"

    async def _list_files(self, path: str = ".") -> str:
        full = self._workspace / path
        if not full.is_dir():
            return f"Error: not a directory: {path}"
        entries = sorted(e.name + ("/" if e.is_dir() else "") for e in full.iterdir())
        return "\n".join(entries) if entries else "(empty)"

    async def _bash(self, command: str) -> str:
        proc = await asyncio.create_subprocess_shell(
            command,
            cwd=str(self._workspace),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        output = stdout.decode("utf-8", errors="replace")
        if stderr:
            output += "\n[stderr]\n" + stderr.decode("utf-8", errors="replace")
        return output or "(no output)"
