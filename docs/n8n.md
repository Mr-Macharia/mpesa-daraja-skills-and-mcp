# Using the MCP server from n8n

n8n's AI Agent can call the M-Pesa tools through the **MCP Client Tool** node. The server must be reachable over HTTPS, so [self-host it](self-hosting.md) first.

> For plain workflows without an AI agent, install the community nodes [`n8n-nodes-daraja-mpesa`](../node/packages/n8n-nodes-daraja-mpesa) instead: STK Push, B2C, B2B, status and an M-Pesa Trigger for callbacks.

## Import the example

1. In n8n: **Workflows → Import from file** → [`examples/n8n/mpesa-agent.json`](../examples/n8n/mpesa-agent.json).
2. Open **M-Pesa MCP**:
   - **Endpoint**: `https://<your-domain>/mcp`
   - **Server transport**: HTTP Streamable
   - **Authentication**: Bearer, with a new credential holding your `DARAJA_MCP_TOKEN`
3. Open **Chat Model** and pick your model credential.
4. Open the chat and try: *"Check my M-Pesa setup"*, then *"Charge 0712345678 KES 1 for order 42"* in the sandbox.

Node fields change between n8n versions. If the import complains, add the MCP Client Tool node by hand with the settings above.

## Choose which tools the agent sees

- In the node, **Tools to include** → *Selected* limits the agent to what the workflow needs, e.g. `mpesa_stk_push_and_wait` and `mpesa_get_result` for checkout.
- On the server, `DARAJA_TOOLSETS=stk` does the same for every client.

## Approvals

n8n can't show MCP approval prompts. With the hosted defaults (`DARAJA_APPROVAL_THRESHOLD=0`), every **payout** is refused from n8n, with nothing sent. Collections such as STK Push work, because the customer approves with their PIN.

To allow payouts from n8n, set a threshold that covers what the workflow may pay without a human, plus `DARAJA_ALLOWED_RECIPIENTS`. Larger amounts stay refused. For a human step, add n8n's own approval (e.g. *Send and Wait for Response*) before the agent runs.
