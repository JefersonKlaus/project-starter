"""Call the WebSocket API end to end: Cognito login -> connect -> prompt -> save the result.

    pip install boto3 websockets
    python backend-ia/scripts/call_api.py <user> <pass> <cognito_client_id> <ws_api> [--stage dev]

<cognito_client_id> is the Terraform output cognito_app_client_id and <ws_api> is either
the API id (abc123 -> wss://abc123.execute-api.us-east-2.amazonaws.com/<stage>) or the
full wss:// URL (Terraform output ws_api_url). The user must exist in the Cognito user
pool (see backend-ia/lambdas/README.md, "WebSocket API"). The architecture is saved to
resultado_arquitetura.json.
"""

import argparse
import json
import sys
import uuid

import boto3
from websockets.sync.client import connect

REGION = "us-east-2"
DEFAULT_STAGE = "dev"

PROMPT = (
    "To-do list application. The user can create a task, list all tasks, "
    "retrieve a task by ID, update a task, and remove a task."
)
OUTPUT_FILE = "resultado_arquitetura.json"
RESULT_TIMEOUT_SECONDS = 330  # lambda_create may take up to 300s


def websocket_url(ws_api, stage):
    """Accept the API id or a full wss:// URL."""
    if ws_api.startswith(("wss://", "ws://")):
        return ws_api
    return f"wss://{ws_api}.execute-api.{REGION}.amazonaws.com/{stage}"


def login(user, password, client_id):
    """Authenticate against Cognito and return the access token."""
    cognito = boto3.client("cognito-idp", region_name=REGION)
    response = cognito.initiate_auth(
        ClientId=client_id,
        AuthFlow="USER_PASSWORD_AUTH",
        AuthParameters={"USERNAME": user, "PASSWORD": password},
    )
    return response["AuthenticationResult"]["AccessToken"]


def request_architecture(url, token, prompt):
    """Connect with the token, send the prompt and wait for the architecture."""
    request_id = uuid.uuid4().hex
    headers = {"Authorization": f"Bearer {token}"}
    chunks = {}  # index -> data, for results bigger than one message

    with connect(url, additional_headers=headers) as ws:
        print("Connected. Sending the prompt...")
        ws.send(
            json.dumps({"action": "prompt", "prompt": prompt, "request_id": request_id})
        )

        while True:
            message = json.loads(ws.recv(timeout=RESULT_TIMEOUT_SECONDS))
            if message.get("request_id") not in (request_id, None):
                continue  # answer to another request on the same connection

            match message["type"]:
                case "accepted":
                    print("Accepted: the generation started, waiting for the result...")
                case "error":
                    raise RuntimeError(f"API error: {message['detail']}")
                case "result":
                    return message["result"]
                case "result_chunk":
                    chunks[message["index"]] = message["data"]
                    print(f"Received chunk {message['index'] + 1}/{message['total']}")
                    if len(chunks) == message["total"]:
                        return json.loads(
                            "".join(chunks[i] for i in range(message["total"]))
                        )
                case other:
                    print(f"Ignoring unknown message type {other!r}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate an architecture through the WebSocket API"
    )
    parser.add_argument("user", help="Cognito username (e-mail)")
    parser.add_argument("password", metavar="pass", help="Cognito password")
    parser.add_argument(
        "cognito_client_id", help="Cognito app client id (output cognito_app_client_id)"
    )
    parser.add_argument(
        "ws_api",
        help="WebSocket API id (e.g. abc123) or full wss:// URL (output ws_api_url)",
    )
    parser.add_argument(
        "--stage",
        default=DEFAULT_STAGE,
        help=f"stage of the API id (default {DEFAULT_STAGE})",
    )
    args = parser.parse_args()

    try:
        print("Logging in to Cognito...")
        token = login(args.user, args.password, args.cognito_client_id)

        url = websocket_url(args.ws_api, args.stage)
        print(f"Sending request to {url}...")
        architecture = request_architecture(url, token, PROMPT)

        with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
            json.dump(architecture, file, indent=2, ensure_ascii=False)
        print(
            f"Success! The architecture response was saved to the file: {OUTPUT_FILE}"
        )

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
