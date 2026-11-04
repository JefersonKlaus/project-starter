import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from botocore.exceptions import ClientError
from groq import APIConnectionError, AuthenticationError

LAMBDA_STATUS_DIR = Path(__file__).resolve().parents[2] / "lambda_status"

# Top-level names of the flat lambda_status package (sub-modules such as
# checks.rag_index are matched by their first component).
TOP_LEVEL_MODULES = (
    "main",
    "orchestrator",
    "config",
    "models",
    "response",
    "service_health",
    "checks",
)


def _pop_lambda_modules():
    """Remove (and return) every sys.modules entry that belongs to one of the Lambdas."""
    popped = {}
    for name in list(sys.modules):
        if name.split(".")[0] in TOP_LEVEL_MODULES:
            popped[name] = sys.modules.pop(name)
    return popped


@pytest.fixture(scope="session")
def _status_modules():
    """Import the lambda_status modules once, without disturbing lambda_create's."""
    others = _pop_lambda_modules()
    sys.path.insert(0, str(LAMBDA_STATUS_DIR))
    try:
        importlib.import_module("main")  # pulls in the whole import chain
        modules = _pop_lambda_modules()
    finally:
        sys.path.remove(str(LAMBDA_STATUS_DIR))
        sys.modules.update(others)
    return modules


@pytest.fixture(autouse=True)
def status(_status_modules):
    """Namespace with the lambda_status modules, made active in sys.modules for the test."""
    others = _pop_lambda_modules()
    sys.modules.update(_status_modules)
    sys.path.insert(0, str(LAMBDA_STATUS_DIR))  # keeps importlib.reload on our files
    try:
        yield SimpleNamespace(
            **{name: mod for name, mod in _status_modules.items() if "." not in name}
        )
    finally:
        sys.path.remove(str(LAMBDA_STATUS_DIR))
        _pop_lambda_modules()
        sys.modules.update(others)


# --- External dependencies (never called for real) -------------------------


@pytest.fixture
def fake_s3(status, monkeypatch):
    """Replace boto3.client("s3") with a stub whose head_object behaviour the test controls."""

    class FakeS3:
        def __init__(self):
            self.calls = []
            self.exception = None

        def head_object(self, **kwargs):
            self.calls.append(kwargs)
            if self.exception:
                raise self.exception
            return {"ContentLength": 1}

    client = FakeS3()
    monkeypatch.setattr(
        status.checks.rag_index.boto3, "client", lambda *_, **__: client
    )
    return client


@pytest.fixture
def fake_groq(status, monkeypatch):
    """Replace the Groq client class with a stub; the test decides what `create` raises."""

    class State:
        def __init__(self):
            self.calls = []
            self.exception = None
            self.init_kwargs = None

    state = State()

    class FakeCompletions:
        def create(self, **kwargs):
            state.calls.append(kwargs)
            if state.exception:
                raise state.exception
            return {"choices": [{"message": {"content": "Hello!"}}]}

    class FakeGroq:
        def __init__(self, **kwargs):
            state.init_kwargs = kwargs
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr(status.checks.groq_hello, "Groq", FakeGroq)
    return state


@pytest.fixture
def s3_error():
    """Build a botocore ClientError with the given error code, as HeadObject raises it."""

    def _s3_error(code, message="boom"):
        return ClientError({"Error": {"Code": code, "Message": message}}, "HeadObject")

    return _s3_error


@pytest.fixture
def groq_auth_error():
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(401, request=request)
    return AuthenticationError("Invalid API Key", response=response, body=None)


@pytest.fixture
def groq_connection_error():
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    return APIConnectionError(request=request)
