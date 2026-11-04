"""Git provider credentials of a user, stored in AWS Secrets Manager.

One secret per (Cognito user, provider):
    name:  <GIT_CREDENTIALS_SECRET_PREFIX>/<cognito sub>/<provider>   (default prefix: git-credentials)
    value: {"provider": "github", "base_url": "https://api.github.com",
            "token": "...", "username": "octocat", "updated_at": "2025-01-01T00:00:00+00:00"}

The name is always built from the `sub` of the caller's own request, so a user can
only reach their own secrets. IAM: secretsmanager:CreateSecret + PutSecretValue (save)
and secretsmanager:GetSecretValue (load) on arn:aws:secretsmanager:*:*:secret:<prefix>/*.
"""

import json
import logging
import os
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

# botocore DEBUG logs print whole request/response bodies, i.e. the token
logging.getLogger("botocore").setLevel(logging.INFO)


class CredentialsNotFoundError(Exception):
    """The user has no credentials saved for the provider."""


class GitCredentialsRepository:
    def __init__(self, prefix=None, client=None):
        self.prefix = (
            prefix
            or os.environ.get("GIT_CREDENTIALS_SECRET_PREFIX")
            or "git-credentials"
        ).strip("/")
        self.client = client or boto3.client("secretsmanager")

    def secret_name(self, user_sub, provider):
        return f"{self.prefix}/{user_sub}/{provider}"

    def save(self, user_sub, provider, base_url, token, username=None):
        """Create or replace the secret. Returns True when it was created."""
        name = self.secret_name(user_sub, provider)
        value = {
            "provider": provider,
            "base_url": base_url,
            "token": token,
            "username": username,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        secret_string = json.dumps({k: v for k, v in value.items() if v is not None})
        try:
            self.client.create_secret(
                Name=name,
                SecretString=secret_string,
                Tags=[
                    {"Key": "cognito_sub", "Value": user_sub},
                    {"Key": "git_provider", "Value": provider},
                ],
            )
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceExistsException":
                raise
        self.client.put_secret_value(SecretId=name, SecretString=secret_string)
        return False

    def load(self, user_sub, provider):
        """The saved credentials as a dict; raises CredentialsNotFoundError."""
        try:
            response = self.client.get_secret_value(
                SecretId=self.secret_name(user_sub, provider)
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                raise CredentialsNotFoundError(
                    f"No {provider} credentials saved for this user"
                ) from None
            raise
        try:
            return json.loads(response["SecretString"])
        except ValueError:
            # not the caller's fault: must not surface as a 400 "validation" error
            raise RuntimeError(f"Secret for provider {provider} is malformed") from None
