/**
 * Daraja client with token caching, a 401 refresh-and-retry, local validation,
 * idempotency per key and payout guardrails. Ported from mpesa_mcp/server.py.
 */

import { randomUUID } from "node:crypto";

import { explainCode } from "./codes.ts";
import { type Approver, type Guardrails, GuardrailError, guardMoney, guardPayout } from "./guardrails.ts";
import {
  basicAuthHeader, correlationIds, normalizePhone, type Parsed, parseCallback, stkPassword, timestamp, validateAmount,
} from "./helpers.ts";
import { MemoryStore, OPEN_STATUSES, type RequestRecord, type Status, type Store } from "./store.ts";
import { type Api, validate } from "./validation.ts";

export const BASE_URLS = {
  sandbox: "https://sandbox.safaricom.co.ke",
  production: "https://api.safaricom.co.ke",
} as const;

// Refresh a minute before expiry so in-flight requests never carry a dead token.
const TOKEN_SAFETY_MARGIN_MS = 60_000;
// The PIN prompt lives ~60s; queries start after 20s because Daraja answers "still processing" before that.
const STK_WAIT_DEFAULT_S = 90;
const STK_WAIT_MAX_S = 300;

export interface DarajaOptions extends Partial<Guardrails> {
  consumerKey: string;
  consumerSecret: string;
  shortcode?: string;
  passkey?: string;
  initiatorName?: string;
  /** The initiator password encrypted with Safaricom's certificate; see securityCredential(). */
  securityCredential?: string;
  /** Public HTTPS base for callbacks, e.g. https://example.com/hooks. */
  callbackBaseUrl?: string;
  store?: Store;
  fetch?: typeof fetch;
  timeoutMs?: number;
  /** STK wait pacing in milliseconds; defaults suit real Daraja. */
  timing?: { pollMs?: number; queryAfterMs?: number; queryEveryMs?: number };
}

/** Daraja answered with an HTTP error: the request was rejected, not processed. */
export class DarajaError extends Error {
  override name = "DarajaError";
  readonly status: number;
  readonly body: unknown;
  constructor(status: number, body: unknown) {
    const b = (body && typeof body === "object" ? body : {}) as Record<string, any>;
    const code = b.errorCode as string | undefined;
    const msg = b.errorMessage ?? (typeof body === "string" ? body : "");
    super(`Daraja HTTP ${status}: ${[code, msg, code ? explainCode(code) : ""].filter(Boolean).join(" ")}`.trim());
    this.status = status;
    this.body = body;
  }
}

/** One result shape for every money-moving or asynchronous call. */
export interface Outcome {
  status: Status;
  /** Plain-language next step. ACCEPTED is never "paid". */
  message: string;
  idempotency_key?: string;
  duplicate: boolean;
  ids: Record<string, string>;
  receipt?: string;
  result_code?: string;
  explanation?: string;
  raw?: Record<string, any>;
}

export type TransactionType = "CustomerPayBillOnline" | "CustomerBuyGoodsOnline";

export interface StkPushArgs {
  phone: string;
  amount: number;
  accountReference: string;
  description?: string;
  transactionType?: TransactionType;
  /** The Till for Buy Goods; defaults to the shortcode. */
  partyB?: string;
  callbackUrl?: string;
  /** e.g. the order ID: repeating it never sends a second prompt. */
  idempotencyKey?: string;
}

export interface B2cArgs {
  phone: string;
  amount: number;
  remarks: string;
  idempotencyKey: string;
  command?: "BusinessPayment" | "SalaryPayment" | "PromotionPayment" | "BusinessPayToPochi";
  occasion?: string;
  partyA?: string;
  resultUrl?: string;
  timeoutUrl?: string;
  /** The original M-Pesa receipt when this is a refund. */
  refundOf?: string;
}

export interface B2bArgs {
  receiverShortcode: string;
  amount: number;
  accountReference: string;
  command?: "BusinessPayBill" | "BusinessBuyGoods" | "BusinessPayToBulk" | "PayTaxToKRA";
  /** Required except for PayTaxToKRA, where the PRN (accountReference) is the key. */
  idempotencyKey?: string;
  remarks?: string;
  requesterPhone?: string;
  partyA?: string;
  resultUrl?: string;
  timeoutUrl?: string;
}

const ID_FIELDS: Record<string, string> = {
  MerchantRequestID: "merchant_request_id",
  CheckoutRequestID: "checkout_request_id",
  ConversationID: "conversation_id",
  OriginatorConversationID: "originator_conversation_id",
  OriginatorCoversationID: "originator_conversation_id", // Daraja's C2B spelling
};

const VALIDATE_AS: Record<string, Api> = {
  "/mpesa/stkpush/v1/processrequest": "stk",
  "/mpesa/stkpushquery/v1/query": "stk_query",
  "/mpesa/c2b/v2/registerurl": "c2b_register",
  "/mpesa/c2b/v2/simulate": "c2b_simulate",
  "/mpesa/b2c/v3/paymentrequest": "b2c",
  "/mpesa/b2pochi/v1/paymentrequest": "b2pochi",
  "/mpesa/b2b/v1/paymentrequest": "b2b",
  "/mpesa/b2b/v1/remittax": "tax",
  "/mpesa/transactionstatus/v1/query": "status",
  "/mpesa/accountbalance/v1/query": "balance",
  "/mpesa/reversal/v1/request": "reversal",
};

function idsFrom(resp: unknown): Record<string, string> {
  if (!resp || typeof resp !== "object") return {};
  const r = resp as Record<string, any>;
  const ids: Record<string, string> = {};
  for (const [key, name] of Object.entries(ID_FIELDS)) if (r[key]) ids[name] = String(r[key]);
  return ids;
}

function ackStatus(resp: unknown): Status {
  if (!resp || typeof resp !== "object") return "FAILED";
  const r = resp as Record<string, any>;
  return String(r.ResponseCode ?? "") === "0" || String(r.code ?? "") === "0" ? "ACCEPTED" : "FAILED";
}

function message(status: Status, kind: string, ref: string): string {
  switch (status) {
    case "ACCEPTED":
      return `Accepted for processing only - NOT yet completed. Check getResult('${ref}'); if no callback arrives, ` +
        `use ${kind === "stk" ? "stkQuery" : "transactionStatus"}.`;
    case "SUCCESS":
      return "Completed successfully.";
    case "UNKNOWN":
      return `Outcome unknown (timeout). Do not resend: check getResult('${ref}') or transactionStatus first.`;
    default:
      return "Failed. Safe to retry with the same idempotency key once the cause is fixed.";
  }
}

function outcome(key: string | undefined, kind: string, status: Status, ids: Record<string, string>, raw: unknown,
  duplicate = false, parsed?: Parsed): Outcome {
  const ref = key ?? Object.values(ids)[0] ?? "";
  const code = parsed?.result_code;
  const out: Outcome = {
    status,
    message: (duplicate ? `Duplicate suppressed: this idempotency key was already sent (${status}). ` : "") +
      message(status, kind, ref),
    duplicate,
    ids,
    raw: raw && typeof raw === "object" ? (raw as Record<string, any>) : { response: raw },
  };
  if (key) out.idempotency_key = key;
  const receipt = parsed?.receipt ?? parsed?.transaction_id;
  if (receipt) out.receipt = String(receipt);
  if (code !== undefined && code !== null) out.result_code = String(code);
  if (parsed?.explanation) out.explanation = String(parsed.explanation);
  return out;
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export class Daraja {
  readonly env: "sandbox" | "production";
  readonly baseUrl: string;
  readonly store: Store;
  private readonly opts: DarajaOptions;
  private readonly guardrails: Guardrails;
  private readonly http: typeof fetch;
  private token?: string;
  private expiresAt = 0;
  private refreshing?: Promise<string>;

  constructor(options: DarajaOptions) {
    const env = options.env ?? "sandbox";
    if (!(env in BASE_URLS)) throw new Error(`env must be 'sandbox' or 'production', got '${env}'`);
    if (!options.consumerKey || !options.consumerSecret) throw new Error("consumerKey and consumerSecret are required");
    this.env = env;
    this.baseUrl = BASE_URLS[env];
    this.opts = { ...options, callbackBaseUrl: options.callbackBaseUrl?.replace(/\/+$/, "") };
    this.guardrails = { ...options, env };
    this.store = options.store ?? new MemoryStore();
    this.http = options.fetch ?? globalThis.fetch;
  }

  /** Build from DARAJA_* environment variables (the same names as the MCP server). */
  static fromEnv(env: Record<string, string | undefined> = process.env, overrides: Partial<DarajaOptions> = {}): Daraja {
    const get = (n: string) => env[n]?.trim() || undefined;
    const threshold = get("DARAJA_APPROVAL_THRESHOLD");
    if (threshold && !/^\d+$/.test(threshold)) {
      throw new Error(`DARAJA_APPROVAL_THRESHOLD must be whole shillings, got '${threshold}'`);
    }
    return new Daraja({
      env: (get("DARAJA_ENV")?.toLowerCase() ?? "sandbox") as "sandbox" | "production",
      consumerKey: get("DARAJA_CONSUMER_KEY") ?? "",
      consumerSecret: get("DARAJA_CONSUMER_SECRET") ?? "",
      shortcode: get("DARAJA_SHORTCODE"),
      passkey: get("DARAJA_PASSKEY"),
      initiatorName: get("DARAJA_INITIATOR_NAME"),
      securityCredential: get("DARAJA_SECURITY_CREDENTIAL"),
      callbackBaseUrl: get("DARAJA_CALLBACK_BASE_URL"),
      allowLiveMoneyMovement: get("DARAJA_ALLOW_LIVE_MONEY_MOVEMENT") === "true",
      readOnly: ["1", "true", "yes"].includes(get("DARAJA_READ_ONLY")?.toLowerCase() ?? ""),
      approvalThreshold: threshold ? Number(threshold) : undefined,
      allowedRecipients: get("DARAJA_ALLOWED_RECIPIENTS")?.split(","),
      ...overrides,
    });
  }

  // ---------------------------------------------------------------- HTTP

  private async request(url: string, init: RequestInit): Promise<{ status: number; body: any }> {
    const resp = await this.http(url, { ...init, signal: AbortSignal.timeout(this.opts.timeoutMs ?? 30_000) });
    const text = await resp.text();
    try {
      return { status: resp.status, body: JSON.parse(text) };
    } catch {
      return { status: resp.status, body: { errorMessage: text.slice(0, 500) } };
    }
  }

  /** A cached OAuth token, refreshed before expiry. Never log it. */
  async getToken(force = false): Promise<string> {
    if (!force && this.token && Date.now() < this.expiresAt - TOKEN_SAFETY_MARGIN_MS) return this.token;
    this.refreshing ??= (async () => {
      const { status, body } = await this.request(`${this.baseUrl}/oauth/v1/generate?grant_type=client_credentials`, {
        headers: { Authorization: basicAuthHeader(this.opts.consumerKey, this.opts.consumerSecret) },
      });
      if (status !== 200 || !body?.access_token) {
        // Daraja answers bad keys with an empty body; say what that almost always means.
        const hint = (status === 400 || status === 401) && !body?.errorCode
          ? { errorMessage: `Daraja rejected the Consumer Key/Secret for the ${this.env} environment. Check both values ` +
            "(no spaces) and that they come from an app in the same environment." }
          : body;
        throw new DarajaError(status, hint);
      }
      this.token = String(body.access_token);
      this.expiresAt = Date.now() + Number(body.expires_in ?? 3599) * 1000;
      return this.token;
    })().finally(() => { this.refreshing = undefined; });
    return this.refreshing;
  }

  /** POST to a Daraja path. Validates known request bodies first; retries once on 401 with a new token. */
  async post(path: string, payload: Record<string, any>): Promise<any> {
    const api = VALIDATE_AS[path];
    if (api) {
      const problems = validate(api, payload);
      if (problems.length) throw new Error("Request failed local validation (nothing was sent): " + problems.join("; "));
    }
    for (const attempt of [0, 1]) {
      const token = await this.getToken(attempt === 1);
      const { status, body } = await this.request(`${this.baseUrl}${path}`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (status === 401 && attempt === 0) continue;
      if (status >= 400) throw new DarajaError(status, body);
      return body;
    }
  }

  // ---------------------------------------------------------------- shared

  private require(...names: (keyof DarajaOptions)[]): void {
    const missing = names.filter((n) => !this.opts[n]);
    if (missing.length) {
      const env = missing.map((n) => "DARAJA_" + String(n).replace(/[A-Z]/g, (c) => "_" + c).toUpperCase());
      throw new Error(`Missing configuration: ${missing.join(", ")} (${env.join(", ")})`);
    }
  }

  private callback(explicit: string | undefined, path: string): string {
    const url = explicit ?? (this.opts.callbackBaseUrl ? this.opts.callbackBaseUrl + path : undefined);
    if (!url) throw new Error("Pass a callback URL or set callbackBaseUrl (DARAJA_CALLBACK_BASE_URL)");
    if (!url.startsWith("https://")) throw new Error(`Daraja callback URLs must be public HTTPS, got '${url}'`);
    return url;
  }

  private initiator(): [string, string] {
    this.require("initiatorName", "securityCredential");
    return [this.opts.initiatorName!, this.opts.securityCredential!];
  }

  private stkAuth() {
    this.require("shortcode", "passkey");
    const ts = timestamp();
    return { BusinessShortCode: this.opts.shortcode!, Password: stkPassword(this.opts.shortcode!, this.opts.passkey!, ts), Timestamp: ts };
  }

  private async recordOutcome(rec: RequestRecord, duplicate: boolean): Promise<Outcome> {
    const found = await this.store.latestResult([rec.key, ...rec.ids]);
    const { _ids, ...response } = rec.response;
    const ids = (_ids as Record<string, string>) ?? idsFrom(rec.response);
    return outcome(rec.key, rec.kind, rec.status, ids, found?.parsed ?? response, duplicate, found?.parsed);
  }

  /** Send at most once per idempotency key (FAILED requests may be re-sent). */
  private async sendOnce(kind: string, key: string, send: () => Promise<any>, extraIds: Record<string, string> = {}): Promise<Outcome> {
    const previous = await this.store.getRequest(key);
    if (previous && previous.status !== "FAILED") return this.recordOutcome(previous, true);
    let resp: any;
    try {
      resp = await send();
    } catch (exc) {
      if (exc instanceof DarajaError) {
        await this.store.saveRequest({ key, kind, status: "FAILED", response: { error: exc.body }, ids: Object.values(extraIds) });
        throw exc;
      }
      if (exc instanceof Error && exc.message.startsWith("Request failed local validation")) throw exc;
      // No answer: it may or may not have been processed.
      await this.store.saveRequest({ key, kind, status: "UNKNOWN", response: { error: String(exc) }, ids: Object.values(extraIds) });
      throw new Error(`Network error, outcome UNKNOWN for '${key}': check before retrying (${exc})`);
    }
    const ids = { ...idsFrom(resp), ...extraIds };
    const status = ackStatus(resp);
    await this.store.saveRequest({ key, kind, status, response: { ...resp, _ids: ids }, ids: Object.values(ids) });
    return outcome(key, kind, status, ids, resp);
  }

  // ---------------------------------------------------------------- auth, results

  /** Verify the consumer key and secret by fetching a token. Never returns the token. */
  async checkCredentials(): Promise<{ ok: true; environment: string; token_expires_in_s: number }> {
    await this.getToken(true);
    return { ok: true, environment: this.env, token_expires_in_s: Math.max(0, Math.floor((this.expiresAt - Date.now()) / 1000)) };
  }

  /**
   * Feed a callback body from your webhook route. Stores the result and moves the matching request
   * to SUCCESS or FAILED. Reply to Daraja with `ack` straight away. Pass timeout: true for QueueTimeOutURL posts.
   */
  async handleCallback(payload: Record<string, any>, options: { timeout?: boolean } = {}) {
    const parsed = parseCallback(payload);
    let status: Status = parsed.success ? "SUCCESS" : "FAILED";
    if (options.timeout) {
      status = "UNKNOWN"; // outcome not known: query before retrying
      parsed.note = "Queue timeout: outcome unknown - run transactionStatus before any retry.";
    }
    await this.store.addResult(correlationIds(parsed), status, parsed);
    return { status, parsed, ack: { ResultCode: 0, ResultDesc: "Accepted" } };
  }

  /** Final status of a request by idempotency key or any Daraja ID. Queries Daraja for open STK requests when refresh is true. */
  async getResult(id: string, refresh = true): Promise<Outcome> {
    let rec = await this.store.getRequest(id);
    if (rec) {
      if (rec.kind === "stk" && OPEN_STATUSES.includes(rec.status) && refresh && !(await this.store.latestResult([rec.key, ...rec.ids]))) {
        const checkout = (rec.response._ids ?? idsFrom(rec.response)).checkout_request_id;
        if (checkout) {
          await this.stkQueryOnce(checkout);
          rec = (await this.store.getRequest(id)) ?? rec;
        }
      }
      return this.recordOutcome(rec, false);
    }
    const found = await this.store.latestResult([id]);
    if (found) return outcome(undefined, found.parsed.kind, found.status, { id }, found.parsed, false, found.parsed);
    return { status: "UNKNOWN", duplicate: false, ids: { id },
      message: "No request or callback with this ID in this store. If it was sent elsewhere, use stkQuery or transactionStatus." };
  }

  // ---------------------------------------------------------------- STK Push

  private async stkQueryOnce(checkoutRequestId: string): Promise<[Parsed | undefined, any]> {
    let resp: any;
    try {
      resp = await this.post("/mpesa/stkpushquery/v1/query", { ...this.stkAuth(), CheckoutRequestID: checkoutRequestId });
    } catch (exc) {
      if (exc instanceof DarajaError && (exc.body as any)?.errorCode === "500.001.1001") return [undefined, exc.body]; // still processing
      throw exc;
    }
    if (!resp || typeof resp !== "object" || !("ResultCode" in resp)) return [undefined, resp];
    const code = String(resp.ResultCode);
    const parsed: Parsed = { kind: "stk", source: "stk_query", success: code === "0", result_code: code,
      result_desc: resp.ResultDesc ?? null, checkout_request_id: checkoutRequestId,
      merchant_request_id: resp.MerchantRequestID ?? null, explanation: explainCode(code) };
    await this.store.addResult(correlationIds(parsed), code === "0" ? "SUCCESS" : "FAILED", parsed);
    return [parsed, resp];
  }

  /** Send an STK Push PIN prompt. Returns ACCEPTED straight away; that is not paid. */
  async stkPush(a: StkPushArgs): Promise<Outcome> {
    guardMoney(this.guardrails);
    const msisdn = normalizePhone(a.phone);
    const key = a.idempotencyKey ?? `stk:${randomUUID()}`;
    const body = {
      ...this.stkAuth(),
      TransactionType: a.transactionType ?? "CustomerPayBillOnline",
      Amount: validateAmount(a.amount),
      PartyA: msisdn,
      PartyB: a.partyB ?? this.opts.shortcode,
      PhoneNumber: msisdn,
      CallBackURL: this.callback(a.callbackUrl, "/mpesa/stk/callback"),
      AccountReference: a.accountReference.slice(0, 12),
      TransactionDesc: (a.description ?? "Payment").slice(0, 13),
    };
    return this.sendOnce("stk", key, () => this.post("/mpesa/stkpush/v1/processrequest", body));
  }

  /** STK Push, then wait for SUCCESS / FAILED / UNKNOWN using callbacks (handleCallback) or STK Query. */
  async stkPushAndWait(a: Omit<StkPushArgs, "callbackUrl"> & { timeoutS?: number }): Promise<Outcome> {
    const sent = await this.stkPush(a);
    const checkout = sent.ids.checkout_request_id;
    if (sent.status !== "ACCEPTED" || !checkout) return sent;
    const t = { pollMs: 2000, queryAfterMs: 20_000, queryEveryMs: 15_000, ...this.opts.timing };
    const started = Date.now();
    const deadline = started + Math.min(Math.max(a.timeoutS ?? STK_WAIT_DEFAULT_S, 10), STK_WAIT_MAX_S) * 1000;
    let nextQuery = started + t.queryAfterMs;
    while (Date.now() < deadline) {
      if (await this.store.latestResult([checkout])) break;
      if (Date.now() >= nextQuery) {
        if ((await this.stkQueryOnce(checkout))[0]) break;
        nextQuery = Date.now() + t.queryEveryMs;
      }
      await sleep(t.pollMs);
    }
    let rec = await this.store.getRequest(sent.idempotency_key ?? checkout);
    if (rec && rec.status === "ACCEPTED" && !(await this.store.latestResult([checkout]))) {
      await this.store.saveRequest({ ...rec, status: "UNKNOWN" });
      rec = await this.store.getRequest(rec.key);
    }
    return rec ? this.recordOutcome(rec, sent.duplicate) : sent;
  }

  /** Final status of an STK Push. ACCEPTED means Safaricom is still processing it. */
  async stkQuery(checkoutRequestId: string): Promise<Outcome> {
    const ids = { checkout_request_id: checkoutRequestId };
    const known = await this.store.latestResult([checkoutRequestId]);
    if (known && (known.status === "SUCCESS" || known.status === "FAILED")) {
      return outcome(undefined, "stk", known.status, ids, known.parsed, false, known.parsed);
    }
    const [parsed, reply] = await this.stkQueryOnce(checkoutRequestId);
    if (parsed) return outcome(undefined, "stk", parsed.success ? "SUCCESS" : "FAILED", ids, parsed, false, parsed);
    return { status: "ACCEPTED", duplicate: false, ids, raw: reply && typeof reply === "object" ? reply : { response: reply },
      message: `Safaricom says: ${reply?.errorMessage ?? "not final yet"}. Ask again in about 15 seconds.` };
  }

  // ---------------------------------------------------------------- C2B

  /** Register C2B Confirmation and Validation URLs. In production this is effectively one-time. */
  async c2bRegisterUrls(a: { confirmationUrl: string; validationUrl: string; responseType?: "Completed" | "Cancelled"; shortcode?: string }) {
    for (const url of [a.confirmationUrl, a.validationUrl]) this.callback(url, "");
    return this.post("/mpesa/c2b/v2/registerurl", {
      ShortCode: a.shortcode ?? this.opts.shortcode, ResponseType: a.responseType ?? "Completed",
      ConfirmationURL: a.confirmationUrl, ValidationURL: a.validationUrl,
    });
  }

  /** Simulate a customer C2B payment. Sandbox only. */
  async c2bSimulate(a: { amount: number; phone?: string; billRef?: string; command?: TransactionType; shortcode?: string }) {
    if (this.env !== "sandbox") throw new GuardrailError("c2bSimulate only works in the sandbox");
    const command = a.command ?? "CustomerPayBillOnline";
    return this.post("/mpesa/c2b/v2/simulate", {
      ShortCode: a.shortcode ?? this.opts.shortcode, CommandID: command, Amount: validateAmount(a.amount),
      Msisdn: normalizePhone(a.phone ?? "254708374149"),
      BillRefNumber: command === "CustomerPayBillOnline" ? (a.billRef ?? "TEST") : null,
    });
  }

  // ---------------------------------------------------------------- payouts

  /** Pay a customer wallet (or Pochi la Biashara). Repeating idempotencyKey never pays twice. */
  async b2cPayment(a: B2cArgs): Promise<Outcome> {
    guardMoney(this.guardrails);
    if (!a.idempotencyKey) throw new Error("idempotencyKey is required for B2C (e.g. 'refund-order-1042')");
    const msisdn = normalizePhone(a.phone);
    const what = a.refundOf ? `Refund of ${a.refundOf}` : "Payout";
    await guardPayout(this.guardrails, this.store, a.idempotencyKey, a.amount, msisdn,
      `${what}: KES ${a.amount.toLocaleString("en-KE")} to ${msisdn}`);
    const [name, cred] = this.initiator();
    const command = a.command ?? "BusinessPayment";
    const path = command === "BusinessPayToPochi" ? "/mpesa/b2pochi/v1/paymentrequest" : "/mpesa/b2c/v3/paymentrequest";
    const ocid = randomUUID(); // fresh per attempt: Daraja rejects a reused ID even after a failure
    const body = {
      OriginatorConversationID: ocid,
      InitiatorName: name,
      SecurityCredential: cred,
      CommandID: command,
      Amount: validateAmount(a.amount, 10),
      PartyA: a.partyA ?? this.opts.shortcode,
      PartyB: msisdn,
      Remarks: (a.refundOf ? `Refund ${a.refundOf} ${a.remarks}` : a.remarks).slice(0, 100) || "Payment",
      QueueTimeOutURL: this.callback(a.timeoutUrl, "/mpesa/b2c/timeout"),
      ResultURL: this.callback(a.resultUrl, "/mpesa/b2c/result"),
      Occassion: (a.occasion ?? "").slice(0, 100), // Daraja's spelling
    };
    return this.sendOnce("b2c", a.idempotencyKey, () => this.post(path, body), { originator_conversation_id: ocid });
  }

  /** Pay a business: Paybill, Till, B2C utility top-up, or KRA tax (receiver 572572, accountReference = PRN). */
  async b2bPayment(a: B2bArgs): Promise<Outcome> {
    const command = a.command ?? "BusinessPayBill";
    let path = "/mpesa/b2b/v1/paymentrequest";
    let receiver = a.receiverShortcode;
    let key = a.idempotencyKey;
    if (command === "PayTaxToKRA") {
      [path, receiver] = ["/mpesa/b2b/v1/remittax", "572572"];
      key ??= `tax:${a.accountReference}`;
    } else if (!key) {
      throw new Error("idempotencyKey is required for B2B payments (e.g. 'supplier-inv-778')");
    }
    guardMoney(this.guardrails);
    await guardPayout(this.guardrails, this.store, key, a.amount, receiver,
      `Payment: KES ${a.amount.toLocaleString("en-KE")} to ${receiver} (${a.accountReference})`);
    const [name, cred] = this.initiator();
    const body: Record<string, any> = {
      Initiator: name,
      SecurityCredential: cred,
      CommandID: command,
      SenderIdentifierType: "4",
      RecieverIdentifierType: command === "BusinessBuyGoods" ? "2" : "4", // Daraja's spelling
      Amount: validateAmount(a.amount),
      PartyA: a.partyA ?? this.opts.shortcode,
      PartyB: receiver,
      AccountReference: a.accountReference,
      Remarks: (a.remarks ?? "Payment").slice(0, 100),
      QueueTimeOutURL: this.callback(a.timeoutUrl, "/mpesa/b2b/timeout"),
      ResultURL: this.callback(a.resultUrl, "/mpesa/b2b/result"),
    };
    if (a.requesterPhone) body.Requester = normalizePhone(a.requesterPhone);
    return this.sendOnce(command === "PayTaxToKRA" ? "tax" : "b2b", key, () => this.post(path, body));
  }

  // ---------------------------------------------------------------- ops

  private async queued(kind: string, path: string, body: Record<string, any>): Promise<Outcome> {
    const resp = await this.post(path, body);
    const key = `${kind}:${randomUUID()}`;
    const ids = idsFrom(resp);
    const status = ackStatus(resp);
    await this.store.saveRequest({ key, kind, status, response: resp, ids: Object.values(ids) });
    return outcome(key, kind, status, ids, resp);
  }

  /** Ask M-Pesa for the final state of a transaction. The answer arrives on the ResultURL. */
  async transactionStatus(a: { transactionId?: string; originalConversationId?: string; identifierType?: "1" | "2" | "4";
    partyA?: string; resultUrl?: string; timeoutUrl?: string }): Promise<Outcome> {
    if (!a.transactionId && !a.originalConversationId) throw new Error("Provide transactionId or originalConversationId");
    const [name, cred] = this.initiator();
    return this.queued("status", "/mpesa/transactionstatus/v1/query", {
      Initiator: name, SecurityCredential: cred, CommandID: "TransactionStatusQuery",
      TransactionID: a.transactionId ?? "", OriginalConversationID: a.originalConversationId ?? "",
      PartyA: a.partyA ?? this.opts.shortcode, IdentifierType: a.identifierType ?? "4",
      ResultURL: this.callback(a.resultUrl, "/mpesa/status/result"),
      QueueTimeOutURL: this.callback(a.timeoutUrl, "/mpesa/status/timeout"),
      Remarks: "Status check", Occasion: "",
    });
  }

  /** Request shortcode balances. Parsed balances arrive via handleCallback, then getResult. */
  async accountBalance(a: { partyA?: string; resultUrl?: string; timeoutUrl?: string } = {}): Promise<Outcome> {
    const [name, cred] = this.initiator();
    return this.queued("balance", "/mpesa/accountbalance/v1/query", {
      Initiator: name, SecurityCredential: cred, CommandID: "AccountBalance",
      PartyA: a.partyA ?? this.opts.shortcode, IdentifierType: "4", Remarks: "Balance check",
      ResultURL: this.callback(a.resultUrl, "/mpesa/balance/result"),
      QueueTimeOutURL: this.callback(a.timeoutUrl, "/mpesa/balance/timeout"),
    });
  }

  /** Reverse a whole C2B payment. One reversal per transactionId: repeats return the stored request. */
  async reverseTransaction(a: { transactionId: string; amount: number; remarks: string; receiverShortcode?: string;
    resultUrl?: string; timeoutUrl?: string }): Promise<Outcome> {
    guardMoney(this.guardrails);
    const key = `reversal:${a.transactionId}`;
    await guardPayout(this.guardrails, this.store, key, a.amount, null,
      `Reversal of ${a.transactionId}: KES ${a.amount.toLocaleString("en-KE")}`);
    const [name, cred] = this.initiator();
    const body = {
      Initiator: name, SecurityCredential: cred, CommandID: "TransactionReversal",
      TransactionID: a.transactionId, Amount: validateAmount(a.amount),
      ReceiverParty: a.receiverShortcode ?? this.opts.shortcode, RecieverIdentifierType: "11",
      ResultURL: this.callback(a.resultUrl, "/mpesa/reversal/result"),
      QueueTimeOutURL: this.callback(a.timeoutUrl, "/mpesa/reversal/timeout"),
      Remarks: a.remarks.slice(0, 100),
    };
    return this.sendOnce("reversal", key, () => this.post("/mpesa/reversal/v1/request", body));
  }
}

export type { Approver };
