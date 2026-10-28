import type { ICredentialTestRequest, ICredentialType, INodeProperties } from "n8n-workflow";

const secret = { typeOptions: { password: true } };

export class MpesaDarajaApi implements ICredentialType {
  name = "mpesaDarajaApi";
  displayName = "M-Pesa Daraja API";
  documentationUrl = "https://github.com/Mr-Macharia/mpesa-daraja-skills-and-mcp/tree/main/node/packages/n8n-nodes-daraja-mpesa";
  properties: INodeProperties[] = [
    {
      displayName: "Environment", name: "environment", type: "options", default: "sandbox",
      options: [{ name: "Sandbox", value: "sandbox" }, { name: "Production", value: "production" }],
    },
    { displayName: "Consumer Key", name: "consumerKey", type: "string", default: "", required: true, ...secret },
    { displayName: "Consumer Secret", name: "consumerSecret", type: "string", default: "", required: true, ...secret },
    { displayName: "Shortcode", name: "shortcode", type: "string", default: "174379", description: "Your Paybill or Till (sandbox: 174379 for STK, 600000 for payouts)" },
    { displayName: "Passkey", name: "passkey", type: "string", default: "", description: "For STK Push", ...secret },
    { displayName: "Initiator Name", name: "initiatorName", type: "string", default: "", description: "For B2C, B2B, status, balance and reversal" },
    {
      displayName: "Security Credential", name: "securityCredential", type: "string", default: "",
      description: "The initiator password encrypted with Safaricom's certificate (from the Daraja portal)", ...secret,
    },
    {
      displayName: "Allow Live Money Movement", name: "allowLiveMoneyMovement", type: "boolean", default: false,
      description: "Whether production charges and payouts may run. In production everything that moves money is refused until this is on.",
    },
    {
      displayName: "Read Only", name: "readOnly", type: "boolean", default: false,
      description: "Whether to refuse every operation that moves money",
    },
    {
      displayName: "Approval Threshold (KES)", name: "approvalThreshold", type: "number", default: 0,
      description: "Payouts above this need the node's Approved field set to true. 0 turns the check off.",
    },
    {
      displayName: "Allowed Recipients", name: "allowedRecipients", type: "string", default: "",
      description: "Comma-separated phones or shortcodes payouts may go to. Empty allows any.",
    },
  ];

  test: ICredentialTestRequest = {
    request: {
      baseURL: '={{$credentials.environment === "production" ? "https://api.safaricom.co.ke" : "https://sandbox.safaricom.co.ke"}}',
      url: "/oauth/v1/generate?grant_type=client_credentials",
      auth: { username: "={{$credentials.consumerKey}}", password: "={{$credentials.consumerSecret}}" },
    },
  };
}
