"""MCP plugin — connects to Model Context Protocol servers and registers their tools.

MCP allows the agent to use external tools from MCP servers. This plugin:
  - Connects to configured MCP servers (stdio or SSE transport)
  - Discovers available tools from each server
  - Registers them as ToolSpec objects in the plugin registry
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from harness.core.plugin import Plugin, ToolSpec


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server connection."""
    name: str
    transport: str  # "stdio" or "sse"
    command: str | None = None  # For stdio transport
    args: list[str] = field(default_factory=list)
    url: str | None = None  # For SSE transport
    env: dict[str, str] = field(default_factory=dict)


class MCPPlugin(Plugin):
    """Connects to MCP servers and registers their tools."""

    def __init__(self) -> None:
        self._servers: dict[str, MCPServerConfig] = {}
        self._clients: dict[str, Any] = {}
        self._tools: list[ToolSpec] = []

    @property
    def name(self) -> str:
        return "mcp"

    @property
    def priority(self) -> int:
        return 50

    def tools(self) -> list[ToolSpec]:
        return self._tools

    async def add_server(self, config: MCPServerConfig) -> dict[str, Any]:
        """Add and connect to an MCP server."""
        try:
            if config.transport == "stdio":
                client = await self._connect_stdio(config)
            elif config.transport == "sse":
                client = await self._connect_sse(config)
            else:
                raise ValueError(f"Unknown transport: {config.transport}")

            self._servers[config.name] = config
            self._clients[config.name] = client

            # Discover tools from this server
            tools = await self._discover_tools(client, config.name)
            self._tools.extend(tools)

            return {
                "status": "connected",
                "server": config.name,
                "tools_discovered": len(tools),
            }
        except Exception as e:
            return {"status": "error", "server": config.name, "error": str(e)}

    async def remove_server(self, name: str) -> dict[str, Any]:
        """Disconnect and remove an MCP server."""
        if name not in self._servers:
            return {"status": "error", "error": f"Server not found: {name}"}

        try:
            client = self._clients.pop(name)
            if hasattr(client, "close"):
                await client.close()
            del self._servers[name]

            # Remove tools from this server
            self._tools = [t for t in self._tools if not t.name.startswith(f"{name}/")]

            return {"status": "disconnected", "server": name}
        except Exception as e:
            return {"status": "error", "server": name, "error": str(e)}

    def list_servers(self) -> list[dict[str, Any]]:
        """List configured MCP servers."""
        return [
            {
                "name": config.name,
                "transport": config.transport,
                "command": config.command,
                "url": config.url,
                "connected": config.name in self._clients,
            }
            for config in self._servers.values()
        ]

    async def _connect_stdio(self, config: MCPServerConfig) -> Any:
        """Connect to MCP server via stdio transport."""
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client

            server_params = StdioServerParameters(
                command=config.command,
                args=config.args,
                env=config.env if config.env else None,
            )

            # Create the connection
            read, write = await stdio_client(server_params).__aenter__()
            session = await ClientSession(read, write).__aenter__()
            await session.initialize()

            return session
        except ImportError:
            raise ImportError(
                "MCP support requires the 'mcp' package. "
                "Install with: pip install mcp"
            )

    async def _connect_sse(self, config: MCPServerConfig) -> Any:
        """Connect to MCP server via SSE transport."""
        try:
            from mcp import ClientSession
            from mcp.client.sse import sse_client

            # Create the connection
            read, write = await sse_client(config.url).__aenter__()
            session = await ClientSession(read, write).__aenter__()
            await session.initialize()

            return session
        except ImportError:
            raise ImportError(
                "MCP support requires the 'mcp' package. "
                "Install with: pip install mcp"
            )

    async def _discover_tools(self, client: Any, server_name: str) -> list[ToolSpec]:
        """Discover tools from an MCP server and convert them to ToolSpec."""
        tools = []

        try:
            # List tools from the MCP server
            result = await client.list_tools()

            for tool in result.tools:
                # Create a handler that calls the MCP tool
                handler = self._make_mcp_handler(client, tool.name)

                # Convert MCP tool schema to ToolSpec
                tool_spec = ToolSpec(
                    name=f"{server_name}/{tool.name}",
                    description=tool.description or f"MCP tool: {tool.name}",
                    input_schema=tool.inputSchema if hasattr(tool, "inputSchema") else {},
                    handler=handler,
                )
                tools.append(tool_spec)

        except Exception as e:
            print(f"Error discovering tools from {server_name}: {e}")

        return tools

    def _make_mcp_handler(self, client: Any, tool_name: str) -> Any:
        """Create an async handler for an MCP tool."""
        async def handler(**kwargs: Any) -> str:
            try:
                result = await client.call_tool(tool_name, kwargs)
                # MCP returns a list of content items
                if hasattr(result, "content"):
                    return "\n".join(
                        item.text if hasattr(item, "text") else str(item)
                        for item in result.content
                    )
                return str(result)
            except Exception as e:
                return f"MCP tool error: {e}"

        return handler
