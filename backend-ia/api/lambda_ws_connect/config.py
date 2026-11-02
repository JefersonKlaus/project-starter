import os

from dotenv import load_dotenv

load_dotenv()

# How $connect validates the token presented by the client (see service_auth.VALIDATORS):
#   none          - no authentication: every connection is accepted (current phase)
#   shared_secret - the token must equal WS_AUTH_TOKEN
WS_AUTH_MODE = os.environ.get("WS_AUTH_MODE", "none").strip().lower()

# Secret clients must present when WS_AUTH_MODE=shared_secret (never logged nor echoed)
WS_AUTH_TOKEN = os.environ.get("WS_AUTH_TOKEN") or None
