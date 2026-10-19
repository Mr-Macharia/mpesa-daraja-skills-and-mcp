import base64
from datetime import datetime, timezone

import pytest

from mpesa_mcp import helpers


@pytest.mark.parametrize("raw", ["0712345678", "712345678", "+254712345678", "254 712-345-678"])
def test_normalize_phone(raw):
    assert helpers.normalize_phone(raw) == "254712345678"


def test_normalize_phone_accepts_01_prefix():
    assert helpers.normalize_phone("0110000000") == "254110000000"


@pytest.mark.parametrize("raw", ["12345", "0812345678", "2547123456789", "abc"])
def test_normalize_phone_rejects(raw):
    with pytest.raises(ValueError):
        helpers.normalize_phone(raw)


def test_timestamp_is_eat():
    utc = datetime(2026, 10, 19, 21, 30, 5, tzinfo=timezone.utc)
    assert helpers.timestamp(utc) == "20261020003005"


def test_stk_password():
    pwd = helpers.stk_password("174379", "pk", "20261019153045")
    assert base64.b64decode(pwd).decode() == "174379pk20261019153045"


def test_validate_amount():
    assert helpers.validate_amount("10") == 10
    with pytest.raises(ValueError):
        helpers.validate_amount(10.5)
    with pytest.raises(ValueError):
        helpers.validate_amount(5, minimum=10)


def test_parse_stk_success():
    payload = {"Body": {"stkCallback": {
        "MerchantRequestID": "m1", "CheckoutRequestID": "ws_CO_1", "ResultCode": 0,
        "ResultDesc": "ok", "CallbackMetadata": {"Item": [
            {"Name": "Amount", "Value": 1.0}, {"Name": "MpesaReceiptNumber", "Value": "NLJ7RT61SV"},
            {"Name": "TransactionDate", "Value": 20191219102115}, {"Name": "PhoneNumber", "Value": 254708374149}]}}}}
    out = helpers.parse_callback(payload)
    assert out["success"] and out["receipt"] == "NLJ7RT61SV" and out["checkout_request_id"] == "ws_CO_1"


def test_parse_stk_cancelled():
    out = helpers.parse_callback({"Body": {"stkCallback": {"ResultCode": 1032, "ResultDesc": "cancelled"}}})
    assert not out["success"] and "cancelled" in out["explanation"].lower()


def test_parse_result_single_param_object_and_alpha_code():
    out = helpers.parse_callback({"Result": {"ResultCode": "R000002", "ResultDesc": "bad",
        "ResultParameters": {"ResultParameter": {"Key": "X", "Value": 1}}}})
    assert out["result_code"] == "R000002" and out["parameters"] == {"X": 1} and not out["success"]


def test_parse_balance():
    raw = "Working Account|KES|700000.00|700000.00|0.00|0.00&Utility Account|KES|228037.00|228037.00|0.00|0.00"
    out = helpers.parse_callback({"Result": {"ResultCode": 0, "ResultParameters": {
        "ResultParameter": [{"Key": "AccountBalance", "Value": raw}]}}})
    assert out["balances"][1] == {"account": "Utility Account", "currency": "KES", "available": 228037.0,
                                  "raw": ["228037.00", "228037.00", "0.00", "0.00"]}


def test_parse_c2b():
    out = helpers.parse_callback({"TransID": "RKL51ZDR4F", "TransAmount": "5.00", "BillRefNumber": "A1"})
    assert out["kind"] == "c2b" and out["amount"] == 5.0


def test_unknown_payload():
    with pytest.raises(ValueError):
        helpers.parse_callback({"foo": 1})


def test_explain_code():
    assert "PIN" in helpers.explain_code(2001)
    assert "Unknown" in helpers.explain_code("nope")


def test_security_credential_roundtrip():
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.x509.oid import NameOID
    import datetime as dt

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test")])
    now = dt.datetime.now(dt.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(1).not_valid_before(now).not_valid_after(now + dt.timedelta(days=1))
            .sign(key, hashes.SHA256()))
    for encoding in (serialization.Encoding.PEM, serialization.Encoding.DER):
        cred = helpers.security_credential("Safaricom999!", cert.public_bytes(encoding))
        assert key.decrypt(base64.b64decode(cred), padding.PKCS1v15()) == b"Safaricom999!"
