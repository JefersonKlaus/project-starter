"""git_credentials_save: POST that stores the Git provider credentials of the Cognito user
in AWS Secrets Manager (mocked with moto; nothing reaches AWS)."""

import base64
import importlib
import json
import logging
import sys
from pathlib import Path

import pytest

pytest.importorskip("pydantic")
moto = pytest.importorskip("moto")
import boto3  # noqa: E402
from botocore.exceptions import ClientError  # noqa: E402
from botocore.stub import ANY, Stubber  # noqa: E402

LAMBDA_DIR = (
    Path(__file__).resolve().parents[1] / "rest_api" / "post" / "git_credentials"
)
# The Lambda uses bare imports (as in the Lambda runtime): the same names exist in other
# Lambdas, so every test imports a fresh copy of this one
LAMBDA_MODULES = [p.stem for p in LAMBDA_DIR.glob("*.py")]

SUB = "6f1c2d3e-4b5a-4c7d-8e9f-0a1b2c3d4e5f"
OTHER_SUB = "11111111-2222-4333-8444-555555555555"
TOKEN = "ghp_SuperSecretToken1234567890abcdef"


def _forget_lambda_modules():
    for name in LAMBDA_MODULES:
        sys.modules.pop(name, None)
        sys.modules.pop(f"rest_api.post.git_credentials.{name}", None)


@pytest.fixture
def aws(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    with moto.mock_aws():
        yield boto3.client("secretsmanager", region_name="us-east-1")


@pytest.fixture
def load_lambda(monkeypatch, aws):
    """load_lambda(**env) -> the Lambda's `main` module, imported with that environment."""
    monkeypatch.chdir(
        LAMBDA_DIR
    )  # keep load_dotenv() away from a developer's real .env
    for name in ("CORS_ORIGINS", "SECRET_NAME_PREFIX", "KMS_KEY_ID"):
        monkeypatch.delenv(name, raising=False)

    def load(**env):
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        _forget_lambda_modules()
        monkeypatch.syspath_prepend(str(LAMBDA_DIR))
        monkeypatch.syspath_prepend(
            str(LAMBDA_DIR.parents[3] / "layers" / "common" / "python")
        )
        return importlib.import_module("handler")

    yield load
    _forget_lambda_modules()


@pytest.fixture
def handler(load_lambda):
    return load_lambda().lambda_handler


def rest_event(body, sub=SUB, headers=None, encode=True):
    """REST API + Cognito user pool authorizer."""
    event = {
        "httpMethod": "POST",
        "path": "/git-credentials",
        "headers": headers or {"Content-Type": "application/json"},
        "requestContext": {"authorizer": {"claims": {"sub": sub}} if sub else {}},
        "body": json.dumps(body) if encode else body,
        "isBase64Encoded": False,
    }
    return event


def http_event(body, sub=SUB):
    """HTTP API (payload 2.0) + JWT authorizer."""
    return {
        "version": "2.0",
        "routeKey": "POST /git-credentials",
        "headers": {"content-type": "application/json"},
        "requestContext": {
            "http": {"method": "POST"},
            "authorizer": {"jwt": {"claims": {"sub": sub}, "scopes": None}},
        },
        "body": json.dumps(body),
        "isBase64Encoded": False,
    }


def call(handler, event):
    response = handler(event, None)
    return response["statusCode"], json.loads(response["body"]), response


def stored(aws, name):
    return json.loads(aws.get_secret_value(SecretId=name)["SecretString"])


# ====================================================================== success


def test_creates_one_secret_per_user_and_provider(handler, aws):
    status, body, response = call(
        handler,
        rest_event({"provider": "github", "token": TOKEN, "username": "octocat"}),
    )

    assert status == 201
    assert body == {
        "provider": "github",
        "base_url": "https://api.github.com",
        "token_type": "personal_access_token",
        "username": "octocat",
        "has_refresh_token": False,
        "expires_at": None,
        "updated_at": body["updated_at"],
        "created": True,
    }
    assert TOKEN not in response["body"]
    assert response["headers"]["Cache-Control"] == "no-store"

    secret = stored(aws, f"git-credentials/{SUB}/github")
    assert secret["token"] == TOKEN
    assert secret["cognito_sub"] == SUB
    assert secret["provider"] == "github"
    assert secret["schema_version"] == 1
    assert "refresh_token" not in secret

    tags = {
        t["Key"]: t["Value"]
        for t in aws.describe_secret(SecretId=f"git-credentials/{SUB}/github")["Tags"]
    }
    assert tags == {
        "cognito_sub": SUB,
        "git_provider": "github",
        "managed_by": "git_credentials_save",
    }


def test_second_post_updates_the_same_secret(handler, aws):
    call(handler, rest_event({"provider": "github", "token": TOKEN}))
    status, body, _ = call(
        handler, rest_event({"provider": "github", "token": "ghp_NewToken999"})
    )

    assert status == 200
    assert body["created"] is False
    assert stored(aws, f"git-credentials/{SUB}/github")["token"] == "ghp_NewToken999"
    assert len(aws.list_secrets()["SecretList"]) == 1
    previous = aws.get_secret_value(
        SecretId=f"git-credentials/{SUB}/github", VersionStage="AWSPREVIOUS"
    )
    assert json.loads(previous["SecretString"])["token"] == TOKEN


def test_users_and_providers_are_kept_apart(handler, aws):
    call(handler, rest_event({"provider": "github", "token": "tok-a"}, sub=SUB))
    call(handler, rest_event({"provider": "gitlab", "token": "tok-b"}, sub=SUB))
    call(handler, rest_event({"provider": "github", "token": "tok-c"}, sub=OTHER_SUB))

    names = sorted(s["Name"] for s in aws.list_secrets()["SecretList"])
    assert names == [
        f"git-credentials/{OTHER_SUB}/github",
        f"git-credentials/{SUB}/github",
        f"git-credentials/{SUB}/gitlab",
    ]
    assert stored(aws, f"git-credentials/{SUB}/github")["token"] == "tok-a"
    assert stored(aws, f"git-credentials/{OTHER_SUB}/github")["token"] == "tok-c"


def test_http_api_jwt_authorizer_claims(handler, aws):
    status, _, _ = call(
        handler, http_event({"provider": "gitlab", "token": "glpat-abc"})
    )
    assert status == 201
    assert (
        stored(aws, f"git-credentials/{SUB}/gitlab")["base_url"]
        == "https://gitlab.com/api/v4"
    )


def test_other_provider_with_base_url_and_oauth_fields(handler, aws):
    status, body, response = call(
        handler,
        rest_event(
            {
                "provider": "Bitbucket",
                "token": "oauth-access",
                "token_type": "oauth",
                "refresh_token": "oauth-refresh",
                "expires_at": "2030-01-01T00:00:00Z",
                "base_url": "https://api.bitbucket.org/2.0/",
            }
        ),
    )
    assert status == 201
    assert body["provider"] == "bitbucket"
    assert body["base_url"] == "https://api.bitbucket.org/2.0"
    assert body["has_refresh_token"] is True
    assert "oauth-refresh" not in response["body"]
    secret = stored(aws, f"git-credentials/{SUB}/bitbucket")
    assert secret["refresh_token"] == "oauth-refresh"
    assert secret["token_type"] == "oauth"
    assert secret["expires_at"] == "2030-01-01T00:00:00+00:00"


def test_self_hosted_gitlab_overrides_the_default_url(handler, aws):
    call(
        handler,
        rest_event(
            {
                "provider": "gitlab",
                "token": "glpat-x",
                "base_url": "https://git.example.com/api/v4",
            }
        ),
    )
    assert (
        stored(aws, f"git-credentials/{SUB}/gitlab")["base_url"]
        == "https://git.example.com/api/v4"
    )


def test_base64_body(handler, aws):
    event = rest_event(
        base64.b64encode(
            json.dumps({"provider": "github", "token": TOKEN}).encode()
        ).decode(),
        encode=False,
    )
    event["isBase64Encoded"] = True
    assert call(handler, event)[0] == 201


def test_secret_name_prefix_and_kms_key_come_from_the_environment(load_lambda, aws):
    key_id = boto3.client("kms", region_name="us-east-1").create_key()["KeyMetadata"][
        "KeyId"
    ]
    handler = load_lambda(
        SECRET_NAME_PREFIX="/platform/git/", KMS_KEY_ID=key_id
    ).lambda_handler

    assert call(handler, rest_event({"provider": "github", "token": TOKEN}))[0] == 201
    description = aws.describe_secret(SecretId=f"platform/git/{SUB}/github")
    assert description["KmsKeyId"] == key_id


def test_cors_header_only_for_allowed_origins(load_lambda, aws):
    handler = load_lambda(CORS_ORIGINS="https://app.example.com").lambda_handler
    allowed = rest_event(
        {"provider": "github", "token": TOKEN},
        headers={"Origin": "https://app.example.com"},
    )
    other = rest_event(
        {"provider": "github", "token": TOKEN},
        headers={"Origin": "https://evil.example.com"},
    )
    assert (
        handler(allowed, None)["headers"]["Access-Control-Allow-Origin"]
        == "https://app.example.com"
    )
    assert "Access-Control-Allow-Origin" not in handler(other, None)["headers"]


# ============================================================ identity (Cognito)


@pytest.mark.parametrize(
    "request_context",
    [
        {},  # route without authorizer
        {"authorizer": {}},
        {"authorizer": {"claims": {}}},
        {"authorizer": {"claims": {"sub": "../other-user"}}},
        {"authorizer": {"jwt": {"claims": {"sub": ""}}}},
    ],
)
def test_without_an_authenticated_user_nothing_is_saved(handler, aws, request_context):
    event = rest_event({"provider": "github", "token": TOKEN})
    event["requestContext"] = request_context
    status, body, _ = call(handler, event)
    assert status == 401
    assert body == {"detail": "Authentication required"}
    assert aws.list_secrets()["SecretList"] == []


def test_authorization_header_alone_is_not_trusted(handler, aws):
    event = rest_event({"provider": "github", "token": TOKEN}, sub=None)
    event["headers"]["Authorization"] = (
        "Bearer eyJhbGciOiJub25lIn0.eyJzdWIiOiJhZG1pbiJ9."
    )
    assert call(handler, event)[0] == 401


def test_user_id_in_the_body_is_rejected(handler, aws):
    status, _, _ = call(
        handler,
        rest_event({"provider": "github", "token": TOKEN, "cognito_sub": OTHER_SUB}),
    )
    assert status == 422
    assert aws.list_secrets()["SecretList"] == []


# ==================================================================== validation


@pytest.mark.parametrize(
    "body",
    [
        {"token": TOKEN},  # no provider
        {"provider": "github"},  # no token
        {"provider": "github", "token": "   "},
        {"provider": "github", "token": f"{TOKEN} injected"},
        {"provider": "github", "token": f"{TOKEN}\r\nX-Evil: 1"},
        {"provider": "github", "token": "x" * 4097},
        {"provider": "git hub", "token": TOKEN},
        {"provider": "../admin", "token": TOKEN},
        {"provider": "bitbucket", "token": TOKEN},  # unknown provider needs base_url
        {"provider": "github", "token": TOKEN, "token_type": "password"},
        {
            "provider": "github",
            "token": TOKEN,
            "expires_at": "2030-01-01T00:00:00",
        },  # no timezone
    ],
)
def test_invalid_body_is_422_and_never_echoes_secrets(handler, aws, body):
    status, detail, response = call(handler, rest_event(body))
    assert status == 422
    assert TOKEN not in response["body"]
    assert isinstance(detail["detail"], list)
    assert aws.list_secrets()["SecretList"] == []


@pytest.mark.parametrize(
    "base_url",
    [
        "http://git.example.com/api",  # not https
        "https://user:pass@git.example.com/api",
        "https://git.example.com/api?x=1",
        "https://localhost/api",
        "https://127.0.0.1/api",
        "https://10.0.0.5/api",
        "https://169.254.169.254/latest/meta-data",
        "https://[::1]/api",
        "ftp://git.example.com",
        "not a url",
    ],
)
def test_unsafe_base_url_is_rejected(handler, aws, base_url):
    status, _, _ = call(
        handler, rest_event({"provider": "gitea", "token": TOKEN, "base_url": base_url})
    )
    assert status == 422


def test_invalid_json_is_400(handler, aws):
    status, body, _ = call(handler, rest_event("{not json", encode=False))
    assert status == 400
    assert body == {"detail": "Invalid JSON body"}


# ====================================================================== failures


def _stub(load_lambda):
    main = load_lambda()
    import service_secrets

    client = boto3.client("secretsmanager", region_name="us-east-1")
    service_secrets.clients["secretsmanager"] = client
    return main.lambda_handler, Stubber(client)


def test_secret_scheduled_for_deletion_is_restored_on_create(load_lambda):
    handler, stub = _stub(load_lambda)
    name = f"git-credentials/{SUB}/github"
    stub.add_client_error(
        "create_secret",
        "InvalidRequestException",
        "You can't create this secret because a secret with this name is already scheduled for deletion.",
    )
    stub.add_response("restore_secret", {"Name": name}, {"SecretId": name})
    stub.add_response(
        "put_secret_value", {"Name": name}, {"SecretId": name, "SecretString": ANY}
    )
    with stub:
        status, body, _ = call(
            handler, rest_event({"provider": "github", "token": TOKEN})
        )
    stub.assert_no_pending_responses()
    assert (status, body["created"]) == (201, True)


def test_secret_marked_for_deletion_is_restored_on_update(load_lambda):
    handler, stub = _stub(load_lambda)
    name = f"git-credentials/{SUB}/github"
    stub.add_client_error("create_secret", "ResourceExistsException", "already exists")
    stub.add_client_error(
        "put_secret_value",
        "InvalidRequestException",
        "You can't perform this operation on the secret because it was marked for deletion.",
    )
    stub.add_response("restore_secret", {"Name": name}, {"SecretId": name})
    stub.add_response(
        "put_secret_value", {"Name": name}, {"SecretId": name, "SecretString": ANY}
    )
    with stub:
        status, _, _ = call(handler, rest_event({"provider": "github", "token": TOKEN}))
    stub.assert_no_pending_responses()
    assert status == 201


def test_aws_failure_is_a_generic_500_without_secrets_in_response_or_logs(
    load_lambda, caplog
):
    handler, stub = _stub(load_lambda)
    stub.add_client_error(
        "create_secret",
        "AccessDeniedException",
        "User is not authorized to perform CreateSecret",
    )
    with caplog.at_level(logging.DEBUG), stub:
        status, body, response = call(
            handler, rest_event({"provider": "github", "token": TOKEN})
        )
    assert status == 500
    assert body == {"detail": "Could not save the credentials"}
    assert "AccessDenied" not in response["body"]
    assert "Failed to save the git credentials" in caplog.text
    assert TOKEN not in caplog.text


def test_token_is_not_logged_on_success(handler, aws, caplog):
    with caplog.at_level(logging.DEBUG):
        call(
            handler,
            rest_event(
                {"provider": "github", "token": TOKEN, "refresh_token": "refresh-xyz"}
            ),
        )
    assert "Git credentials created" in caplog.text
    assert TOKEN not in caplog.text
    assert "refresh-xyz" not in caplog.text


def test_unhandled_aws_errors_are_500(load_lambda):
    handler, stub = _stub(load_lambda)
    stub.add_client_error("create_secret", "ThrottlingException", "Rate exceeded")
    with stub:
        assert (
            call(handler, rest_event({"provider": "github", "token": TOKEN}))[0] == 500
        )


def test_upsert_reraises_errors_it_does_not_handle(load_lambda):
    _, stub = _stub(load_lambda)
    import service_secrets

    stub.add_client_error("create_secret", "InternalServiceError", "boom")
    with stub, pytest.raises(ClientError):
        service_secrets.upsert_secret("name", "value", "description", {})
