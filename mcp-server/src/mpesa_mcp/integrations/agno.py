"""M-Pesa tools for Agno.

    pip install "mpesa-daraja-mcp[agno]"

    from agno.agent import Agent
    from mpesa_mcp.agent import INSTRUCTIONS
    from mpesa_mcp.integrations.agno import mpesa_agno_tools
    agent = Agent(instructions=INSTRUCTIONS, tools=mpesa_agno_tools(toolsets={"stk"}))
"""

from __future__ import annotations

import json
from typing import Any

try:
    from agno.tools import Function
except ImportError as exc:  # pragma: no cover
    raise ImportError('Agno is not installed: pip install "mpesa-daraja-mcp[agno]"') from exc

from ..agent import AgentTool, mpesa_tools


def to_agno(tool: AgentTool) -> Function:
    async def invoke(**kwargs: Any) -> str:
        return json.dumps(await tool.call(**kwargs), default=str)

    # skip_entrypoint_processing keeps our schema instead of one inferred from **kwargs.
    return Function(name=f"mpesa_{tool.name}", description=tool.description, parameters=tool.parameters,
                    entrypoint=invoke, skip_entrypoint_processing=True)


def mpesa_agno_tools(**options: Any) -> list[Function]:
    """Options as mpesa_mcp.agent.mpesa_tools: toolsets, read_only, approve, include."""
    return [to_agno(t) for t in mpesa_tools(**options).values()]
