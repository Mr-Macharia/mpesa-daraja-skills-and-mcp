"""M-Pesa tools as LangChain tools (also works with LangGraph).

    pip install "mpesa-daraja-mcp[langchain]"

    from mpesa_mcp.integrations.langchain import mpesa_langchain_tools
    tools = mpesa_langchain_tools(toolsets={"stk"})
"""

from __future__ import annotations

from typing import Any

try:
    from langchain_core.tools import StructuredTool
except ImportError as exc:  # pragma: no cover
    raise ImportError('LangChain is not installed: pip install "mpesa-daraja-mcp[langchain]"') from exc

from ..agent import AgentTool, mpesa_tools


def to_langchain(tool: AgentTool) -> StructuredTool:
    async def acall(**kwargs: Any) -> dict[str, Any]:
        return await tool.call(**kwargs)

    def call(**kwargs: Any) -> dict[str, Any]:
        return tool.call_sync(**kwargs)

    return StructuredTool.from_function(
        func=call, coroutine=acall, name=f"mpesa_{tool.name}",
        description=tool.description, args_schema=tool.args_model,
    )


def mpesa_langchain_tools(**options: Any) -> list[StructuredTool]:
    """Options as mpesa_mcp.agent.mpesa_tools: toolsets, read_only, approve, include."""
    return [to_langchain(t) for t in mpesa_tools(**options).values()]
