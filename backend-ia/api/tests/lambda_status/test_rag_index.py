import pytest
from botocore.exceptions import EndpointConnectionError


@pytest.fixture
def rag_index(status):
    return status.checks.rag_index


def test_requires_bucket(rag_index, fake_s3):
    result = rag_index.check(None, "rag_index.json")

    assert result.to_dict() == {"status": "error", "detail": "RAG_S3_BUCKET is not set"}
    assert fake_s3.calls == []  # S3 is not even contacted


def test_ok_when_object_exists(rag_index, fake_s3):
    result = rag_index.check("my-bucket", "indexes/rag.json")

    assert result.to_dict() == {
        "status": "ok",
        "detail": "s3://my-bucket/indexes/rag.json is available",
    }
    assert fake_s3.calls == [{"Bucket": "my-bucket", "Key": "indexes/rag.json"}]


@pytest.mark.parametrize("code", ["404", "NotFound", "NoSuchKey"])
def test_missing_object(rag_index, fake_s3, s3_error, code):
    fake_s3.exception = s3_error(code)

    result = rag_index.check("my-bucket", "rag_index.json")

    assert result.to_dict() == {
        "status": "error",
        "detail": "s3://my-bucket/rag_index.json not found",
    }


@pytest.mark.parametrize("code", ["403", "AccessDenied", "Forbidden"])
def test_access_denied(rag_index, fake_s3, s3_error, code):
    fake_s3.exception = s3_error(code)

    result = rag_index.check("my-bucket", "rag_index.json")

    assert result.to_dict() == {
        "status": "error",
        "detail": "access denied to s3://my-bucket/rag_index.json",
    }


def test_other_client_error(rag_index, fake_s3, s3_error):
    fake_s3.exception = s3_error("InternalError")

    result = rag_index.check("my-bucket", "rag_index.json")

    assert not result.passed
    assert (
        result.detail == "could not read s3://my-bucket/rag_index.json: InternalError"
    )


def test_connection_error(rag_index, fake_s3):
    fake_s3.exception = EndpointConnectionError(endpoint_url="https://s3.amazonaws.com")

    result = rag_index.check("my-bucket", "rag_index.json")

    assert not result.passed
    assert result.detail.startswith("could not read s3://my-bucket/rag_index.json: ")
    assert "https://s3.amazonaws.com" in result.detail
