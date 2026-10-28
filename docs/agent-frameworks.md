# Use the tools from an agent framework

`mpesa_mcp.agent` gives you the MCP server's tools as plain Python tools, with no server process. You get the same validation and the same guardrails: read-only mode, the production lock, the approval threshold, the recipient allowlist and idempotency keys. Configuration comes from the same place as the server (`mpesa init`, or `DARAJA_*` variables).

```bash
pip install "mpesa-daraja-mcp[langchain]"       # or [openai-agents]
```

## Any framework

```python
from mpesa_mcp.agent import INSTRUCTIONS, mpesa_tools

tools = mpesa_tools(toolsets={"stk"})        # or include={"stk_push_and_wait", "get_result"}
for t in tools.values():
    print(t.name, t.parameters)              # name, description, JSON schema

out = await tools["stk_push_and_wait"].call(phone="2547XXXXXXXX", amount=10, account_reference="order-1")
out["status"]                                # SUCCESS, FAILED, UNKNOWN or ACCEPTED
```

Each tool's `call()` returns a dict that can be turned into JSON. Errors come back as `{"error": "..."}` instead of being raised, so the agent can read them. `call_sync()` is the same thing for code that isn't async. Put `INSTRUCTIONS` in the system prompt. It tells the model that `ACCEPTED` doesn't mean paid, and that it must not retry an unknown payout.

## LangChain and LangGraph

```python
from mpesa_mcp.integrations.langchain import mpesa_langchain_tools

tools = mpesa_langchain_tools(toolsets={"stk"})
```

## OpenAI Agents SDK

```python
from agents import Agent
from mpesa_mcp.agent import INSTRUCTIONS
from mpesa_mcp.integrations.openai_agents import mpesa_openai_tools

agent = Agent(name="cashier", instructions=INSTRUCTIONS, tools=mpesa_openai_tools(toolsets={"stk"}))
```

## Vercel AI SDK (Node)

The Node library [`mpesa-daraja`](../node/packages/mpesa-daraja) has the same tools, by the same names, for TypeScript agents. It has no MCP server and no Python. Payouts take an `approve` callback in the client options.

```ts
import { generateText } from "ai";
import { Daraja } from "mpesa-daraja";
import { mpesaAiTools, INSTRUCTIONS } from "mpesa-daraja/ai";

const daraja = Daraja.fromEnv(process.env, { approve: async (summary) => askAHuman(summary) });
await generateText({ model, system: INSTRUCTIONS, tools: mpesaAiTools(daraja), prompt });
```

`mpesaTools(daraja)` returns the framework-neutral tools (a JSON schema and `execute`) for any other Node framework.

## Approving payouts

With MCP, a payout above `DARAJA_APPROVAL_THRESHOLD` asks for approval in the chat. Outside MCP, you pass `approve`. It receives a one-line summary and returns `True` to send, and it can be async (for example, to post to Slack and wait for a reply). If you don't pass `approve`, payouts above the threshold are refused and nothing is sent.

```python
tools = mpesa_tools(toolsets={"payouts"}, approve=lambda summary: input(f"{summary} [y/N] ") == "y")
```

Options for all three entry points: `toolsets`, `read_only`, `approve` and `include`. Give an agent only the tools its job needs. A sales agent rarely needs `payouts`.
