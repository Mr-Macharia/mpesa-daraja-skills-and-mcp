// Runs the built nodes (dist/) with a fake n8n context and a fake Daraja behind globalThis.fetch.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { beforeEach, test } from "node:test";

const require = createRequire(import.meta.url);
const { MpesaDaraja, MpesaDarajaTrigger, MpesaDarajaApi } = require("../dist/index.js");

const CREDS = { environment: "sandbox", consumerKey: "k", consumerSecret: "s", shortcode: "174379", passkey: "pk",
  initiatorName: "api", securityCredential: "cred", allowLiveMoneyMovement: false, readOnly: false,
  approvalThreshold: 0, allowedRecipients: "" };
const URL = "https://n8n.example.com/webhook/abc/mpesa";

let calls;
let routes;
beforeEach(() => {
  calls = [];
  routes = {
    "/oauth/v1/generate": () => ({ access_token: "t", expires_in: "3599" }),
    "/mpesa/stkpush/v1/processrequest": () => ({ ResponseCode: "0", MerchantRequestID: "m-1", CheckoutRequestID: "ws_CO_1" }),
    "/mpesa/b2c/v3/paymentrequest": (b) => ({ ResponseCode: "0", ConversationID: "AG_1", OriginatorConversationID: b.OriginatorConversationID }),
  };
  globalThis.fetch = async (url, init) => {
    const path = new globalThis.URL(url).pathname;
    const body = init.body ? JSON.parse(init.body) : undefined;
    calls.push({ path, body });
    return new Response(JSON.stringify(routes[path](body)), { status: 200 });
  };
});

function ctx({ params, creds = CREDS, staticData = {}, items = 1, body, query = {} }) {
  return {
    staticData,
    getCredentials: async () => creds,
    getWorkflowStaticData: () => staticData,
    getInputData: () => Array.from({ length: items }, () => ({ json: {} })),
    getNodeParameter: (name, _i, fallback) => (name in params ? params[name] : fallback),
    getNode: () => ({ name: "M-Pesa Daraja", type: "mpesaDaraja", typeVersion: 1, parameters: {} }),
    continueOnFail: () => params.continueOnFail === true,
    getBodyData: () => body,
    getQueryData: () => query,
  };
}

const run = (c) => new MpesaDaraja().execute.call(c);
const stk = { operation: "stkPush", phone: "0712345678", amount: 10, accountReference: "order-1", description: "Test",
  idempotencyKey: "order-1", callbackUrl: URL };
const b2c = { operation: "b2c", phone: "0712345678", amount: 500, remarks: "Refund", idempotencyKey: "r-1", callbackUrl: URL };

test("package metadata points n8n at the built files", () => {
  const pkg = require("../package.json");
  assert.ok(pkg.keywords.includes("n8n-community-node-package"));
  for (const f of [...pkg.n8n.nodes, ...pkg.n8n.credentials]) require(`../${f}`);
  assert.equal(new MpesaDarajaApi().name, new MpesaDaraja().description.credentials[0].name);
});

test("STK push returns ACCEPTED, not paid, and sends the callback URL", async () => {
  const [[item]] = await run(ctx({ params: stk }));
  assert.equal(item.json.status, "ACCEPTED");
  const sent = calls.find((c) => c.path.includes("stkpush")).body;
  assert.equal(sent.CallBackURL, URL);
  assert.equal(sent.PhoneNumber, "254712345678");
});

test("the same idempotency key never sends a second prompt across executions", async () => {
  const staticData = {};
  await run(ctx({ params: stk, staticData }));
  const [[again]] = await run(ctx({ params: stk, staticData }));
  assert.equal(again.json.duplicate, true);
  assert.equal(calls.filter((c) => c.path.includes("stkpush")).length, 1);
});

test("the trigger acknowledges, stores the result and outputs it; Get Result then sees SUCCESS", async () => {
  const staticData = {};
  await run(ctx({ params: stk, staticData }));
  const body = { Body: { stkCallback: { MerchantRequestID: "m-1", CheckoutRequestID: "ws_CO_1", ResultCode: 0,
    ResultDesc: "ok", CallbackMetadata: { Item: [{ Name: "Amount", Value: 10 }, { Name: "MpesaReceiptNumber", Value: "NLJ7RT61SV" }] } } } };
  const res = await new MpesaDarajaTrigger().webhook.call(ctx({ params: {}, staticData, body }));
  assert.deepEqual(res.webhookResponse, { ResultCode: 0, ResultDesc: "Accepted" });
  assert.equal(res.workflowData[0][0].json.status, "SUCCESS");
  const [[got]] = await run(ctx({ params: { operation: "getResult", id: "order-1" }, staticData }));
  assert.equal(got.json.status, "SUCCESS");
  assert.equal(got.json.receipt, "NLJ7RT61SV");
});

test("a queue-timeout callback is UNKNOWN; Only Successful skips it but still acknowledges", async () => {
  const body = { Result: { ResultType: 0, ResultCode: 1, ResultDesc: "x", OriginatorConversationID: "o", ConversationID: "AG_9", TransactionID: "T" } };
  const res = await new MpesaDarajaTrigger().webhook.call(ctx({ params: {}, body, query: { timeout: "1" } }));
  assert.equal(res.workflowData[0][0].json.status, "UNKNOWN");
  const skipped = await new MpesaDarajaTrigger().webhook.call(ctx({ params: { onlySuccess: true }, body }));
  assert.equal(skipped.workflowData, undefined);
  assert.deepEqual(skipped.webhookResponse, { ResultCode: 0, ResultDesc: "Accepted" });
});

test("a body that is not a Daraja callback starts nothing", async () => {
  const res = await new MpesaDarajaTrigger().webhook.call(ctx({ params: {}, body: { hello: "world" } }));
  assert.equal(res.workflowData, undefined);
});

test("B2C sends the trigger URL as ResultURL and a timeout URL", async () => {
  const [[item]] = await run(ctx({ params: b2c }));
  assert.equal(item.json.status, "ACCEPTED");
  const sent = calls.find((c) => c.path.includes("b2c")).body;
  assert.equal(sent.ResultURL, URL);
  assert.equal(sent.QueueTimeOutURL, `${URL}?timeout=1`);
  assert.equal(sent.Occassion, "");
});

test("above the threshold a payout needs Approved", async () => {
  const creds = { ...CREDS, approvalThreshold: 100 };
  await assert.rejects(run(ctx({ params: b2c, creds })), /not approved.*approval step/s);
  assert.equal(calls.some((c) => c.path.includes("b2c")), false);
  const [[item]] = await run(ctx({ params: { ...b2c, approved: true }, creds }));
  assert.equal(item.json.status, "ACCEPTED");
});

test("allowlist, read-only and the production lock refuse before anything is sent", async () => {
  await assert.rejects(run(ctx({ params: b2c, creds: { ...CREDS, allowedRecipients: "0799999999" } })), /ALLOWED_RECIPIENTS/);
  await assert.rejects(run(ctx({ params: stk, creds: { ...CREDS, readOnly: true } })), /read-only/);
  await assert.rejects(run(ctx({ params: stk, creds: { ...CREDS, environment: "production" } })), /real money/);
  assert.equal(calls.length, 0);
});

test("errors become items with Continue On Fail, and money errors say not to blindly retry", async () => {
  const [[item]] = await run(ctx({ params: { ...stk, callbackUrl: "http://insecure", continueOnFail: true } }));
  assert.match(item.json.error, /HTTPS/);
  assert.match(item.json.error, /same idempotency key/);
});
