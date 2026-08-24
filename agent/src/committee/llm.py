"""One committee member's turn: a Claude call with that role's scoped MCP tools.

Each role runs against tools drawn from its own MCP session, so a role's capabilities are
bounded by its toolset rather than by its prompt. The Bear cannot place an order here
because `place_option_order` is not among the tools passed to the model at all.

Every turn returns a `Turn` carrying the final text AND the full tool-call trail. The trail
is not debug output — it is the evidence behind the decision, written to the decision log
and shown on the dashboard. "Cite the numbers you looked up" is enforceable only because we
keep the record of what was looked up.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from anthropic import AsyncAnthropic

from .mcp_client import ScopedSession
from .roles import MODEL, Role

# Opus 5 may decline a request outright (HTTP 200, stop_reason "refusal"). Server-side
# fallback routes those by category instead of failing the cycle. A trading agent that
# stops mid-session because one prompt tripped a classifier is worse than one that
# completes on a fallback model and says so.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


@dataclass
class ToolCall:
    tool: str
    arguments: dict[str, Any]
    result: str

    def short(self, limit: int = 220) -> str:
        body = self.result if len(self.result) <= limit else self.result[:limit] + "…"
        return f"{self.tool}({json.dumps(self.arguments)[:120]}) -> {body}"


@dataclass
class Turn:
    role: str
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str | None = None
    refused: bool = False
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def evidence(self) -> list[str]:
        return [c.short() for c in self.tool_calls]


async def run_turn(
    client: AsyncAnthropic,
    role: Role,
    session: ScopedSession,
    schemas: dict[str, dict],
    prompt: str,
    *,
    max_iterations: int = 8,
) -> Turn:
    """Run one role to completion, executing its tool calls against its scoped session.

    `max_iterations` bounds the loop. A role that has not finished after that many rounds is
    looping rather than working, and we would rather return a partial answer the committee
    can see than hang a trading cycle.
    """
    tools = session.anthropic_tools(schemas)
    messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
    turn = Turn(role=role.name, text="")

    for _ in range(max_iterations):
        response = await client.beta.messages.create(
            model=MODEL,
            max_tokens=role.max_tokens,
            system=role.system,
            messages=messages,
            tools=tools,
            thinking={"type": "adaptive"},
            output_config={"effort": role.effort},
            betas=[FALLBACK_BETA],
            fallbacks="default",
        )

        turn.stop_reason = response.stop_reason
        turn.input_tokens += response.usage.input_tokens
        turn.output_tokens += response.usage.output_tokens

        if response.stop_reason == "refusal":
            turn.refused = True
            detail = getattr(response, "stop_details", None)
            turn.text = f"[refused: {getattr(detail, 'category', 'unknown')}]"
            return turn

        text_parts = [b.text for b in response.content if b.type == "text"]
        if text_parts:
            turn.text = "\n".join(text_parts).strip()

        if response.stop_reason != "tool_use":
            return turn

        # Execute every requested tool, then return ALL results in a single user message —
        # splitting them across messages teaches the model to stop calling tools in parallel.
        messages.append({"role": "assistant", "content": response.content})
        results: list[dict[str, Any]] = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            args = block.input if isinstance(block.input, dict) else json.loads(block.input)
            try:
                output = await session.call(block.name, args)
                is_error = output.startswith("ERROR:")
            except PermissionError as exc:
                # Structurally impossible for a scoped role, but recorded rather than
                # swallowed: if this ever fires, the least-privilege model has a hole.
                output, is_error = f"DENIED: {exc}", True
            except Exception as exc:  # noqa: BLE001
                output, is_error = f"ERROR: {type(exc).__name__}: {exc}", True

            turn.tool_calls.append(ToolCall(block.name, args, output))
            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": output[:20_000],
                    "is_error": is_error,
                }
            )
        messages.append({"role": "user", "content": results})

    turn.text = turn.text or "[no conclusion reached within the iteration budget]"
    return turn
