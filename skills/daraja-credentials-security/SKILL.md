---
name: daraja-credentials-security
description: Manages Safaricom Daraja secrets safely (Consumer Key and Secret, M-Pesa Express passkey, initiator password, SecurityCredential) and generates the SecurityCredential by RSA-encrypting the initiator password with Safaricom's sandbox or production certificate. Covers .env files versus secret managers, fail-fast config, log masking, rotation and leak response. Use when wiring M-Pesa configuration, generating a SecurityCredential, or handling 2001, 18 or 8006 initiator errors.
---

# Daraja credentials and security

## Secret inventory

| Secret | Grants | Sensitivity |
|---|---|---|
| Consumer Key and Secret | Tokens: calling every API on the app | High |
| Passkey | Signing STK requests for the shortcode | High |
| Initiator name and password | B2C, B2B, tax, reversal, status, balance | **Critical** (moves money out) |
| SecurityCredential | Encrypted initiator password. Replayable | **Critical** |
| Access token | One hour of API access | Medium. Keep it in memory or cache only |

## Storage

1. **Never hardcode secrets.** Git history keeps them even after deletion.
2. **Development**: a `.env` file plus `python-dotenv`/`dotenv`. The file is in `.gitignore`, has `chmod 600`, and a `.env.example` without values is committed.
3. **Production**: a secret manager (AWS Secrets Manager/SSM, GCP Secret Manager, Azure Key Vault, Vault, K8s/Docker secrets), injected at runtime with least-privilege access and audit logs.
4. Keep separate credentials per environment, and **no default fallback values in code**.

Fail fast at startup:

```python
REQUIRED = ["DARAJA_CONSUMER_KEY", "DARAJA_CONSUMER_SECRET", "DARAJA_SHORTCODE", "DARAJA_PASSKEY"]
missing = [k for k in REQUIRED if not os.getenv(k, "").strip()]   # .strip() catches trailing newlines
if missing:
    raise RuntimeError(f"Missing M-Pesa config: {', '.join(missing)}")
```

## Generating the SecurityCredential

`SecurityCredential = base64(RSA_PKCS1v1.5_encrypt(initiator_password, certificate_public_key))`

1. Download the **sandbox** or **production** certificate from the Daraja portal. It must match the environment you will call.
2. Run the script. It reads the password from the environment so it never lands in shell history:
   ```bash
   DARAJA_INITIATOR_PASSWORD='...' python scripts/security_credential.py ProductionCertificate.cer
   ```
   It uses `cryptography` if installed (`pip install cryptography`), otherwise the `openssl` CLI. The output differs on every run because of random padding; that is expected.
3. Store the output as `DARAJA_SECURITY_CREDENTIAL` in the secret store.
4. Verify it with one sandbox `account_balance` call. A `2001` or `18` result means the wrong password or the wrong certificate: go back to step 1.

Node.js equivalent:

```js
crypto.publicEncrypt({ key: fs.readFileSync(certPath), padding: crypto.constants.RSA_PKCS1_PADDING },
                     Buffer.from(process.env.DARAJA_INITIATOR_PASSWORD)).toString("base64");
```

## Operational hygiene

- Mask secrets and `Authorization` headers in logs, APM tools and CI output. Masking is not a substitute for not printing them.
- Rotate the consumer secret (regenerate it in the portal) and the initiator password on a schedule and when staff leave. Regenerate the SecurityCredential after each password change.
- Repeated wrong passwords lock the initiator (`8006`). An org-portal admin unlocks it.
- Restrict who can deploy or run payout code. Require approval for reversals and large B2C payments.

## Leak response (rotation first, cleanup second)

```
- [ ] Regenerate consumer secret / reset initiator password in the portals NOW
- [ ] Update the secret manager; redeploy
- [ ] Review recent transactions and token usage for abuse
- [ ] Purge from git history (git filter-repo) and force-rotate anything else in the same file
- [ ] Post-mortem: add secret scanning (gitleaks / GitHub push protection)
```

## MCP

The `mpesa` server accepts either `DARAJA_SECURITY_CREDENTIAL`, or `DARAJA_INITIATOR_PASSWORD` plus `DARAJA_CERT_PATH`, in which case it encrypts at startup. It never returns secrets in tool output.
