---
name: daraja-tax-remittance
description: Remits taxes to the Kenya Revenue Authority (KRA) from a business shortcode through Safaricom Daraja's Tax Remittance API (CommandID PayTaxToKRA, PartyB 572572, AccountReference set to the KRA Payment Registration Number). Use when a system must pay KRA taxes such as VAT, PAYE or withholding tax via M-Pesa.
---

# Tax Remittance to KRA

**Pre-condition:** your business needs a prior integration with KRA to declare tax and generate a **PRN (Payment Registration Number)**. Daraja only moves the money.

## Request

`POST /mpesa/b2b/v1/remittax`

```json
{
  "Initiator": "TaxPayer",
  "SecurityCredential": "<encrypted>",
  "CommandID": "PayTaxToKRA",
  "SenderIdentifierType": "4",
  "RecieverIdentifierType": "4",
  "Amount": 239,
  "PartyA": "888880",
  "PartyB": "572572",
  "AccountReference": "PRN1234XN",
  "Remarks": "VAT Sept",
  "QueueTimeOutURL": "https://example.com/payments/tax/timeout",
  "ResultURL": "https://example.com/payments/tax/result"
}
```

Fixed values: `PartyB` is always `572572`, both identifier types are always `"4"`, and `AccountReference` is the PRN.

Validate the body: `python scripts/validate_request.py tax body.json`

## Responses

- **Sync**: `ResponseCode "0"`, `ConversationID` and `OriginatorConversationID`.
- **Result**: the B2B envelope. `TransactionID` is the receipt, and `ResultParameters` include `Amount`, `DebitPartyAffectedAccountBalance`, `TransCompletedTime` and `ReceiverPartyPublicName` (the tax collector).

## Workflow

```
- [ ] PRN obtained from KRA for this exact amount
- [ ] Record tax_payment(prn UNIQUE, amount, status=PENDING)
- [ ] Send request; store ConversationID
- [ ] Result 0 → PAID with TransactionID; keep the receipt for KRA reconciliation
- [ ] Timeout/no result → transaction_status before re-sending (a PRN must not be paid twice)
```

Errors and the initiator setup are the same as B2B (see `daraja-b2b` and `daraja-troubleshooting`).

## MCP

`mpesa_b2b_payment(receiver_shortcode="572572", amount=…, account_reference="<PRN>", command="PayTaxToKRA")`. The tool forces `PartyB=572572` and the remittax endpoint.
