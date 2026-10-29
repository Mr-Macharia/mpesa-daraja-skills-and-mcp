"""M-Pesa tools for any agent framework, without running an MCP server.

The same functions, validation and guardrails as the MCP server (read-only mode,
live-money lock, approval threshold, recipient allowlist, idempotency keys), as
plain tools with a name, a description, a JSON schema and an async call:

    from mpesa_mcp.agent import mpesa_tools

    tools = mpesa_tools(toolsets={"stk"}, approve=lambda summary: input(summary + " [y/N] ") == "y")
    result = await tools["stk_push_and_wait"].call(phone="2547XXXXXXXX", amount=10, account_reference="order-1")

Adapters: mpesa_mcp.integrations.langchain and mpesa_mcp.integrations.openai_agents.

Payouts above DARAJA_APPROVAL_THRESHOLD call `approve` with a summary; without it they are refused.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import inspect
from collections.abc import Awaitable, Callable, Iterator, Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError, create_model

from . import server

# Add to the agent's system prompt: how to read ACCEPTED and when not to retry.
INSTRUCTIONS = server.INSTRUCTIONS

Approver = Callable[[str], bool | Awaitable[bool]]


@dataclass(frozen=True)
class AgentTool:
    """One Daraja operation. call() returns a JSON-ready dict; errors come back as {"error": ...}."""

    name: str
    description: str
    args_model: type[BaseModel]
    moves_money: bool
    read_only: bool
    _fn: Callable[..., Any]
    _approve: Approver | None

    @property
    def parameters(self) -> dict[str, Any]:
        """JSON schema of the arguments."""
        return self.args_model.model_json_schema()

    async def call(self, **kwargs: Any) -> dict[str, Any]:
        try:
            args = self.args_model(**kwargs).model_dump(exclude_unset=True)
        except ValidationError as exc:
            return {"error": f"Invalid arguments: {exc.errors(include_url=False)}"}
        token = server.APPROVER.set(self._approve)
        try:
            result = self._fn(**args)
            if inspect.isawaitable(result):
                result = await result
        except server.EXPECTED_ERRORS as exc:
            return {"error": str(exc)}
        finally:
            server.APPROVER.reset(token)
        if isinstance(result, BaseModel):
            return result.model_dump(exclude_none=True)
        return result if isinstance(result, dict) else {"result": result}

    def call_sync(self, **kwargs: Any) -> dict[str, Any]:
        """call() for synchronous code; runs in a worker thread when an event loop is already running."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.call(**kwargs))
        with concurrent.futures.ThreadPoolExecutor(1) as pool:
            return pool.submit(asyncio.run, self.call(**kwargs)).result()


class MpesaTools(Mapping[str, AgentTool]):
    """The selected tools, keyed by name without the mpesa_ prefix."""

    def __init__(self, tools: list[AgentTool]):
        self._tools = {t.name: t for t in tools}

    def __getitem__(self, name: str) -> AgentTool:
        return self._tools[name.removeprefix("mpesa_")]

    def __iter__(self) -> Iterator[str]:
        return iter(self._tools)

    def __len__(self) -> int:
        return len(self._tools)


def _args_model(fn: Callable[..., Any]) -> type[BaseModel]:
    fields: dict[str, Any] = {}
    hints = inspect.get_annotations(fn, eval_str=True)
    for p in inspect.signature(fn).parameters.values():
        if p.name == "ctx":
            continue
        default = ... if p.default is inspect.Parameter.empty else p.default
        fields[p.name] = (hints.get(p.name, Any), default)
    return create_model(f"{fn.__name__}_args", __config__=ConfigDict(extra="forbid"), **fields)


def mpesa_tools(
    toolsets: set[str] | None = None,
    read_only: bool | None = None,
    approve: Approver | None = None,
    include: set[str] | None = None,
) -> MpesaTools:
    """Build the tools.

    toolsets: as DARAJA_TOOLSETS (core is always included); default all, or DARAJA_TOOLSETS.
    read_only: leave out tools that move money or write; default DARAJA_READ_ONLY.
    approve: asked for payouts above DARAJA_APPROVAL_THRESHOLD; return True to send.
    include: keep only these tool names (e.g. {"stk_push_and_wait", "get_result"}).
    """
    read_only = server.read_only_from_env() if read_only is None else read_only
    toolsets = server.toolsets_from_env() if toolsets is None else toolsets
    wanted = set(server.TOOLSETS) if toolsets is None else {"core", *toolsets}
    unknown = wanted - set(server.TOOLSETS)
    if unknown:
        raise ValueError(f"Unknown toolsets {sorted(unknown)}; choose from {', '.join(server.TOOLSETS)}")
    names = {n.removeprefix("mpesa_") for n in include} if include else None
    out = []
    for wrapped, hints, toolset in server._REGISTRY:
        fn = inspect.unwrap(wrapped)
        if toolset not in wanted or (read_only and not hints.read_only_hint):
            continue
        if names is not None and fn.__name__ not in names:
            continue
        out.append(AgentTool(
            name=fn.__name__,
            description=inspect.cleandoc(fn.__doc__ or fn.__name__),
            args_model=_args_model(fn),
            moves_money=bool(hints.destructive_hint) and not hints.read_only_hint,
            read_only=bool(hints.read_only_hint),
            _fn=fn,
            _approve=approve,
        ))
    if names is not None and (missing := names - {t.name for t in out}):
        raise ValueError(f"Unknown or filtered-out tools: {sorted(missing)}")
    return MpesaTools(out)
