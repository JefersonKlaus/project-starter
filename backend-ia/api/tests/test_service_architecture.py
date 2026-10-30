from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from lambda_create import service_architecture
from lambda_create.service_architecture import create_architecture


def _ready(monkeypatch, result, documents=()):
    rag = Mock()
    rag.find_references.return_value = ("ctx", list(documents))
    monkeypatch.setattr(
        service_architecture, "get_ai_state", lambda: {"rag": rag, "llm": "llm"}
    )
    generate = Mock(return_value=result)
    monkeypatch.setattr(service_architecture, "generate_architecture_script", generate)
    return rag, generate


def test_create_architecture_adds_rag_references(monkeypatch):
    rag, generate = _ready(
        monkeypatch,
        {"generated_code": {}},
        [SimpleNamespace(metadata={"source": "a.py"}), SimpleNamespace(metadata={})],
    )

    response = create_architecture("x")

    assert response == {"generated_code": {}, "rag_references": ["a.py", "unknown"]}
    rag.find_references.assert_called_once_with("x")
    generate.assert_called_once_with(llm="llm", prompt_text="x", rag_context="ctx")


def test_create_architecture_unwraps_list_responses(monkeypatch):
    _ready(monkeypatch, [{"generated_code": {}}])
    assert create_architecture("x") == {"generated_code": {}, "rag_references": []}


def test_create_architecture_rejects_non_dict_responses(monkeypatch):
    _ready(monkeypatch, "not a dict")
    with pytest.raises(ValueError, match="Unexpected JSON format"):
        create_architecture("x")


def test_create_architecture_propagates_generation_errors(monkeypatch):
    _, generate = _ready(monkeypatch, None)
    generate.side_effect = RuntimeError("boom")
    with pytest.raises(RuntimeError, match="boom"):
        create_architecture("x")
