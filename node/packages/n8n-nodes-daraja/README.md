# n8n-nodes-daraja

n8n community nodes for Safaricom M-Pesa Daraja, built on the [`mpesa-daraja`](https://www.npmjs.com/package/mpesa-daraja) Node library.

- **M-Pesa Daraja**: STK Push, STK Push and Wait, STK Query, Get Result, B2C, B2B (Paybill, Till, KRA tax), Transaction Status, Account Balance, Reverse Transaction.
- **M-Pesa Trigger**: starts a workflow when Daraja posts a callback, and replies to Daraja straight away.

Install in n8n: **Settings → Community Nodes → Install** → `n8n-nodes-daraja`.

## Setup

1. Add an **M-Pesa Daraja API** credential: environment, consumer key and secret, shortcode, passkey (STK), and initiator name and security credential (payouts, status, balance, reversal). **Test** fetches a token to check the key and secret.
2. Add an **M-Pesa Trigger** to a workflow and activate it. Copy its **Production URL**.
3. In each **M-Pesa Daraja** node, paste that URL into **Callback URL**. It must be public HTTPS.

## Rules that come with it

- **ACCEPTED is not paid.** STK Push returns `ACCEPTED`. Only the trigger's `SUCCESS`, STK Query or Transaction Status confirm a payment. STK Push and Wait waits for the final result.
- **Idempotency.** Give each charge or payout an **Idempotency Key**, such as the order ID. Running the node again with the same key returns the stored request instead of charging or paying twice. If a payout's outcome is `UNKNOWN`, check it with Get Result or Transaction Status before you decide anything.
- **Guardrails** on the credential: production is refused until **Allow Live Money Movement** is on; **Read Only**; **Allowed Recipients**; and an **Approval Threshold**. Payouts above it need **Approved** set to true, for example from a Wait or approval step. Never let an AI agent set it.
- A trigger result with status `UNKNOWN` came from a queue timeout.

## Limits

Sent requests and callback results live in the workflow's static data. n8n saves it only for executions of an active workflow, so manual test runs start empty. Two executions finishing at the same moment can overwrite each other's record. For high-volume production payouts, use the Node library with a database-backed store.

## Development

```bash
cd node && npm install && npm run build && npm test
```
