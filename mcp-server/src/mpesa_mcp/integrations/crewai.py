"""M-Pesa tools for CrewAI.

    pip install "mpesa-daraja-mcp[crewai]"

    from crewai import Agent
    from mpesa_mcp.agent import INSTRUCTIONS
    from mpesa_mcp.integrations.crewai import mpesa_crewai_tools
    agent = Agent(role="Cashier", goal="Collect payments", backstory=INSTRUCTIONS,
                  tools=mpesa_crewai_tools(toolsets={"stk"}))
"""

from __future__ import annotations

from typing import Any

try:
    from crewai.tools import BaseTool
except ImportError as exc:  # pragma: no cover
    raise ImportError('CrewAI is not installed: pip install "mpesa-daraja-mcp[crewai]"') from exc

from ..agent import AgentTool, mpesa_tools


class MpesaCrewAITool(BaseTool):
    tool: AgentTool

    def _run(self, **kwargs: Any) -> dict[str, Any]:
        return self.tool.call_sync(**kwargs)

    async def _arun(self, **kwargs: Any) -> dict[str, Any]:
        return await self.tool.call(**kwargs)


def to_crewai(tool: AgentTool) -> MpesaCrewAITool:
    return MpesaCrewAITool(name=f"mpesa_{tool.name}", description=tool.description,
                           args_schema=tool.args_model, tool=tool)


def mpesa_crewai_tools(**options: Any) -> list[MpesaCrewAITool]:
    """Options as mpesa_mcp.agent.mpesa_tools: toolsets, read_only, approve, include."""
    return [to_crewai(t) for t in mpesa_tools(**options).values()]
