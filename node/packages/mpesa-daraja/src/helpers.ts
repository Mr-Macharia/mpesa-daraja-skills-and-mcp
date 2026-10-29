/**
 * Pure, offline Daraja helpers: formatting, signing and payload parsing.
 * Same rules as mpesa_mcp/helpers.py; both pass shared/fixtures/.
 */

import { X509Certificate, constants, publicEncrypt } from "node:crypto";

import { explainCode } from "./codes.ts";

const PHONE_RE = /^(?:\+?254|0)?([17]\d{8})$/;

/** Return a phone number as 2547XXXXXXXX / 2541XXXXXXXX. Accepts 07…, 01…, 7…, +2547…, with spaces or dashes. */
export function normalizePhone(raw: string | number): string {
  const digits = String(raw).replace(/[\s\-()]/g, "");
  const match = PHONE_RE.exec(digits);
  if (!match) {
    throw new Error(`Invalid Kenyan mobile number ${JSON.stringify(String(raw))}; expected e.g. 0712345678 or 254712345678`);
  }
  return "254" + match[1];
}

/** YYYYMMDDHHmmss in EAT (UTC+3, no DST), as STK Push and Ratiba require. */
export function timestamp(now: Date = new Date()): string {
  const eat = new Date(now.getTime() + 3 * 3600_000);
  const p = (n: number) => String(n).padStart(2, "0");
  return (
    eat.getUTCFullYear() + p(eat.getUTCMonth() + 1) + p(eat.getUTCDate()) +
    p(eat.getUTCHours()) + p(eat.getUTCMinutes()) + p(eat.getUTCSeconds())
  );
}

/** base64(BusinessShortCode + Passkey + Timestamp). */
export function stkPassword(shortcode: string | number, passkey: string, ts: string): string {
  return Buffer.from(`${shortcode}${passkey}${ts}`).toString("base64");
}

export function basicAuthHeader(consumerKey: string, consumerSecret: string): string {
  return "Basic " + Buffer.from(`${consumerKey}:${consumerSecret}`).toString("base64");
}

/** Daraja only accepts whole shillings. */
export function validateAmount(amount: number | string, minimum = 1): number {
  const value = typeof amount === "number" ? amount : amount.trim() === "" ? NaN : Number(amount);
  if (!Number.isFinite(value)) throw new Error(`Amount is not numeric: ${JSON.stringify(amount)}`);
  if (!Number.isInteger(value)) throw new Error(`Amount must be a whole number of shillings, got ${amount}`);
  if (value < minimum) throw new Error(`Amount must be at least ${minimum}, got ${amount}`);
  return value;
}

/**
 * RSA PKCS#1 v1.5 encrypt the initiator password with Safaricom's certificate (PEM or DER).
 * Use SandboxCertificate.cer for sandbox and ProductionCertificate.cer for production.
 * The output differs on every call (random padding); that is expected.
 */
export function securityCredential(initiatorPassword: string, cert: string | Buffer): string {
  const key = new X509Certificate(cert).publicKey;
  return publicEncrypt({ key, padding: constants.RSA_PKCS1_PADDING }, Buffer.from(initiatorPassword)).toString("base64");
}

// ------------------------------------------------------------------ callbacks

export type Parsed = Record<string, unknown> & { kind: string; success: boolean };
type Json = Record<string, any>;

function lowerKeys(obj: unknown): Json {
  return Object.fromEntries(Object.entries((obj as Json) ?? {}).map(([k, v]) => [k.toLowerCase(), v]));
}

export function parseStkCallback(payload: Json): Parsed {
  const cb = payload.Body.stkCallback;
  const items: Json = {};
  for (const i of cb.CallbackMetadata?.Item ?? []) items[i.Name] = i.Value ?? null;
  const code = parseInt(String(cb.ResultCode), 10);
  return {
    kind: "stk",
    success: code === 0,
    result_code: code,
    result_desc: cb.ResultDesc ?? null,
    merchant_request_id: cb.MerchantRequestID ?? null,
    checkout_request_id: cb.CheckoutRequestID ?? null,
    amount: items.Amount ?? null,
    receipt: items.MpesaReceiptNumber ?? null,
    transaction_date: items.TransactionDate ?? null,
    phone: items.PhoneNumber ?? null,
    explanation: explainCode(code),
  };
}

/** B2C, B2B, Transaction Status, Reversal, Account Balance and tax `Result` callbacks. */
export function parseResultCallback(payload: Json): Parsed {
  const res = payload.Result;
  let params = res.ResultParameters?.ResultParameter ?? [];
  if (!Array.isArray(params)) params = [params]; // Daraja sends a bare object when there is one item
  const values: Json = {};
  for (const p of params) values[p.Key] = p.Value ?? null;
  const raw = res.ResultCode;
  // Reversal uses alphanumeric codes such as R000002.
  const code: number | string = /^\s*-?\d+\s*$/.test(String(raw)) ? parseInt(String(raw), 10) : String(raw);
  const out: Parsed = {
    kind: "result",
    success: code === 0,
    result_code: code,
    result_desc: res.ResultDesc ?? null,
    originator_conversation_id: res.OriginatorConversationID ?? null,
    conversation_id: res.ConversationID ?? null,
    transaction_id: res.TransactionID ?? null,
    parameters: values,
    explanation: explainCode(code),
  };
  if ("AccountBalance" in values) out.balances = parseAccountBalance(String(values.AccountBalance));
  return out;
}

export function parseC2bCallback(payload: Json): Parsed {
  return {
    kind: "c2b",
    success: true,
    transaction_id: payload.TransID ?? null,
    transaction_type: payload.TransactionType ?? null,
    amount: Number(payload.TransAmount || 0),
    shortcode: payload.BusinessShortCode ?? null,
    bill_ref: payload.BillRefNumber ?? null,
    msisdn: payload.MSISDN ?? null,
    time: payload.TransTime ?? null,
    first_name: payload.FirstName ?? null,
  };
}

export function parseRatibaCallback(payload: Json): Parsed {
  // Ratiba mixes key casing between docs and responses.
  const low = lowerKeys(payload);
  const header = lowerKeys(low.responseheader);
  const body = lowerKeys(low.responsebody);
  const data: Json = {};
  for (const i of body.responsedata ?? []) data[String(i.name ?? i.Name)] = i.value ?? i.Value ?? null;
  const code = String(header.responsecode ?? data.responseCode ?? "");
  return {
    kind: "ratiba",
    success: code === "0",
    result_code: code,
    result_desc: header.responsedescription ?? null,
    request_ref_id: header.requestrefid ?? null,
    response_ref_id: header.responserefid ?? null,
    transaction_id: data.TransactionID ?? null,
    parameters: data,
    explanation: explainCode(code),
  };
}

export function parseB2bExpressCallback(payload: Json): Parsed {
  const code = String(payload.resultCode ?? "");
  return {
    kind: "b2b_express",
    success: code === "0",
    result_code: code,
    result_desc: payload.resultDesc ?? null,
    request_id: payload.requestId ?? null,
    conversation_id: payload.conversationID ?? null,
    transaction_id: payload.transactionId ?? null,
    amount: payload.amount ?? null,
    explanation: explainCode(code),
  };
}

export function parseBillManagerPayment(payload: Json): Parsed {
  return {
    kind: "bill_manager_payment",
    success: true,
    transaction_id: payload.transactionId ?? null,
    amount: payload.paidAmount ?? null,
    account_reference: payload.accountReference ?? null,
    msisdn: payload.msisdn ?? null,
    shortcode: payload.shortCode ?? null,
    date: payload.dateCreated ?? null,
  };
}

/** Detect the callback type and flatten it. Throws for payloads that are not Daraja callbacks. */
export function parseCallback(payload: Json): Parsed {
  if (payload?.Body?.stkCallback) return parseStkCallback(payload);
  if (payload && "Result" in payload) return parseResultCallback(payload);
  if (payload && "TransID" in payload) return parseC2bCallback(payload);
  if (payload && Object.keys(payload).some((k) => k.toLowerCase() === "responseheader")) return parseRatibaCallback(payload);
  if (payload && "requestId" in payload && "resultCode" in payload) return parseB2bExpressCallback(payload);
  if (payload && "paidAmount" in payload) return parseBillManagerPayment(payload);
  throw new Error(
    "Unrecognised Daraja callback payload: expected Body.stkCallback, Result, TransID, " +
      "responseHeader (Ratiba), requestId (B2B Express) or paidAmount (Bill Manager)",
  );
}

const CORRELATION_FIELDS = [
  "checkout_request_id", "merchant_request_id", "originator_conversation_id", "conversation_id",
  "transaction_id", "request_id", "request_ref_id", "response_ref_id",
];

/** Every ID in a parsed callback that a stored request might be indexed under. */
export function correlationIds(parsed: Json): string[] {
  return CORRELATION_FIELDS.filter((f) => parsed[f]).map((f) => String(parsed[f]));
}

/** Parse 'Working Account|KES|700000.00|700000.00|0.00|0.00&Utility Account|…'. */
export function parseAccountBalance(raw: string): { account: string; currency: string; available: number; raw: string[] }[] {
  return raw
    .split("&")
    .filter(Boolean)
    .map((chunk) => chunk.split("|"))
    .filter((parts) => parts.length >= 3)
    .map((parts) => ({ account: parts[0], currency: parts[1], available: Number(parts[2]), raw: parts.slice(2) }));
}
