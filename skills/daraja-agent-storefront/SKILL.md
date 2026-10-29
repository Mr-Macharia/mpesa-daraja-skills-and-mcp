---
name: daraja-agent-storefront
description: Recipe for an AI agent that sells and takes M-Pesa payments for a store, either inside a developer-built store with its own backend or as an agent-only seller in a chat. Covers working out which kind of store it is, the order-to-STK-to-confirmed flow, using the order ID as the account reference, tracking orders with forwarding or a CSV sales log, safe retries after failed payments, receipts, and refunds behind approval. Use when an agent handles selling, checkout or order payments for a shop over chat, WhatsApp, a website assistant or similar.
---

# Recipe: an agent that sells

The agent takes the order, asks for payment with an STK Push, and only hands over the goods once M-Pesa confirms. It needs the `mpesa-daraja` MCP server connected (`mpesa_*` tools).

## First: which kind of store?

Look before asking:

| Sign | Kind |
|---|---|
| A codebase with orders/products, an API the agent can call | **developer-built store**: the store's backend owns orders; the agent drives checkout |
| No codebase; a product list in chat, a spreadsheet or a file | **agent-only seller**: the agent keeps the record itself |

If it's still unclear, ask one question: *"Do you have a shop system I should record orders in, or should I keep a sales log? (default: sales log)"*.

## Needs

| Need | Default |
|---|---|
| Products and prices | from the store API, or a list the owner gives once |
| Paybill or Till | from `mpesa_setup_status` |
| Where results go | developer-built: `DARAJA_FORWARD_URL` to the store's webhook; agent-only: `mpesa_get_result` |
| Receipt wording | "Paid KES <amount> for <items>. M-Pesa receipt <receipt>." |
| Refund approval | the owner approves every refund (`DARAJA_APPROVAL_THRESHOLD=0`) |

## The sale, step by step

1. **Take the order.** Confirm the items, the total in whole shillings and the customer's phone. Read the total back before charging.
2. **Create the order** before any money moves.
   - Developer-built: create it through the store's API.
   - Agent-only: `python scripts/sales_log.py add <order_id> <phone> <amount> "<items>"`.
   - Make the order ID short (12 characters max), e.g. `A1042`.
3. **Ask for payment.** Call `mpesa_stk_push_and_wait` with:
   - `account_reference = <order_id>`
   - `idempotency_key = <order_id>-<attempt>`
   - the amount and phone
   Tell the customer: *"Check your phone and enter your M-Pesa PIN."*
4. **Act only on the final status:**

| status | Do |
|---|---|
| `SUCCESS` (result code 0) | check the amount matches, mark paid (`sales_log.py set <id> paid <receipt>`), fulfil, send the receipt |
| `FAILED` 1032 | the customer cancelled: ask if they'd like another prompt |
| `FAILED` 1037 / 2001 | not answered / wrong PIN: offer **one** new prompt |
| `FAILED` other | explain with `mpesa_explain_code`; don't loop |
| `UNKNOWN` or `ACCEPTED` | say it's still processing; check `mpesa_get_result(<key>)` again shortly. **Do not send another prompt.** |

5. **Retrying.** A new prompt after `FAILED` uses a new key (`<order_id>-2`). Never re-send while the outcome is `ACCEPTED` or `UNKNOWN`. At most two prompts per order before handing over to the owner.
6. **Never say "paid"** until step 4 gives `SUCCESS` with a receipt.

## Refunds

Collecting needs no approval, because the customer enters their own PIN. Refunds move the business's money:
- Only for an order that is `paid`, quoting its receipt: `mpesa_b2c_payment(phone, amount, remarks, idempotency_key="refund-<order_id>", refund_of=<receipt>)`.
- The owner approves it (the server asks in the chat). Record it with `sales_log.py set <id> refunded` once its result is `SUCCESS`.

## Keeping track

- Developer-built: the store's webhook receives each callback, signed (forwarding). The store is the source of truth, and the agent reads order state from it.
- Agent-only: `python scripts/sales_log.py open` lists orders that aren't final. Check each with `mpesa_get_result` before closing the day. The MCP server is not an order database: the log is.

## Done when

- [ ] A sandbox sale goes order → prompt → `SUCCESS` → receipt, and the log shows `paid` with the receipt
- [ ] A cancelled prompt leads to one offer of a new prompt, with a new key
- [ ] A slow payment (`UNKNOWN`) is never prompted twice
- [ ] A refund needs the owner's yes and quotes the original receipt

Related: `daraja-checkout` (for building the store's own checkout), `daraja-stk-push`, `daraja-b2c`, `daraja-payment-design`.
