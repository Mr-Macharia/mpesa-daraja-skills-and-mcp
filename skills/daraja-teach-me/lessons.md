# Lessons

Each lesson: the idea, a sandbox step, what to read in the response, and a check question. Commands use the `mpesa` CLI; the MCP tool with the same job is given in brackets. The sandbox test phone is the learner's own Safaricom number registered on the Daraja portal, as `2547XXXXXXXX`.

## F. Foundations

### F1 What Daraja is
**Idea.** Daraja is Safaricom's web API for M-Pesa. Your server sends HTTPS requests; M-Pesa does the money movement; the result comes back later to a URL you host. A business is identified by its **shortcode** (Paybill or Till number).

```
your server ──request──▶ Daraja ──▶ M-Pesa ──▶ customer's phone
     ▲                                              │
     └────────────── callback (result) ◀────────────┘
```

**Try it.** Nothing to run yet. Ask what they want to build.
**Check.** "Where does the final result of a payment arrive?" (At your callback URL, later; not in the first response.)

### F2 Sandbox app and keys
**Idea.** The sandbox is a test copy of Daraja with fake money. You create an app on developer.safaricom.co.ke and get a **consumer key** and **consumer secret**. The sandbox shortcode `174379` and its **passkey** are published on the portal for STK Push tests.

**Try it.**
```bash
mpesa init        # asks for the keys and saves them outside the repo
mpesa status      # [mpesa_setup_status]
```
**Read it.** Environment says `sandbox`; credentials show as set, never their values.
**Check.** "Why must the consumer secret never go into git?" (Anyone with it can call Daraja as you.)

### F3 Tokens
**Idea.** Every call needs a bearer **token**. You get one by sending the key and secret to the OAuth endpoint; it lasts about an hour. Good code caches it and fetches a new one on a 401.

**Try it.** `[mpesa_check_credentials]`, or `mpesa status`, which fetches one.
**Read it.** Success means the key and secret are right. A 400/401 here means wrong keys or the wrong environment.
**Check.** "What should your code do when a call returns 401?" (Get a new token once, retry once.)

### F4 Accepted is not paid
**Idea.** Daraja answers in two steps. The first response, with `ResponseCode "0"`, only means "request accepted". The customer may still cancel, or not answer. The real outcome is the `ResultCode` in the callback (or a status query). `ResultCode 0` means success.

```
request ─▶ ResponseCode "0"   = accepted (nothing paid yet)
       ... customer enters PIN / cancels / ignores ...
callback ─▶ ResultCode 0      = paid
            ResultCode 1032   = cancelled
            ResultCode 1037   = no answer
```

**Try it.** `mpesa explain 1032` `[mpesa_explain_code]`.
**Check.** "Your code marks an order paid when `ResponseCode` is `"0"`. What goes wrong?" (Orders get marked paid when the customer cancelled.)

## C. Collecting money

### C1 STK Push
**Idea.** STK Push (M-Pesa Express) sends a PIN prompt to the customer's phone. You send the phone, amount, shortcode, an account reference (your order number) and a **password**: base64 of shortcode + passkey + timestamp, the timestamp in EAT.

**Try it.**
```bash
mpesa pay stk 2547XXXXXXXX 10     # [mpesa_stk_push_and_wait]
```
The learner approves on the phone.
**Read it.** `CheckoutRequestID` (the handle for this payment), then the final status and receipt.
**Check.** "Why whole shillings only?" (Daraja rejects fractions.) Note: sandbox may reject very small amounts with code 2, and sometimes answers 9999 "retry later"; retry with the same `--key`.

### C2 STK Query
**Idea.** If the callback is late or lost, ask Daraja directly with the `CheckoutRequestID`.

**Try it.** `mpesa pay stk 2547XXXXXXXX 10 --no-wait`, then `mpesa result <id>` `[mpesa_stk_query]`.
**Read it.** "still processing" while the prompt is open; a `ResultCode` once final.
**Check.** "When would your app call STK Query on its own?" (For payments still pending after a couple of minutes.)

### C3 Paybill and Till (C2B)
**Idea.** Here the customer starts the payment from their phone menu. You register a **confirmation URL** (and optionally a **validation URL**) for your shortcode, and M-Pesa calls it on each payment. The customer types an account number; you match it to an invoice.

**Try it.** `[mpesa_c2b_register_urls]`, then `[mpesa_c2b_simulate]` (sandbox only).
**Check.** "A payment arrives with an account number you don't know. What do you do?" (Store it as unmatched and resolve it; never drop it.)

### C4 Dynamic QR
**Idea.** A QR code that encodes your till and an amount; the customer scans it in the M-Pesa app.
**Try it.** `[mpesa_generate_dynamic_qr]`.
**Check.** "How do you learn that the QR was paid?" (The same way as C2B: the confirmation, or a status query.)

## K. Callbacks

### K1 What a callback is
**Idea.** A callback is an HTTPS POST that Daraja sends to your URL with the result. The URL must be public HTTPS. Your handler replies fast with `{"ResultCode": 0, "ResultDesc": "Accepted"}` and does slow work later.

**Try it.** Show a sample body and parse it: `[mpesa_parse_callback]`.
**Read it.** `ResultCode`, `MpesaReceiptNumber`, `Amount`, `CheckoutRequestID`.
**Check.** "Why reply before sending the customer an email?" (A slow reply times out, and Daraja retries.)

### K2 A local receiver with a tunnel
**Idea.** Your laptop isn't public, so a **tunnel** gives it a temporary public HTTPS URL that forwards to a local port.

**Try it.** Two terminals:
```bash
mpesa dev                          # terminal 1: receiver + tunnel, prints the URL
mpesa pay stk 2547XXXXXXXX 10      # terminal 2
```
**Read it.** Terminal 1 logs the callback with the same `CheckoutRequestID`.
**Check.** "What changes when you deploy?" (The callback URL becomes your own HTTPS domain.)

### K3 Duplicates and idempotency
**Idea.** The same callback can arrive twice. Processing it twice credits the order twice. Make the receipt unique in your database so the second copy changes nothing. **Idempotency** means doing a thing twice has the same effect as once.

**Try it.** POST the same sample callback twice to their receiver (or reason through it with a tiny table).
**Check.** "Which column gets a UNIQUE constraint?" (The M-Pesa receipt, and the `CheckoutRequestID`.)

## P. Paying out

### P1 B2C
**Idea.** B2C sends money from a business to a phone. It needs an **initiator** (an API user) and a **SecurityCredential**: the initiator password encrypted with Safaricom's certificate. Results come to a `ResultURL`.

**Try it.** `mpesa pay b2c 2547XXXXXXXX 10` `[mpesa_b2c_payment]`.
**Read it.** `ConversationID` and `OriginatorConversationID`; final status later.
**Check.** "Why is B2C more dangerous than STK Push?" (Money leaves your account; a mistake pays someone.)

### P2 Timeouts and unknown outcomes
**Idea.** Sometimes you send a payout and get no answer. The money may or may not have moved. **Never resend.** Query Transaction Status first. Reusing the same **idempotency key** makes a retry safe with the MCP server.

```
send ─▶ no answer ─▶ UNKNOWN ─▶ Transaction Status ─▶ paid? stop : now safe to retry
                       ✗ resend (could pay twice)
```

**Check.** "The network dropped after you sent a KES 5,000 B2C. Your colleague wants to click Send again. What do you say?"

### P3 B2B
**Idea.** Business to business: paying a Paybill or Till, or topping up your own B2C account. Daraja's field is spelled `RecieverIdentifierType`; keep that spelling.
**Try it.** `mpesa pay b2b 600000 10` (a sandbox test shortcode) `[mpesa_b2b_payment]`.
**Check.** "Why not fix the spelling of `RecieverIdentifierType`?" (Daraja rejects the corrected name.)

## O. Operations

### O1 Transaction Status
**Idea.** Ask M-Pesa what happened to a transaction, by receipt or originator ID. The answer comes to your `ResultURL`.
**Try it.** `[mpesa_transaction_status]` on the receipt from C1.
**Check.** "Which states in your system should trigger this query?" (Accepted or timed out for too long.)

### O2 Reversal
**Idea.** Pulls a whole customer payment back. No partial amounts; for those, refund with B2C.
**Try it.** `mpesa pay reverse <receipt> 10` `[mpesa_reverse_transaction]`.
**Check.** "A customer paid KES 1,000 and wants KES 300 back. Reversal or B2C?" (B2C.)

### O3 Account Balance
**Idea.** Your shortcode's balance, delivered to your `ResultURL`.
**Try it.** `mpesa balance` `[mpesa_account_balance]`.
**Check.** "How does the balance help reconciliation?" (The day's change should equal the day's ledger total.)

## D. Payment design

Teach from `daraja-payment-design`; these lessons are the guided tour.

- **D1 The state machine**: initiated → accepted → confirmed / failed / timed_out. Check: "Which signal is allowed to move a payment to confirmed?"
- **D2 The ledger**: integer shillings, unique receipts, raw events, never edit money in place. Have them sketch the `payments` table. Check: "How do you record a refund?"
- **D3 Reconciliation**: daily match against Safaricom's records into matched, orphan at Safaricom, orphan in ledger, mismatch. Check: "Money arrived with no order. Which bucket?"
- **D4 Going live**: walk the go-live checklist; run `check_integration.py` on their code. Check: "What's the one real-money test before launch?"
