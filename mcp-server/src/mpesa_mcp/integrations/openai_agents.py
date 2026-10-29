"""M-Pesa tools for the OpenAI Agents SDK.

    pip install "mpesa-daraja-mcp[openai-agents]"

    from agents import Agent
    from mpesa_mcp.agent import INSTRUCTIONS
    from mpesa_mcp.integrations.openai_agents import mpesa_openai_tools
    agent = Agent(name="cashier", instructions=INSTRUCTIONS, tools=mpesa_openai_tools(toolsets={"stk"}))
"""

from __future__ import annotations

import json
from typing import Any

try:
    from agents import FunctionTool
except ImportError as exc:  # pragma: no cover
    raise ImportError('The OpenAI Agents SDK is not installed: pip install "mpesa-daraja-mcp[openai-agents]"') from exc

from ..agent import AgentTool, mpesa_tools


def to_openai_agents(tool: AgentTool) -> FunctionTool:
    async def invoke(_ctx: Any, args_json: str) -> str:
        try:
            args = json.loads(args_json or "{}")
        except json.JSONDecodeError as exc:
            return json.dumps({"error": f"Arguments are not valid JSON: {exc}"})
        return json.dumps(await tool.call(**args), default=str)

    # Optional arguments with defaults don't fit strict mode, so the schema is sent as is.
    return FunctionTool(name=f"mpesa_{tool.name}", description=tool.description,
                        params_json_schema=tool.parameters, on_invoke_tool=invoke, strict_json_schema=False)


def mpesa_openai_tools(**options: Any) -> list[FunctionTool]:
    """Options as mpesa_mcp.agent.mpesa_tools: toolsets, read_only, approve, include."""
    return [to_openai_agents(t) for t in mpesa_tools(**options).values()]
