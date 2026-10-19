---
name: daraja-credentials-security
description: Securely manage Safaricom Daraja secrets — Consumer Key/Secret, Lipa na M-Pesa passkey, initiator password — and generate the SecurityCredential by RSA-encrypting the initiator password with Safaricom's certificate. Covers .env usage, secret managers, rotation, fail-fast config, log masking and leak response. Use when wiring configuration or when any SecurityCredential/initiator error occurs.
---

# Daraja Credentials & Security

## Secret inventory

| Secret | Used for | Sensitivity |
|---|---|---|
| Consumer Key + Secret | OAuth tokens | High — anyone can call APIs as you |
| Passkey | STK Password | High |
| Initiator name + password | B2C/B2B/Status/Reversal/Balance | **Critical** — can move money out |
| SecurityCredential | Encrypted initiator password | Critical (replayable) |
| Access token | 1 hour bearer | Medium; memory/cache only |

## Storage hierarchy

1. **Never hardcode** — git history keeps leaked secrets forever, even after deletion.
2. **Development**: `.env` + `python-dotenv` / `dotenv`, `.env` in `.gitignore`, file mode `600`.
3. **Production**: a secret manager (AWS Secrets Manager / SSM, GCP Secret Manager, Azure Key Vault, HashiCorp Vault, Docker/K8s secrets) injected at runtime; least-privilege IAM; audit logs.
4. Separate credentials per environment; never a "fallback" default value in code.

## Fail fast

```python
REQUIRED = ["MPESA_CONSUMER_KEY", "MPESA_CONSUMER_SECRET", "MPESA_SHORTCODE", "MPESA_PASSKEY"]
missing = [k for k in REQUIRED if not os.getenv(k, "").strip()]
if missing:
    raise RuntimeError(f"Missing M-Pesa config: {', '.join(missing)}")
```
`.strip()` also catches the common trailing-newline bug.

## Generating the SecurityCredential

`SecurityCredential = base64( RSA_encrypt_PKCS1v1.5( initiator_password, safaricom_cert_public_key ) )`

Download the certificate from the Daraja portal: **SandboxCertificate.cer** for sandbox, **ProductionCertificate.cer** for production — using the wrong one gives `2001`/"initiator information is invalid".

Python (`cryptography`):
```python
import base64
from cryptography import x509
from cryptography.hazmat.primitives.asymmetric import padding

def security_credential(password: str, cert_path: str) -> str:
    with open(cert_path, "rb") as f:
        data = f.read()
    try:
        cert = x509.load_pem_x509_certificate(data)
    except ValueError:
        cert = x509.load_der_x509_certificate(data)
    encrypted = cert.public_key().encrypt(password.encode(), padding.PKCS1v15())
    return base64.b64encode(encrypted).decode()
```

Node.js:
```js
const crypto = require("crypto"), fs = require("fs");
const cert = fs.readFileSync("ProductionCertificate.cer");
const cred = crypto.publicEncrypt(
  { key: cert, padding: crypto.constants.RSA_PKCS1_PADDING },
  Buffer.from(process.env.MPESA_INITIATOR_PASSWORD)
).toString("base64");
```
OpenSSL: `printf '%s' "$PASS" | openssl pkeyutl -encrypt -certin -inkey ProductionCertificate.cer -pkeyopt rsa_padding_mode:pkcs1 | base64 -w0`

Output differs each run (random padding) — that's expected. Initiator passwords expire/lock after failed attempts (`8006`); rotate in the org portal and regenerate.

## Operational hygiene

- Mask secrets and `Authorization` headers in logs, error trackers, CI output.
- Rotate Consumer Secret (portal regenerate) and initiator password on schedule and on staff exit.
- Leak response: revoke/regenerate in the portal immediately → update secret manager → redeploy → audit transactions → purge from git history (`git filter-repo`) — rotation first, cleanup second.
- Restrict who can run payout code paths; require approvals for reversals and large B2C.
