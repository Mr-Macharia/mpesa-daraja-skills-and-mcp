# mpesa-daraja (Node)

A Safaricom M-Pesa Daraja client for Node.js 20+ with no runtime dependencies. It covers STK Push, STK Query, C2B, B2C, B2B, KRA tax, Transaction Status, Account Balance, Reversal and callbacks. The safety rules from the [`mpesa-daraja-mcp` MCP server](https://pypi.org/project/mpesa-daraja-mcp/) come with it:

- **Local validation.** Requests Daraja would reject fail before they're sent, including Daraja's own spellings `RecieverIdentifierType` and `Occassion`.
- **Idempotency.** Each money request is sent at most once per key. A request whose outcome is unknown is never sent again automatically.
- **Guardrails.** A live-money lock in production, read-only mode, a recipient allowlist, and human approval above a threshold.
- **"Accepted" is not "paid".** Every money call returns an `Outcome` whose `status` is `ACCEPTED`, `SUCCESS`, `FAILED` or `UNKNOWN`.

The Python package and this one run the same [shared fixtures](https://github.com/Mr-Macharia/mpesa-daraja-skills-and-mcp/tree/main/shared/fixtures), so they follow the same rules.

```bash
npm install mpesa-daraja
```

## Quick start

```ts
import { Daraja } from "mpesa-daraja";

// Reads the DARAJA_* variables the MCP server uses (DARAJA_CONSUMER_KEY, DARAJA_PASSKEY, …).
const daraja = Daraja.fromEnv();

const out = await daraja.stkPushAndWait({
  phone: "0712345678",
  amount: 10,
  accountReference: "order-1042",
  idempotencyKey: "order-1042", // a retry with this key never sends a second prompt
});

if (out.status === "SUCCESS") console.log("Paid", out.receipt);
else console.log(out.status, out.message); // FAILED, or UNKNOWN: check before retrying
```

Or configure it in code:

```ts
const daraja = new Daraja({
  env: "sandbox",
  consumerKey: process.env.DARAJA_CONSUMER_KEY!,
  consumerSecret: process.env.DARAJA_CONSUMER_SECRET!,
  shortcode: "174379",
  passkey: process.env.DARAJA_PASSKEY,
  callbackBaseUrl: "https://example.com/hooks",
});
```

Never hardcode or log the consumer secret, passkey, initiator password or SecurityCredential.

## Callbacks

Daraja posts results to `callbackBaseUrl` + `/mpesa/stk/callback`, `/mpesa/b2c/result` and so on. Pass each body to `handleCallback` and reply with `ack` straight away:

```ts
app.post("/hooks/mpesa/:kind/:type", async (req, res) => {
  const { ack } = await daraja.handleCallback(req.body, { timeout: req.params.type === "timeout" });
  res.json(ack);
});

await daraja.getResult("order-1042"); // SUCCESS with the receipt, once the callback arrives
```

Put a secret token in the callback path. Daraja doesn't sign its callbacks.

## Payouts

```ts
const daraja = Daraja.fromEnv(process.env, {
  approvalThreshold: 1000,                      // or DARAJA_APPROVAL_THRESHOLD
  allowedRecipients: ["0712345678", "600001"],  // or DARAJA_ALLOWED_RECIPIENTS
  approve: async (summary) => askAHuman(summary), // true sends; without approve, larger payouts are refused
});

await daraja.b2cPayment({ phone: "0712345678", amount: 500, remarks: "Refund", idempotencyKey: "refund-1042", refundOf: "NLJ7RT61SV" });
await daraja.b2bPayment({ receiverShortcode: "600001", amount: 2000, accountReference: "INV-778", idempotencyKey: "supplier-inv-778" });
```

B2C and B2B need `initiatorName` and `securityCredential`. Use `securityCredential(password, certificate)` to encrypt the initiator password with Safaricom's certificate. If a payout fails with a network error, its outcome is `UNKNOWN`. Calling again with the same key returns the stored request instead of paying twice. Check `transactionStatus` before you decide anything.

In production, every charge and payout is refused unless you set `allowLiveMoneyMovement: true` (`DARAJA_ALLOW_LIVE_MONEY_MOVEMENT=true`).

## Storage

The default `MemoryStore` forgets everything when the process exits. That's fine for tests and scripts. In production, implement the four-method `Store` interface on your database, so a restart never forgets what was already sent:

```ts
const daraja = Daraja.fromEnv(process.env, { store: new PostgresStore(pool) });
```

## AI agents

`mpesaTools(daraja)` returns tools with the same names and arguments as the MCP server's (`stk_push_and_wait`, `get_result`, `b2c_payment`, …). Each has a JSON schema and an `execute` method that returns errors as `{ error }`. Add `INSTRUCTIONS` to the system prompt.

With the [Vercel AI SDK](https://ai-sdk.dev) (`ai` 5 or later):

```ts
import { generateText } from "ai";
import { mpesaAiTools, INSTRUCTIONS } from "mpesa-daraja/ai";

const { text } = await generateText({
  model,
  system: INSTRUCTIONS,
  tools: mpesaAiTools(daraja, { readOnly: false }),
  prompt: "Charge 0712345678 KES 10 for order 1042",
});
```

The guardrails apply to agent calls too. A payout above the threshold calls your `approve` function, never the model.

## Offline helpers

`normalizePhone`, `validateAmount`, `timestamp` (EAT), `stkPassword`, `validate(api, body)`, `parseCallback`, `explainCode`.

## Development

```bash
cd node && npm install
npm run build && npm test   # tests need Node 22.6+ (they run the TypeScript sources directly)
```
