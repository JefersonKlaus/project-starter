from unittest.mock import Mock

from lambda_create import service_ai


def test_get_ai_state_loads_services_once(monkeypatch):
    monkeypatch.setattr(service_ai, "ai_state", {})
    rag_engine = Mock(return_value="rag")
    load_text_model = Mock(return_value="llm")
    monkeypatch.setattr(service_ai, "RAGEngine", rag_engine)
    monkeypatch.setattr(service_ai, "load_text_model", load_text_model)

    assert service_ai.get_ai_state() == {"rag": "rag", "llm": "llm"}
    assert (
        service_ai.get_ai_state() is service_ai.ai_state
    )  # warm invocation reuses the cache
    rag_engine.assert_called_once()
    load_text_model.assert_called_once()


def test_get_ai_state_only_loads_missing_services(monkeypatch):
    monkeypatch.setattr(service_ai, "ai_state", {"llm": "llm"})
    rag_engine = Mock(return_value="rag")
    monkeypatch.setattr(service_ai, "RAGEngine", rag_engine)
    monkeypatch.setattr(service_ai, "load_text_model", Mock(side_effect=AssertionError))

    assert service_ai.get_ai_state() == {"rag": "rag", "llm": "llm"}
    rag_engine.assert_called_once()
