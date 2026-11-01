from unittest.mock import Mock

import pytest

import service_ai


@pytest.fixture
def index_path(monkeypatch, tmp_path):
    path = tmp_path / "rag_index.json"
    monkeypatch.setattr(service_ai.config, "RAG_INDEX_PATH", path)
    return path


def test_get_ai_state_loads_services_once(monkeypatch, index_path):
    index_path.write_text("{}")
    monkeypatch.setattr(service_ai, "ai_state", {})
    rag_engine = Mock(return_value="rag")
    load_text_model = Mock(return_value="llm")
    monkeypatch.setattr(service_ai, "RAGEngine", rag_engine)
    monkeypatch.setattr(service_ai, "load_text_model", load_text_model)

    assert service_ai.get_ai_state() == {"rag": "rag", "llm": "llm"}
    assert (
        service_ai.get_ai_state() is service_ai.ai_state
    )  # warm invocation reuses the cache
    rag_engine.assert_called_once_with(index_path)
    load_text_model.assert_called_once()


def test_get_ai_state_only_loads_missing_services(monkeypatch, index_path):
    index_path.write_text("{}")
    monkeypatch.setattr(service_ai, "ai_state", {"llm": "llm"})
    rag_engine = Mock(return_value="rag")
    monkeypatch.setattr(service_ai, "RAGEngine", rag_engine)
    monkeypatch.setattr(service_ai, "load_text_model", Mock(side_effect=AssertionError))

    assert service_ai.get_ai_state() == {"rag": "rag", "llm": "llm"}
    rag_engine.assert_called_once_with(index_path)


def test_ensure_rag_index_skips_download_when_file_exists(monkeypatch, index_path):
    index_path.write_text("{}")
    monkeypatch.setattr(service_ai.boto3, "client", Mock(side_effect=AssertionError))

    assert service_ai.ensure_rag_index() == index_path


def test_ensure_rag_index_downloads_from_s3(monkeypatch, index_path):
    monkeypatch.setattr(service_ai.config, "RAG_S3_BUCKET", "my-bucket")
    monkeypatch.setattr(service_ai.config, "RAG_S3_KEY", "rag_index.json")
    s3 = Mock()
    monkeypatch.setattr(service_ai.boto3, "client", Mock(return_value=s3))

    assert service_ai.ensure_rag_index() == index_path
    s3.download_file.assert_called_once_with(
        "my-bucket", "rag_index.json", str(index_path)
    )


def test_ensure_rag_index_fails_without_bucket(monkeypatch, index_path):
    monkeypatch.setattr(service_ai.config, "RAG_S3_BUCKET", None)

    with pytest.raises(RuntimeError, match="RAG_S3_BUCKET is not set"):
        service_ai.ensure_rag_index()


def test_ensure_rag_index_wraps_download_errors(monkeypatch, index_path):
    monkeypatch.setattr(service_ai.config, "RAG_S3_BUCKET", "my-bucket")
    s3 = Mock()
    s3.download_file.side_effect = Exception("NoSuchKey")
    monkeypatch.setattr(service_ai.boto3, "client", Mock(return_value=s3))

    with pytest.raises(RuntimeError, match="s3://my-bucket/rag_index.json: NoSuchKey"):
        service_ai.ensure_rag_index()
