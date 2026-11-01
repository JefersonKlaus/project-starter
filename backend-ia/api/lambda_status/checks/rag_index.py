"""Check: the RAG index object exists in S3 (HeadObject, nothing is downloaded)."""

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from models import CheckResult

NOT_FOUND_CODES = ("404", "NoSuchKey", "NotFound")
FORBIDDEN_CODES = ("403", "AccessDenied", "Forbidden")


def check(bucket, key) -> CheckResult:
    if not bucket:
        return CheckResult.error("RAG_S3_BUCKET is not set")

    uri = f"s3://{bucket}/{key}"
    try:
        boto3.client("s3").head_object(Bucket=bucket, Key=key)
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in NOT_FOUND_CODES:
            return CheckResult.error(f"{uri} not found")
        if code in FORBIDDEN_CODES:
            return CheckResult.error(f"access denied to {uri}")
        return CheckResult.error(f"could not read {uri}: {code or e}")
    except BotoCoreError as e:
        return CheckResult.error(f"could not read {uri}: {e}")
    return CheckResult.ok(f"{uri} is available")
