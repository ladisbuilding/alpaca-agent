"""Scoped Alpaca MCP sessions.

Each committee role gets its own MCP server process, started with only the toolsets that
role is permitted to use. This is the enforcement point for the project's central safety
claim: the advocate agents cannot place an order because `place_option_order` is not in
their tool list at all — not because a system prompt asked them not to.

`scripts/discover_tools.py` asserts that property against the running server and fails
loudly if it ever stops holding.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# In the container the MCP server is on PATH (pip-installed); locally it lives in the venv.
# ALPACA_MCP_BIN lets the container override without a code change.
DEFAULT_SERVER = os.environ.get("ALPACA_MCP_BIN") or str(
    Path(__file__).resolve().parents[2] / ".venv" / "bin" / "alpaca-mcp-server"
)


@dataclass(frozen=True)
class McpCredentials:
    api_key: str
    secret_key: str
    paper: bool = True

    @staticmethod
    def from_dev_vars(path: Path) -> "McpCredentials":
        env: dict[str, str] = {}
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
        return McpCredentials(
            api_key=env["ALPACA_API_KEY_ID"],
            secret_key=env["ALPACA_API_SECRET_KEY"],
            paper=True,  # this project never carries a live key — see CLAUDE.md
        )


class ScopedSession:
    """An open MCP session restricted to one role's toolsets."""

    def __init__(self, session: ClientSession, toolsets: str, tool_names: list[str]) -> None:
        self._session = session
        self.toolsets = toolsets
        self.tool_names = tool_names

    def can(self, tool: str) -> bool:
        return tool in self.tool_names

    async def call(self, tool: str, arguments: dict[str, Any]) -> str:
        """Call a tool and flatten its result to text.

        Raises PermissionError when the tool is outside this role's scope. The MCP server
        would reject it anyway — this just fails earlier and with a clearer message than a
        protocol-level error.
        """
        if not self.can(tool):
            raise PermissionError(
                f"tool {tool!r} is not in this role's scope ({self.toolsets}). "
                f"Available: {', '.join(sorted(self.tool_names))}"
            )
        result = await self._session.call_tool(tool, arguments)
        parts: list[str] = []
        for block in result.content:
            text = getattr(block, "text", None)
            if text is not None:
                parts.append(text)
        body = "\n".join(parts)
        if getattr(result, "isError", False):
            return f"ERROR: {body}"
        return body

    def anthropic_tools(self, schemas: dict[str, dict]) -> list[dict]:
        """Tool definitions in Anthropic Messages API shape, for this role's scope only."""
        return [
            {
                "name": name,
                "description": schemas[name]["description"],
                "input_schema": schemas[name]["input_schema"],
            }
            for name in self.tool_names
            if name in schemas
        ]


@asynccontextmanager
async def scoped_session(
    toolsets: str,
    creds: McpCredentials,
    *,
    server: str = DEFAULT_SERVER,
) -> AsyncIterator[tuple[ScopedSession, dict[str, dict]]]:
    """Start an MCP server limited to `toolsets` and yield (session, tool schemas).

    `toolsets` is a comma-separated list from Alpaca's vocabulary:
    account, trading, watchlists, assets, stock-data, crypto-data, options-data,
    corporate-actions, news, fixed-income-data, locates.
    """
    env = {
        **os.environ,
        "ALPACA_API_KEY": creds.api_key,
        "ALPACA_SECRET_KEY": creds.secret_key,
        "ALPACA_PAPER_TRADE": "true" if creds.paper else "false",
        "ALPACA_TOOLSETS": toolsets,
    }
    params = StdioServerParameters(command=server, args=["--transport", "stdio"], env=env)

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            schemas = {
                t.name: {
                    "description": (t.description or "")[:1024],
                    "input_schema": t.inputSchema or {"type": "object", "properties": {}},
                }
                for t in listed.tools
            }
            yield ScopedSession(session, toolsets, list(schemas)), schemas
