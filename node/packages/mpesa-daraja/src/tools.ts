/**
 * Daraja operations as agent tools: a name, a description, a JSON schema and execute().
 * Names and arguments match the MCP server's tools (without the mpesa_ prefix).
 * Errors come back as { error } so the model can read them; nothing is thrown.
 */

import type { Daraja } from "./client.ts";
import { explainCode } from "./codes.ts";
import { normalizePhone, parseCallback } from "./helpers.ts";

export const INSTRUCTIONS =
  "Tools for Safaricom M-Pesa Daraja. status=ACCEPTED only means Daraja accepted the request; never report it as " +
  "paid. Use stk_push_and_wait for checkout, or get_result(id) later. Money tools are idempotent per " +
  "idempotency_key: reuse the key when retrying, and never retry an ACCEPTED or UNKNOWN payout - check its result first.";

export interface JsonSchema {
  type: "object";
  properties: Record<string, Record<string, unknown>>;
  required?: string[];
  additionalProperties: false;
}

export interface AgentTool {
  name: string;
  description: string;
  parameters: JsonSchema;
  movesMoney: boolean;
  execute(args: Record<string, any>): Promise<Record<string, any>>;
}

const s = (description: string) => ({ type: "string", description });
const n = (description: string) => ({ type: "integer", minimum: 1, description });
const obj = (properties: JsonSchema["properties"], required: string[] = []): JsonSchema =>
  ({ type: "object", properties, required, additionalProperties: false });

const PHONE = s("Kenyan phone, any format (07…, +2547…, 2547…)");
const AMOUNT = n("Whole shillings");
const KEY = s("Stable ID for this payment, e.g. the order ID. Reuse it on retry; it never pays twice.");

type Def = [name: string, description: string, parameters: JsonSchema, movesMoney: boolean,
  run: (d: Daraja, a: Record<string, any>) => unknown];

const DEFS: Def[] = [
  ["explain_code", "Explain a Daraja errorCode (e.g. 400.002.02) or ResultCode (e.g. 1032, 2001).",
    obj({ code: s("The code") }, ["code"]), false, (_d, a) => ({ code: a.code, meaning: explainCode(a.code) })],
  ["normalize_phone", "Convert a Kenyan phone number into Daraja's 2547XXXXXXXX format.",
    obj({ phone: PHONE }, ["phone"]), false, (_d, a) => ({ input: a.phone, msisdn: normalizePhone(a.phone) })],
  ["parse_callback", "Parse any Daraja callback body into flat fields.",
    obj({ payload: { type: "object", description: "The callback JSON" } }, ["payload"]), false,
    (_d, a) => parseCallback(a.payload)],
  ["check_credentials", "Verify the consumer key and secret by fetching a token. Never returns the token.",
    obj({}), false, (d) => d.checkCredentials()],
  ["get_result", "Final status of a request by idempotency_key or any Daraja ID (CheckoutRequestID, ConversationID…).",
    obj({ id: s("idempotency_key or Daraja ID") }, ["id"]), false, (d, a) => d.getResult(a.id)],
  ["stk_query", "Final status of an STK Push. status=ACCEPTED means Safaricom is still processing it.",
    obj({ checkout_request_id: s("CheckoutRequestID") }, ["checkout_request_id"]), false,
    (d, a) => d.stkQuery(a.checkout_request_id)],
  ["transaction_status", "Ask M-Pesa for the final state of a transaction by receipt or OriginatorConversationID. " +
    "The answer arrives later; read it with get_result using the returned ID.",
    obj({ transaction_id: s("M-Pesa receipt"), original_conversation_id: s("OriginatorConversationID") }), false,
    (d, a) => d.transactionStatus({ transactionId: a.transaction_id, originalConversationId: a.original_conversation_id })],
  ["account_balance", "Request shortcode balances; read them later with get_result using the returned ID.",
    obj({}), false, (d) => d.accountBalance()],
  ["stk_push", "Send an M-Pesa Express (STK Push) PIN prompt and return immediately with status ACCEPTED (not paid). " +
    "Prefer stk_push_and_wait when the final result is needed.",
    obj({ phone: PHONE, amount: AMOUNT, account_reference: s("Order number, max 12 characters"),
      description: s("Shown on the prompt, max 13 characters"), idempotency_key: KEY }, ["phone", "amount", "account_reference"]),
    true, (d, a) => d.stkPush({ phone: a.phone, amount: a.amount, accountReference: a.account_reference,
      description: a.description, idempotencyKey: a.idempotency_key })],
  ["stk_push_and_wait", "Send an STK Push and wait for the final result (SUCCESS / FAILED / UNKNOWN) in one call.",
    obj({ phone: PHONE, amount: AMOUNT, account_reference: s("Order number, max 12 characters"),
      description: s("Shown on the prompt, max 13 characters"), idempotency_key: KEY,
      timeout_s: { type: "integer", minimum: 10, maximum: 300, description: "Seconds to wait (default 90)" } },
    ["phone", "amount", "account_reference"]),
    true, (d, a) => d.stkPushAndWait({ phone: a.phone, amount: a.amount, accountReference: a.account_reference,
      description: a.description, idempotencyKey: a.idempotency_key, timeoutS: a.timeout_s })],
  ["b2c_payment", "Pay a customer wallet. idempotency_key is required: repeating it never pays twice. " +
    "For a refund, pass refund_of = the original M-Pesa receipt.",
    obj({ phone: PHONE, amount: n("Whole shillings, at least 10"), remarks: s("Reason"), idempotency_key: KEY,
      refund_of: s("Original receipt, for refunds") }, ["phone", "amount", "remarks", "idempotency_key"]),
    true, (d, a) => d.b2cPayment({ phone: a.phone, amount: a.amount, remarks: a.remarks,
      idempotencyKey: a.idempotency_key, refundOf: a.refund_of })],
  ["b2b_payment", "Pay a business: BusinessPayBill (Paybill + account), BusinessBuyGoods (Till), BusinessPayToBulk " +
    "or PayTaxToKRA (account_reference = KRA PRN). idempotency_key is required except for PayTaxToKRA.",
    obj({ receiver_shortcode: s("Paybill or Till"), amount: AMOUNT, account_reference: s("Account or PRN"),
      command: { type: "string", enum: ["BusinessPayBill", "BusinessBuyGoods", "BusinessPayToBulk", "PayTaxToKRA"] },
      idempotency_key: KEY }, ["receiver_shortcode", "amount", "account_reference"]),
    true, (d, a) => d.b2bPayment({ receiverShortcode: a.receiver_shortcode, amount: a.amount,
      accountReference: a.account_reference, command: a.command, idempotencyKey: a.idempotency_key })],
  ["reverse_transaction", "Reverse a whole C2B payment received on your shortcode. Needs a human-approved reason.",
    obj({ transaction_id: s("Original M-Pesa receipt"), amount: AMOUNT, remarks: s("Reason") },
      ["transaction_id", "amount", "remarks"]),
    true, (d, a) => d.reverseTransaction({ transactionId: a.transaction_id, amount: a.amount, remarks: a.remarks })],
];

export interface ToolOptions {
  /** Leave out every tool that moves money. */
  readOnly?: boolean;
  /** Keep only these tool names. */
  include?: string[];
}

/** The tools for one client. Guardrails (approval, allowlist, live-money lock) come from the client's options. */
export function mpesaTools(daraja: Daraja, options: ToolOptions = {}): AgentTool[] {
  const include = options.include?.map((x) => x.replace(/^mpesa_/, ""));
  const unknown = include?.filter((x) => !DEFS.some(([name]) => name === x)) ?? [];
  if (unknown.length) throw new Error(`Unknown tools: ${unknown.join(", ")}`);
  return DEFS
    .filter(([name, , , moves]) => !(options.readOnly && moves) && (!include || include.includes(name)))
    .map(([name, description, parameters, movesMoney, run]) => ({
      name, description, parameters, movesMoney,
      async execute(args) {
        try {
          const out = await run(daraja, args ?? {});
          return out && typeof out === "object" ? (out as Record<string, any>) : { result: out };
        } catch (exc) {
          return { error: exc instanceof Error ? exc.message : String(exc) };
        }
      },
    }));
}
