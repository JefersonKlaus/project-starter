import os

from dotenv import load_dotenv

load_dotenv()

# How $connect validates the token presented by the client (see service_auth.VALIDATORS):
#   cognito       - the token must be a valid JWT of the Cognito user pool below (deployed default)
#   shared_secret - the token must equal WS_AUTH_TOKEN
#   none          - no authentication: every connection is accepted
WS_AUTH_MODE = os.environ.get("WS_AUTH_MODE", "none").strip().lower()

# Cognito user pool (e.g. us-east-2_AbCdEfGhI; the region is its prefix) and the app
# client that issued the tokens, both created by Terraform (infra/modules/cognito)
COGNITO_USER_POOL_ID = os.environ.get("COGNITO_USER_POOL_ID") or None
COGNITO_APP_CLIENT_ID = os.environ.get("COGNITO_APP_CLIENT_ID") or None

# Secret clients must present when WS_AUTH_MODE=shared_secret (never logged nor echoed)
WS_AUTH_TOKEN = os.environ.get("WS_AUTH_TOKEN") or None
