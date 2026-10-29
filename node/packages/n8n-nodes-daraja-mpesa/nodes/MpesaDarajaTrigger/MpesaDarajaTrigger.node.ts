import type {
  IDataObject, INodeType, INodeTypeDescription, IWebhookFunctions, IWebhookResponseData,
} from "n8n-workflow";
import { client, lib, StaticDataStore } from "../shared.js";

const ACK = { ResultCode: 0, ResultDesc: "Accepted" };

export class MpesaDarajaTrigger implements INodeType {
  description: INodeTypeDescription = {
    displayName: "M-Pesa Trigger",
    name: "mpesaDarajaTrigger",
    icon: "file:mpesa.svg",
    group: ["trigger"],
    version: 1,
    description: "Starts the workflow when Daraja posts a callback: STK results, B2C/B2B results, C2B payments, status, balance",
    defaults: { name: "M-Pesa Trigger" },
    inputs: [],
    outputs: ["main"],
    credentials: [{ name: "mpesaDarajaApi", required: true }],
    webhooks: [{ name: "default", httpMethod: "POST", responseMode: "onReceived", path: "mpesa" }],
    properties: [
      {
        displayName: "Use this trigger's Production URL as the Callback URL in M-Pesa Daraja nodes, or as a C2B confirmation URL. " +
          "It replies to Daraja at once. A result whose status is UNKNOWN came from a queue timeout: check the transaction before retrying.",
        name: "notice", type: "notice", default: "",
      },
      {
        displayName: "Only Successful", name: "onlySuccess", type: "boolean", default: false,
        description: "Whether to start the workflow only for successful results (failed and timed-out callbacks are still stored)",
      },
    ],
  };

  async webhook(this: IWebhookFunctions): Promise<IWebhookResponseData> {
    const body = this.getBodyData() as IDataObject;
    const timeout = Boolean((this.getQueryData() as IDataObject).timeout);
    const { parseCallback } = await lib();
    try {
      parseCallback(body);
    } catch {
      // Not a Daraja callback. Acknowledge so Daraja does not retry, but start nothing.
      return { webhookResponse: ACK, noWebhookResponse: false };
    }
    const creds = (await this.getCredentials("mpesaDarajaApi")) as IDataObject;
    const daraja = await client(creds, new StaticDataStore(this.getWorkflowStaticData("global")));
    const { status, parsed } = await daraja.handleCallback(body, { timeout });
    if (this.getNodeParameter("onlySuccess", false) && status !== "SUCCESS") return { webhookResponse: ACK };
    return { webhookResponse: ACK, workflowData: [[{ json: { status, ...parsed } as IDataObject }]] };
  }
}
