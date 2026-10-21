import os
import tempfile

# Isolate tests from the developer's real M-Pesa config. settings.load() runs when the server
# module is imported, so before that: an empty config dir, no project .env, no DARAJA_* vars.
_ISOLATED = tempfile.mkdtemp(prefix="mpesa-test-")
for _key in [k for k in os.environ if k.startswith("DARAJA_")]:
    del os.environ[_key]
os.environ["DARAJA_CONFIG_DIR"] = os.path.join(_ISOLATED, "config")
os.environ["DARAJA_DOTENV"] = os.path.join(_ISOLATED, "no.env")
