"""M-Pesa tools for the Google Agent Development Kit (ADK).

    pip install "mpesa-daraja-mcp[google-adk]"

    from google.adk.agents import Agent
    from mpesa_mcp.agent import INSTRUCTIONS
    from mpesa_mcp.integrations.google_adk import mpesa_adk_tools
    agent = Agent(name="cashier", model="gemini-2.5-flash", instruction=INSTRUCTIONS,
                  tools=mpesa_adk_tools(toolsets={"stk"}))
"""

from __future__ import annotations

from typing import Any

try:
    from google.adk.tools import BaseTool, ToolContext
    from google.genai import types
except ImportError as exc:  # pragma: no cover
    raise ImportError('Google ADK is not installed: pip install "mpesa-daraja-mcp[google-adk]"') from exc

from ..agent import AgentTool, mpesa_tools


class MpesaAdkTool(BaseTool):
    def __init__(self, tool: AgentTool):
        super().__init__(name=f"mpesa_{tool.name}", description=tool.description)
        self.tool = tool

    def _get_declaration(self) -> types.FunctionDeclaration:
        return types.FunctionDeclaration(name=self.name, description=self.description,
                                         parameters_json_schema=self.tool.parameters)

    async def run_async(self, *, args: dict[str, Any], tool_context: ToolContext) -> dict[str, Any]:
        return await self.tool.call(**args)


def mpesa_adk_tools(**options: Any) -> list[MpesaAdkTool]:
    """Options as mpesa_mcp.agent.mpesa_tools: toolsets, read_only, approve, include."""
    return [MpesaAdkTool(t) for t in mpesa_tools(**options).values()]
