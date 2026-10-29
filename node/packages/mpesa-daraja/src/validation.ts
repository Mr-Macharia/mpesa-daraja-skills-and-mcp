/**
 * Daraja request-body rules. Same rules as mpesa_mcp/validation.py; both pass
 * shared/fixtures/validation.json.
 */

export type Api =
  | "stk" | "stk_query" | "c2b_register" | "c2b_simulate" | "b2c" | "b2pochi" | "b2b" | "tax"
  | "status" | "balance" | "reversal" | "qr" | "ratiba";

const PHONE = /^254[17]\d{8}$/;
const TIMESTAMP = /^\d{14}$/;
const SHORTCODE = /^\d{5,7}$/;
const C2B_FORBIDDEN = ["mpesa", "m-pesa", "safaricom", "exec", "cmd", "sql", "query"];

const INITIATED = ["Initiator", "SecurityCredential", "CommandID"];
const B2C = ["OriginatorConversationID", "InitiatorName", "SecurityCredential", "CommandID", "Amount",
  "PartyA", "PartyB", "Remarks", "QueueTimeOutURL", "ResultURL"];
const B2B = [...INITIATED, "SenderIdentifierType", "RecieverIdentifierType", "Amount", "PartyA", "PartyB",
  "AccountReference", "Remarks", "QueueTimeOutURL", "ResultURL"];

export const REQUIRED: Record<Api, string[]> = {
  stk: ["BusinessShortCode", "Password", "Timestamp", "TransactionType", "Amount", "PartyA", "PartyB",
    "PhoneNumber", "CallBackURL", "AccountReference", "TransactionDesc"],
  stk_query: ["BusinessShortCode", "Password", "Timestamp", "CheckoutRequestID"],
  c2b_register: ["ShortCode", "ResponseType", "ConfirmationURL", "ValidationURL"],
  c2b_simulate: ["ShortCode", "CommandID", "Amount", "Msisdn"],
  b2c: B2C,
  b2pochi: B2C,
  b2b: B2B,
  tax: B2B,
  status: [...INITIATED, "PartyA", "IdentifierType", "ResultURL", "QueueTimeOutURL", "Remarks"],
  balance: [...INITIATED, "PartyA", "IdentifierType", "Remarks", "QueueTimeOutURL", "ResultURL"],
  reversal: [...INITIATED, "TransactionID", "Amount", "ReceiverParty", "RecieverIdentifierType", "ResultURL",
    "QueueTimeOutURL", "Remarks"],
  qr: ["MerchantName", "RefNo", "Amount", "TrxCode", "CPI", "Size"],
  ratiba: ["StandingOrderName", "StartDate", "EndDate", "BusinessShortCode", "TransactionType",
    "ReceiverPartyIdentifierType", "Amount", "PartyA", "CallBackURL", "AccountReference", "TransactionDesc",
    "Frequency"],
};

const COMMANDS: Partial<Record<Api, [string, string[]]>> = {
  stk: ["TransactionType", ["CustomerPayBillOnline", "CustomerBuyGoodsOnline"]],
  c2b_simulate: ["CommandID", ["CustomerPayBillOnline", "CustomerBuyGoodsOnline"]],
  b2c: ["CommandID", ["BusinessPayment", "SalaryPayment", "PromotionPayment"]],
  b2pochi: ["CommandID", ["BusinessPayToPochi"]],
  b2b: ["CommandID", ["BusinessPayBill", "BusinessBuyGoods", "BusinessPayToBulk", "DisburseFundsToBusiness",
    "BusinessToBusinessTransfer", "MerchantToMerchantTransfer"]],
  tax: ["CommandID", ["PayTaxToKRA"]],
  status: ["CommandID", ["TransactionStatusQuery"]],
  balance: ["CommandID", ["AccountBalance"]],
  reversal: ["CommandID", ["TransactionReversal"]],
  qr: ["TrxCode", ["BG", "PB", "WA", "SM", "SB"]],
  ratiba: ["TransactionType", ["Standing Order Customer Pay Bill", "Standing Order Customer Pay Marchant"]],
};

// Common misspellings people "fix" that Daraja then rejects or ignores.
const SPELLING: Record<string, string> = {
  ReceiverIdentifierType: "RecieverIdentifierType",
  Occasion: "Occassion (B2C v3 / B2Pochi spelling)",
};

const URL_FIELDS = ["CallBackURL", "ConfirmationURL", "ValidationURL", "QueueTimeOutURL", "ResultURL"];

const PHONE_FIELDS: Partial<Record<Api, string[]>> = {
  stk: ["PartyA", "PhoneNumber"], c2b_simulate: ["Msisdn"], b2c: ["PartyB"], b2pochi: ["PartyB"], ratiba: ["PartyA"],
};

const show = (v: unknown) => (typeof v === "string" ? `'${v}'` : String(v));
const str = (v: unknown) => (v === undefined || v === null ? "" : String(v));

function strictBase64Decode(s: string): string {
  if (s.length % 4 !== 0 || !/^[A-Za-z0-9+/]*={0,2}$/.test(s)) throw new Error("not base64");
  return new TextDecoder("utf-8", { fatal: true }).decode(Buffer.from(s, "base64"));
}

/** Problems with a request body, or [] when Daraja should accept its shape. */
export function validate(api: string, body: Record<string, any>): string[] {
  const errors: string[] = [];
  if (!(api in REQUIRED)) return [`Unknown api '${api}'; choose one of: ${Object.keys(REQUIRED).join(", ")}`];
  const a = api as Api;
  const has = (f: string) => Object.hasOwn(body, f);

  for (const field of REQUIRED[a]) {
    if (body[field] === undefined || body[field] === null || body[field] === "") errors.push(`Missing required field ${field}`);
  }

  if (["b2b", "tax", "reversal", "b2c", "b2pochi"].includes(a)) {
    for (const [wrong, right] of Object.entries(SPELLING)) {
      if (!has(wrong) || (wrong === "Occasion" && a !== "b2c" && a !== "b2pochi")) continue;
      errors.push(`Field '${wrong}' should be spelled ${right}`);
    }
  }

  const command = COMMANDS[a];
  if (command && has(command[0]) && !command[1].includes(body[command[0]])) {
    errors.push(`${command[0]}=${show(body[command[0]])} not valid here; allowed: ${[...command[1]].sort().join(", ")}`);
  }

  if (has("Amount")) {
    const raw = body.Amount;
    const amount = typeof raw === "number" ? raw : typeof raw === "string" && raw.trim() !== "" ? Number(raw) : NaN;
    if (!Number.isFinite(amount)) errors.push(`Amount is not numeric: ${show(raw)}`);
    else if (!Number.isInteger(amount)) errors.push(`Amount must be a whole number, got ${show(raw)}`);
    else if (amount < 1) errors.push("Amount must be at least 1");
    else if ((a === "b2c" || a === "b2pochi") && amount < 10) errors.push("B2C amounts below 10 KES are rejected");
  }

  for (const field of PHONE_FIELDS[a] ?? []) {
    if (has(field) && !PHONE.test(str(body[field]))) {
      errors.push(`${field}=${show(body[field])} must be 2547XXXXXXXX or 2541XXXXXXXX (no +, no leading 0)`);
    }
  }

  for (const field of ["BusinessShortCode", "ShortCode"]) {
    if (has(field) && !SHORTCODE.test(str(body[field]))) errors.push(`${field}=${show(body[field])} should be a 5-7 digit shortcode`);
  }

  for (const field of URL_FIELDS) {
    const url = str(body[field]);
    if (url && !url.startsWith("https://")) errors.push(`${field} must be a public https:// URL, got '${url}'`);
    if (url && /\/\/(localhost|127\.|10\.|192\.168\.)/.test(url)) {
      errors.push(`${field} points at a private/local host Daraja cannot reach: '${url}'`);
    }
    if (a === "c2b_register" && C2B_FORBIDDEN.some((w) => url.toLowerCase().includes(w))) {
      errors.push(`${field} contains a word Daraja rejects for C2B URLs (${C2B_FORBIDDEN.join(", ")})`);
    }
  }

  if (a === "stk" || a === "stk_query") {
    const ts = str(body.Timestamp);
    if (ts && !TIMESTAMP.test(ts)) errors.push(`Timestamp must be YYYYMMDDHHmmss (EAT), got '${ts}'`);
    try {
      const decoded = strictBase64Decode(str(body.Password));
      const sc = str(body.BusinessShortCode);
      if (sc && !decoded.startsWith(sc)) errors.push("Password does not start with BusinessShortCode once decoded - rebuild it");
      if (ts && !decoded.endsWith(ts)) errors.push("Password was built with a different Timestamp than the one in the body");
    } catch {
      errors.push("Password is not valid base64(BusinessShortCode + Passkey + Timestamp)");
    }
  }

  if (a === "stk") {
    if (str(body.AccountReference).length > 12) errors.push("AccountReference longer than 12 characters (long prompts fail with 1025)");
    if (str(body.TransactionDesc).length > 13) errors.push("TransactionDesc longer than 13 characters");
    if (body.PartyA && body.PhoneNumber && body.PartyA !== body.PhoneNumber) {
      errors.push("PartyA and PhoneNumber normally hold the same paying phone number");
    }
  }

  if (a === "tax") {
    if (String(body.PartyB) !== "572572") errors.push("Tax remittance PartyB must be KRA's shortcode 572572");
    for (const f of ["SenderIdentifierType", "RecieverIdentifierType"]) {
      if (has(f) && String(body[f]) !== "4") errors.push(`${f} must be '4' for tax remittance`);
    }
  }

  if (a === "b2b") {
    const expected = body.CommandID === "BusinessBuyGoods" ? "2" : "4";
    if (String(body.RecieverIdentifierType ?? expected) !== expected) {
      errors.push(`RecieverIdentifierType should be ${expected} for ${body.CommandID}`);
    }
  }

  if (a === "reversal" && String(body.RecieverIdentifierType ?? "11") !== "11") {
    errors.push("Reversal RecieverIdentifierType must be '11'");
  }

  if (a === "ratiba") {
    for (const f of ["StartDate", "EndDate"]) {
      if (has(f) && !/^\d{8}$/.test(str(body[f]))) errors.push(`${f} must be YYYYMMDD`);
    }
    if (String(body.StartDate ?? "0") > String(body.EndDate ?? "99999999")) errors.push("EndDate is before StartDate");
    if (!["1", "2", "3", "4", "5", "6", "7", "8"].includes(String(body.Frequency))) errors.push("Frequency must be '1'..'8'");
    const till = body.TransactionType === "Standing Order Customer Pay Marchant";
    if (String(body.ReceiverPartyIdentifierType) !== (till ? "2" : "4")) {
      errors.push("ReceiverPartyIdentifierType must be '2' for Till, '4' for Paybill");
    }
  }

  if (a === "status" && !(body.TransactionID || body.OriginalConversationID)) {
    errors.push("Provide TransactionID or OriginalConversationID");
  }

  return errors;
}
