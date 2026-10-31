import json
from datetime import date
from unittest.mock import Mock

import httpx
import pytest
from groq import BadRequestError
from langchain_core.exceptions import OutputParserException
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from lambda_create.ai import machine


def bad_request(message):
    request = httpx.Request("POST", "https://api.groq.com")
    response = httpx.Response(400, request=request)
    return BadRequestError(message, response=response, body=None)


def test_invoke_with_retry_retries_json_validate_failed():
    chain = Mock()
    chain.invoke.side_effect = [bad_request("json_validate_failed"), "ok"]
    assert machine._invoke_with_retry(chain, {}) == "ok"
    assert chain.invoke.call_count == 2


def test_invoke_with_retry_does_not_retry_other_bad_requests():
    chain = Mock()
    chain.invoke.side_effect = bad_request("invalid api key")
    with pytest.raises(BadRequestError):
        machine._invoke_with_retry(chain, {})
    chain.invoke.assert_called_once()


def test_invoke_with_retry_gives_up_after_max_attempts():
    chain = Mock()
    chain.invoke.side_effect = OutputParserException("bad json")
    with pytest.raises(OutputParserException):
        machine._invoke_with_retry(chain, {})
    assert chain.invoke.call_count == machine.MAX_ATTEMPTS


def test_invoke_with_retry_propagates_unrelated_errors():
    chain = Mock()
    chain.invoke.side_effect = KeyError("boom")
    with pytest.raises(KeyError):
        machine._invoke_with_retry(chain, {})
    chain.invoke.assert_called_once()


def test_invoke_with_retry_backoff_grows_between_attempts(monkeypatch):
    waits = []
    monkeypatch.setattr(machine.time, "sleep", waits.append)
    chain = Mock()
    chain.invoke.side_effect = [
        OutputParserException("bad"),
        OutputParserException("bad"),
        "ok",
    ]

    assert machine._invoke_with_retry(chain, {}) == "ok"
    assert waits == [2, 4]  # 2 * attempt


def test_load_text_model_forces_json_response(monkeypatch):
    chat_groq = Mock(return_value="model")
    monkeypatch.setattr(machine, "ChatGroq", chat_groq)
    monkeypatch.setenv("GROQ_API_KEY", "test-key")

    assert machine.load_text_model() == "model"
    kwargs = chat_groq.call_args.kwargs
    assert kwargs["api_key"] == "test-key"
    assert kwargs["model"] == machine.GROQ_MODEL
    assert kwargs["model_kwargs"] == {"response_format": {"type": "json_object"}}


def test_load_text_model_requires_api_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        machine.load_text_model()


VALID = {
    "analysis_date": "1999-01-01",
    "mermaid_diagram": "graph TD; A-->B",
    "aws_services": [{"service": "AWS Lambda", "resource_name": "create_item"}],
    "generated_code": {
        "terraform": {"main.tf": "", "variables.tf": "", "outputs.tf": ""},
        "python": {"create_item.py": "def handler(e, c): pass"},
    },
}


def test_generate_architecture_script_parses_and_normalizes_date():
    seen = []

    def fake_llm(prompt_value):
        seen.append(prompt_value.to_string())
        return AIMessage(content=json.dumps(VALID))

    out = machine.generate_architecture_script(
        RunnableLambda(fake_llm), "todo API", "RAG context"
    )

    assert out["analysis_date"] == date.today().isoformat()  # sobrescreve 1999
    assert "create_item.py" in out["generated_code"]["python"]
    assert "todo API" in seen[0] and "RAG context" in seen[0]


def test_generate_architecture_script_retries_invalid_json():
    replies = iter(["not json", json.dumps(VALID)])
    llm = RunnableLambda(lambda _: AIMessage(content=next(replies)))
    out = machine.generate_architecture_script(llm, "todo API", "")
    assert out["aws_services"][0]["resource_name"] == "create_item"


def test_generate_architecture_script_sends_rules_as_system_message():
    seen = []

    def fake_llm(prompt_value):
        seen.append(prompt_value.to_messages())
        return AIMessage(content=json.dumps(VALID))

    machine.generate_architecture_script(
        RunnableLambda(fake_llm), "todo API", "RAG context"
    )

    system, user = seen[0]
    assert system.type == "system" and system.content == machine.SYSTEM_RULES
    assert user.type == "human"
    assert "[CONTEXTO RAG]:\nRAG context" in user.content
    assert f"analysis_date = {date.today().isoformat()}" in user.content
    assert (
        "{format_instructions}" not in user.content
    )  # placeholder was actually filled
