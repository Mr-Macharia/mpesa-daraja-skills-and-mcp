# Documentation

How the Safaricom Daraja API works: the transaction types, the request-and-callback cycle, OAuth and credentials, and the sandbox. It explains the *why* behind the rules the [skills](../skills) and [MCP server](../mcp-server) follow.

> These chapters are general background. Where they disagree with the [skills](../skills) or [AGENTS.md](../AGENTS.md), trust the skills: they are kept current and tested.

**Before you start:** REST APIs and JSON, HTTP methods, Base64, and a way to expose a local server over HTTPS (such as ngrok).

## Using this project

- [Agent setup](clients.md): skills folders, MCP config snippets, config files
- [Self-hosting](self-hosting.md): Docker, HTTPS, HTTP mode with a bearer token
- [n8n](n8n.md): use the tools from an n8n AI Agent
- [Forwarding](forwarding.md): send each callback on to your app, signed
- [Agent frameworks](agent-frameworks.md): the tools in LangChain, the OpenAI Agents SDK or your own agent
- [How it works](diagrams/how-it-works.svg): architecture diagram

## How Daraja works

1. [The M-Pesa ecosystem and transaction types](01-mpesa-ecosystem.md)
2. [Daraja's request-response cycle](02-request-response-cycle.md)
3. [Callback mechanisms](03-callbacks.md)
4. [Credentials and OAuth 2.0](04-credentials-and-oauth.md)
5. [Token lifecycle: expiry and refresh](05-token-lifecycle.md)
6. [Secure credential storage](06-secure-credential-storage.md)
7. [Sandbox setup and app creation](07-sandbox-setup.md)

## Key terms

| Term | Where |
|---|---|
| Daraja gateway, shortcodes, transaction types, STK Push | [1](01-mpesa-ecosystem.md) |
| Callback URLs | [2](02-request-response-cycle.md), [3](03-callbacks.md) |
| Consumer Key and Secret, OAuth 2.0, bearer token | [4](04-credentials-and-oauth.md) |
| Token expiry and refresh | [5](05-token-lifecycle.md) |
| `.env` files, secret managers | [6](06-secure-credential-storage.md) |
| Sandbox app, test credentials, ngrok, simulator | [7](07-sandbox-setup.md) |
