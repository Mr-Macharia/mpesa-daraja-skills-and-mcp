import assert from "node:assert/strict";
import { test } from "node:test";

import { Daraja, DarajaError, mpesaTools } from "../src/index.ts";
import { mpesaAiTools } from "../src/ai.ts";

type Route = (body: any, headers: Headers) => [number, unknown];

/** A fake Daraja: routes by path, records every call. */
function fake(routes: Record<string, Route | Route[]>) {
  const calls: { path: string; body: any; headers: Headers }[] = [];
  const fetch = (async (input: string, init: RequestInit = {}) => {
    const url = new URL(input);
    const headers = new Headers(init.headers);
    const body = init.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ path: url.pathname, body, headers });
    let route = routes[url.pathname] ?? (url.pathname === "/oauth/v1/generate" ? () => [200, { access_token: "T1", expires_in: "3599" }] : undefined);
    if (Array.isArray(route)) route = route.shift();
    if (!route) return new Response("not found", { status: 404 });
    const [status, out] = route(body, headers);
    if (out instanceof Error) throw out;
    return new Response(JSON.stringify(out), { status });
  }) as typeof fetch;
  return { calls, fetch, of: (path: string) => calls.filter((c) => c.path === path) };
}

const STK_ACK = { MerchantRequestID: "m1", CheckoutRequestID: "ws_CO_1", ResponseCode: "0" };
const B2C_ACK = { ConversationID: "AG_1", OriginatorConversationID: "oc", ResponseCode: "0" };

function client(f: ReturnType<typeof fake>, extra = {}) {
  return new Daraja({
    consumerKey: "k", consumerSecret: "s", shortcode: "174379", passkey: "pk", initiatorName: "testapi",
    securityCredential: "CRED", callbackBaseUrl: "https://example.com/hooks/", fetch: f.fetch,
    timing: { pollMs: 5, queryAfterMs: 20, queryEveryMs: 20 }, ...extra,
  });
}

const stkCallback = (code = 0) => ({ Body: { stkCallback: { MerchantRequestID: "m1", CheckoutRequestID: "ws_CO_1",
  ResultCode: code, ResultDesc: "x", ...(code === 0 ? { CallbackMetadata: { Item: [{ Name: "MpesaReceiptNumber", Value: "NLJ7RT61SV" }] } } : {}) } } });

test("STK Push builds the payload and is ACCEPTED, not paid", async () => {
  const f = fake({ "/mpesa/stkpush/v1/processrequest": () => [200, STK_ACK] });
  const out = await client(f).stkPush({ phone: "0712345678", amount: 1, accountReference: "INVOICE-1234567890", description: "Order 1042 long description" });
  const sent = f.of("/mpesa/stkpush/v1/processrequest")[0];
  assert.equal(sent.body.PartyA, "254712345678");
  assert.equal(sent.body.PhoneNumber, "254712345678");
  assert.equal(sent.body.CallBackURL, "https://example.com/hooks/mpesa/stk/callback");
  assert.equal(sent.body.AccountReference.length, 12);
  assert.equal(sent.body.TransactionDesc.length, 13);
  assert.equal(sent.headers.get("Authorization"), "Bearer T1");
  assert.equal(out.status, "ACCEPTED");
  assert.equal(out.ids.checkout_request_id, "ws_CO_1");
  assert.match(out.message, /NOT yet completed/);
});

test("the same idempotency key never sends a second prompt", async () => {
  const f = fake({ "/mpesa/stkpush/v1/processrequest": () => [200, STK_ACK] });
  const d = client(f);
  await d.stkPush({ phone: "0712345678", amount: 1, accountReference: "ref", idempotencyKey: "order-1" });
  const again = await d.stkPush({ phone: "0712345678", amount: 1, accountReference: "ref", idempotencyKey: "order-1" });
  assert.equal(f.of("/mpesa/stkpush/v1/processrequest").length, 1);
  assert.equal(again.duplicate, true);
});

test("the token is cached, and a 401 refreshes it once", async () => {
  const f = fake({
    "/oauth/v1/generate": [() => [200, { access_token: "T1", expires_in: "3599" }], () => [200, { access_token: "T2", expires_in: "3599" }]],
    "/mpesa/stkpush/v1/processrequest": [() => [200, STK_ACK], () => [401, {}], () => [200, STK_ACK]],
  });
  const d = client(f);
  await d.stkPush({ phone: "0712345678", amount: 1, accountReference: "a" });
  await d.stkPush({ phone: "0712345678", amount: 1, accountReference: "b" });
  assert.equal(f.of("/oauth/v1/generate").length, 2);
  assert.equal(f.of("/mpesa/stkpush/v1/processrequest")[2].headers.get("Authorization"), "Bearer T2");
});

test("bad keys get a plain explanation", async () => {
  const f = fake({ "/oauth/v1/generate": () => [400, ""] });
  await assert.rejects(client(f).checkCredentials(), (e: DarajaError) => e.status === 400 && /rejected the Consumer Key/.test(e.message));
});

test("local validation stops a bad request before it is sent", async () => {
  const f = fake({});
  await assert.rejects(client(f, { callbackBaseUrl: "https://localhost/x" }).stkPush({ phone: "0712345678", amount: 1, accountReference: "a" }),
    /nothing was sent/);
  assert.equal(f.of("/mpesa/stkpush/v1/processrequest").length, 0);
});

test("a callback moves the request to SUCCESS with the receipt", async () => {
  const f = fake({ "/mpesa/stkpush/v1/processrequest": () => [200, STK_ACK] });
  const d = client(f);
  await d.stkPush({ phone: "0712345678", amount: 1, accountReference: "a", idempotencyKey: "order-7" });
  const { ack, status } = await d.handleCallback(stkCallback(0));
  assert.deepEqual(ack, { ResultCode: 0, ResultDesc: "Accepted" });
  assert.equal(status, "SUCCESS");
  const out = await d.getResult("order-7");
  assert.equal(out.status, "SUCCESS");
  assert.equal(out.receipt, "NLJ7RT61SV");
});

test("stkPushAndWait returns the final result from STK Query", async () => {
  const f = fake({
    "/mpesa/stkpush/v1/processrequest": () => [200, STK_ACK],
    "/mpesa/stkpushquery/v1/query": [() => [500, { errorCode: "500.001.1001", errorMessage: "The transaction is being processed" }],
      () => [200, { ResultCode: "1032", ResultDesc: "Request cancelled by user" }]],
  });
  const out = await client(f).stkPushAndWait({ phone: "0712345678", amount: 1, accountReference: "a" });
  assert.equal(out.status, "FAILED");
  assert.equal(out.result_code, "1032");
});

test("a network error marks the payout UNKNOWN, and the same key is not resent", async () => {
  const f = fake({ "/mpesa/b2c/v3/paymentrequest": [() => [0, new TypeError("fetch failed")], () => [200, B2C_ACK]] });
  const d = client(f);
  const args = { phone: "0712345678", amount: 100, remarks: "r", idempotencyKey: "pay-1" };
  await assert.rejects(d.b2cPayment(args), /outcome UNKNOWN/);
  const again = await d.b2cPayment(args);
  assert.equal(again.status, "UNKNOWN");
  assert.equal(again.duplicate, true);
  assert.equal(f.of("/mpesa/b2c/v3/paymentrequest").length, 1);
});

test("B2C keeps Daraja's spelling Occassion and uses a fresh OriginatorConversationID", async () => {
  const f = fake({ "/mpesa/b2c/v3/paymentrequest": () => [200, B2C_ACK] });
  const out = await client(f).b2cPayment({ phone: "0712345678", amount: 100, remarks: "r", idempotencyKey: "pay-2" });
  const body = f.of("/mpesa/b2c/v3/paymentrequest")[0].body;
  assert.ok("Occassion" in body && !("Occasion" in body));
  assert.equal(out.ids.originator_conversation_id, body.OriginatorConversationID);
});

test("B2B Buy Goods uses RecieverIdentifierType 2", async () => {
  const f = fake({ "/mpesa/b2b/v1/paymentrequest": () => [200, B2C_ACK] });
  await client(f).b2bPayment({ receiverShortcode: "600001", amount: 100, accountReference: "inv", command: "BusinessBuyGoods", idempotencyKey: "b-1" });
  assert.equal(f.of("/mpesa/b2b/v1/paymentrequest")[0].body.RecieverIdentifierType, "2");
});

test("production refuses money moves without the live-money switch", async () => {
  const f = fake({});
  await assert.rejects(client(f, { env: "production" }).stkPush({ phone: "0712345678", amount: 1, accountReference: "a" }),
    /DARAJA_ALLOW_LIVE_MONEY_MOVEMENT/);
  assert.equal(f.calls.length, 0);
});

test("payouts above the threshold ask approve, and a no sends nothing", async () => {
  const f = fake({ "/mpesa/b2c/v3/paymentrequest": () => [200, B2C_ACK] });
  const asked: string[] = [];
  const d = client(f, { approvalThreshold: 50, approve: async (s: string) => (asked.push(s), false) });
  await assert.rejects(d.b2cPayment({ phone: "0712345678", amount: 100, remarks: "r", idempotencyKey: "pay-3" }), /not approved/);
  assert.match(asked[0], /KES 100 to 254712345678/);
  assert.equal(f.calls.length, 0);
});

test("fromEnv reads the MCP server's variable names", () => {
  const d = Daraja.fromEnv({ DARAJA_CONSUMER_KEY: "k", DARAJA_CONSUMER_SECRET: "s", DARAJA_ENV: "Production" });
  assert.equal(d.env, "production");
  assert.throws(() => Daraja.fromEnv({ DARAJA_CONSUMER_KEY: "k", DARAJA_CONSUMER_SECRET: "s", DARAJA_APPROVAL_THRESHOLD: "1.5" }));
});

test("agent tools: errors are data, read-only hides money tools", async () => {
  const f = fake({});
  const d = client(f);
  const tools = mpesaTools(d);
  assert.equal(tools.length, 13);
  assert.ok(mpesaTools(d, { readOnly: true }).every((t) => !t.movesMoney));
  const phone = tools.find((t) => t.name === "normalize_phone")!;
  assert.deepEqual(await phone.execute({ phone: "0712345678" }), { input: "0712345678", msisdn: "254712345678" });
  assert.match((await phone.execute({ phone: "nope" })).error, /Invalid Kenyan mobile number/);
  assert.throws(() => mpesaTools(d, { include: ["nope"] }));
});

test("Vercel AI SDK tools are keyed mpesa_<name> and execute", async () => {
  const tools = mpesaAiTools(client(fake({})), { include: ["explain_code"] });
  assert.deepEqual(Object.keys(tools), ["mpesa_explain_code"]);
  const out = await tools.mpesa_explain_code.execute!({ code: "1032" }, { toolCallId: "1", messages: [] });
  assert.equal(out.meaning, "Request cancelled by user.");
});

test("securityCredential encrypts with the certificate's public key", async (t) => {
  const { execFileSync } = await import("node:child_process");
  const { mkdtempSync, readFileSync } = await import("node:fs");
  const { constants, privateDecrypt } = await import("node:crypto");
  const { securityCredential } = await import("../src/index.ts");
  const dir = mkdtempSync((await import("node:os")).tmpdir() + "/mpesa-cert-");
  try {
    execFileSync("openssl", ["req", "-x509", "-newkey", "rsa:2048", "-nodes", "-subj", "/CN=test", "-days", "1",
      "-keyout", `${dir}/key.pem`, "-out", `${dir}/cert.pem`], { stdio: "ignore" });
  } catch {
    t.skip("openssl not available");
    return;
  }
  const out = securityCredential("Safaricom999!*!", readFileSync(`${dir}/cert.pem`));
  const plain = privateDecrypt({ key: readFileSync(`${dir}/key.pem`), padding: constants.RSA_PKCS1_PADDING }, Buffer.from(out, "base64"));
  assert.equal(plain.toString(), "Safaricom999!*!");
});
