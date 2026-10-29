import { NodeOperationError } from "n8n-workflow";
import type {
  IDataObject, IExecuteFunctions, INodeExecutionData, INodeProperties, INodeType, INodeTypeDescription,
} from "n8n-workflow";
import { client, StaticDataStore } from "../shared.js";

const MONEY = ["stkPush", "stkPushAndWait", "b2c", "b2b", "reverse"];
const PAYOUTS = ["b2c", "b2b", "reverse"];
const CALLBACK = ["stkPush", "stkPushAndWait", "b2c", "b2b", "transactionStatus", "accountBalance", "reverse"];

const show = (...operation: string[]) => ({ displayOptions: { show: { operation } } });

const properties: INodeProperties[] = [
  {
    displayName: "Operation", name: "operation", type: "options", noDataExpression: true, default: "stkPushAndWait",
    options: [
      { name: "STK Push and Wait", value: "stkPushAndWait", action: "Charge a customer and wait for the result",
        description: "Send a PIN prompt and wait for SUCCESS, FAILED or UNKNOWN" },
      { name: "STK Push", value: "stkPush", action: "Send a PIN prompt",
        description: "Returns ACCEPTED straight away. The result arrives on the M-Pesa Trigger." },
      { name: "STK Query", value: "stkQuery", action: "Check an STK push" },
      { name: "Get Result", value: "getResult", action: "Get the stored result of a request",
        description: "By idempotency key or any Daraja ID, from callbacks this workflow's M-Pesa Trigger received" },
      { name: "B2C Payment", value: "b2c", action: "Pay a customer", description: "Pay or refund an M-Pesa wallet" },
      { name: "B2B Payment", value: "b2b", action: "Pay a business", description: "Paybill, Till, or KRA tax" },
      { name: "Transaction Status", value: "transactionStatus", action: "Ask M-Pesa for a transaction's final state" },
      { name: "Account Balance", value: "accountBalance", action: "Request the shortcode balances" },
      { name: "Reverse Transaction", value: "reverse", action: "Reverse a C2B payment" },
    ],
  },
  { displayName: "Phone", name: "phone", type: "string", default: "", required: true, placeholder: "0712345678",
    description: "Kenyan phone in any format", ...show("stkPush", "stkPushAndWait", "b2c") },
  { displayName: "Amount (KES)", name: "amount", type: "number", default: 1, required: true, typeOptions: { minValue: 1 },
    description: "Whole shillings", ...show("stkPush", "stkPushAndWait", "b2c", "b2b", "reverse") },
  { displayName: "Account Reference", name: "accountReference", type: "string", default: "", required: true,
    description: "Order number (max 12 characters), Paybill account, or KRA PRN", ...show("stkPush", "stkPushAndWait", "b2b") },
  { displayName: "Description", name: "description", type: "string", default: "Payment",
    description: "Shown on the prompt, max 13 characters", ...show("stkPush", "stkPushAndWait") },
  { displayName: "Wait (Seconds)", name: "timeoutS", type: "number", default: 90, typeOptions: { minValue: 10, maxValue: 300 },
    ...show("stkPushAndWait") },
  { displayName: "Checkout Request ID", name: "checkoutRequestId", type: "string", default: "", required: true, ...show("stkQuery") },
  { displayName: "ID", name: "id", type: "string", default: "", required: true,
    description: "Idempotency key, CheckoutRequestID, ConversationID or OriginatorConversationID", ...show("getResult") },
  { displayName: "Receiver Shortcode", name: "receiverShortcode", type: "string", default: "", required: true,
    description: "Paybill or Till. Ignored for PayTaxToKRA.", ...show("b2b") },
  { displayName: "Command", name: "command", type: "options", default: "BusinessPayBill", ...show("b2b"),
    options: ["BusinessPayBill", "BusinessBuyGoods", "BusinessPayToBulk", "PayTaxToKRA"].map((v) => ({ name: v, value: v })) },
  { displayName: "Remarks", name: "remarks", type: "string", default: "", required: true, description: "The reason", ...show("b2c", "reverse") },
  { displayName: "Refund Of", name: "refundOf", type: "string", default: "",
    description: "For a refund, the original M-Pesa receipt", ...show("b2c") },
  { displayName: "Transaction ID", name: "transactionId", type: "string", default: "", required: true,
    description: "The M-Pesa receipt", ...show("reverse") },
  { displayName: "Transaction ID", name: "statusTransactionId", type: "string", default: "",
    description: "The M-Pesa receipt. Give this or the OriginatorConversationID.", ...show("transactionStatus") },
  { displayName: "OriginatorConversationID", name: "originalConversationId", type: "string", default: "", ...show("transactionStatus") },
  {
    displayName: "Idempotency Key", name: "idempotencyKey", type: "string", default: "",
    description: "A stable ID such as the order ID. Running again with the same key never charges or pays twice. Required for payouts (except KRA tax).",
    required: false, ...show("stkPush", "stkPushAndWait", "b2c", "b2b"),
  },
  {
    displayName: "Callback URL", name: "callbackUrl", type: "string", default: "", required: true,
    placeholder: "https://n8n.example.com/webhook/…/mpesa",
    description: "The Production URL of an M-Pesa Trigger node (public HTTPS)", ...show(...CALLBACK),
  },
  {
    displayName: "Approved", name: "approved", type: "boolean", default: false,
    description: "Whether a human approved this payout. Only needed above the credential's approval threshold; set it from an approval step, never from an AI agent.",
    ...show(...PAYOUTS),
  },
];

export class MpesaDaraja implements INodeType {
  description: INodeTypeDescription = {
    displayName: "M-Pesa Daraja",
    name: "mpesaDaraja",
    icon: "file:mpesa.svg",
    group: ["transform"],
    version: 1,
    subtitle: '={{$parameter["operation"]}}',
    description: "Charge, pay and check M-Pesa payments with Safaricom Daraja. ACCEPTED means sent, not paid.",
    defaults: { name: "M-Pesa Daraja" },
    inputs: ["main"],
    outputs: ["main"],
    credentials: [{ name: "mpesaDarajaApi", required: true }],
    properties,
  };

  async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
    const creds = (await this.getCredentials("mpesaDarajaApi")) as IDataObject;
    const store = new StaticDataStore(this.getWorkflowStaticData("global"));
    const out: INodeExecutionData[] = [];

    for (let i = 0; i < this.getInputData().length; i++) {
      const p = <T = string>(name: string, fallback?: T) => this.getNodeParameter(name, i, fallback) as T;
      const op = p("operation");
      const optional = (name: string) => p(name, "").trim() || undefined;
      try {
        const daraja = await client(creds, store, PAYOUTS.includes(op) && p("approved", false));
        const url = CALLBACK.includes(op) ? p("callbackUrl").trim() : "";
        const urls = { resultUrl: url, timeoutUrl: url && `${url}${url.includes("?") ? "&" : "?"}timeout=1` };
        const stk = () => ({
          phone: p("phone"), amount: p<number>("amount"), accountReference: p("accountReference"),
          description: optional("description"), idempotencyKey: optional("idempotencyKey"), callbackUrl: url,
        });
        let result: unknown;
        switch (op) {
          case "stkPush": result = await daraja.stkPush(stk()); break;
          case "stkPushAndWait": result = await daraja.stkPushAndWait({ ...stk(), timeoutS: p<number>("timeoutS", 90) }); break;
          case "stkQuery": result = await daraja.stkQuery(p("checkoutRequestId").trim()); break;
          case "getResult": result = await daraja.getResult(p("id").trim()); break;
          case "b2c":
            result = await daraja.b2cPayment({ phone: p("phone"), amount: p<number>("amount"), remarks: p("remarks"),
              idempotencyKey: optional("idempotencyKey") ?? "", refundOf: optional("refundOf"), ...urls });
            break;
          case "b2b":
            result = await daraja.b2bPayment({ receiverShortcode: p("receiverShortcode").trim(), amount: p<number>("amount"),
              accountReference: p("accountReference"), command: p("command"), idempotencyKey: optional("idempotencyKey"), ...urls });
            break;
          case "transactionStatus":
            result = await daraja.transactionStatus({ transactionId: optional("statusTransactionId"),
              originalConversationId: optional("originalConversationId"), ...urls });
            break;
          case "accountBalance": result = await daraja.accountBalance(urls); break;
          case "reverse":
            result = await daraja.reverseTransaction({ transactionId: p("transactionId").trim(), amount: p<number>("amount"),
              remarks: p("remarks"), ...urls });
            break;
          default: throw new Error(`Unknown operation '${op}'`);
        }
        out.push({ json: result as IDataObject, pairedItem: { item: i } });
      } catch (exc) {
        let message = exc instanceof Error ? exc.message : String(exc);
        if (message.startsWith("Payout not approved")) {
          message += " It is above the credential's approval threshold: add an approval step and set Approved from it.";
        }
        if (MONEY.includes(op)) message += " Check the result before retrying, and retry only with the same idempotency key.";
        if (this.continueOnFail()) {
          out.push({ json: { error: message }, pairedItem: { item: i } });
          continue;
        }
        throw new NodeOperationError(this.getNode(), message, { itemIndex: i });
      }
    }
    return [out];
  }
}
