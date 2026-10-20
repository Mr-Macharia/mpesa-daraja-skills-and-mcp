#!/usr/bin/env python3
"""Encrypt an initiator password into a Daraja SecurityCredential.

Usage:
    MPESA_INITIATOR_PASSWORD=... python scripts/security_credential.py <certificate.cer>

Use SandboxCertificate.cer for the sandbox and ProductionCertificate.cer for production.

Reads the password from the environment (never pass it as an argument: it
would land in shell history). Uses the `cryptography` package if installed,
otherwise falls back to the `openssl` CLI. Output differs per run (random
PKCS#1 v1.5 padding) - that is expected.
"""
import base64
import os
import shutil
import subprocess
import sys

if len(sys.argv) != 2:
    sys.exit(__doc__)
cert_path = sys.argv[1]
password = os.environ.get("MPESA_INITIATOR_PASSWORD", "")
if not password:
    sys.exit("Set MPESA_INITIATOR_PASSWORD in the environment first")
if not os.path.exists(cert_path):
    sys.exit(f"Certificate not found: {cert_path}. Download it from the Daraja portal (docs / test credentials).")

data = open(cert_path, "rb").read()
try:
    from cryptography import x509
    from cryptography.hazmat.primitives.asymmetric import padding

    try:
        cert = x509.load_pem_x509_certificate(data)
    except ValueError:
        cert = x509.load_der_x509_certificate(data)
    encrypted = cert.public_key().encrypt(password.encode(), padding.PKCS1v15())
except ImportError:
    if not shutil.which("openssl"):
        sys.exit("Install `cryptography` (pip install cryptography) or the openssl CLI")
    fmt = "PEM" if b"BEGIN CERTIFICATE" in data else "DER"
    pem = subprocess.run(["openssl", "x509", "-inform", fmt, "-in", cert_path],
                         capture_output=True, check=True).stdout
    pub = subprocess.run(["openssl", "x509", "-pubkey", "-noout"], input=pem,
                         capture_output=True, check=True).stdout
    keyfile = cert_path + ".pub.pem"
    open(keyfile, "wb").write(pub)
    try:
        encrypted = subprocess.run(
            ["openssl", "pkeyutl", "-encrypt", "-pubin", "-inkey", keyfile,
             "-pkeyopt", "rsa_padding_mode:pkcs1"],
            input=password.encode(), capture_output=True, check=True).stdout
    finally:
        os.remove(keyfile)

print(base64.b64encode(encrypted).decode())
