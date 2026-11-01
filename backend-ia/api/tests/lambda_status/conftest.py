import importlib.util
from pathlib import Path

import httpx
import pytest
from botocore.exceptions import ClientError
from groq import APIConnectionError, AuthenticationError

# Both Lambdas ship a flat main.py. The lambda_create tests import theirs as the
# top-level module `main`, so this one is loaded under a distinct module name.
LAMBDA_STATUS_MAIN = Path(__file__).resolve().parents[2] / "lambda_status" / "main.py"


def _load_status_module():
    spec = importlib.util.spec_from_file_location(
        "lambda_status_main", LAMBDA_STATUS_MAIN
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def status():
    """The lambda_status handler module (main.py)."""
    return _load_status_module()


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Tests start without any of the variables the checks read, whatever the shell has."""
    for name in ("GROQ_API_KEY", "RAG_S3_BUCKET", "RAG_S3_KEY"):
        monkeypatch.delenv(name, raising=False)


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
    monkeypatch.setattr(status.boto3, "client", lambda service, **_: client)
    return client


@pytest.fixture
def fake_groq(status, monkeypatch):
    """Replace the Groq client class with a stub; the test decides what `create` raises."""

    class FakeCompletions:
        def __init__(self, state):
            self.state = state

        def create(self, **kwargs):
            self.state.calls.append(kwargs)
            if self.state.exception:
                raise self.state.exception
            return {"choices": [{"message": {"content": "Hello!"}}]}

    class State:
        def __init__(self):
            self.calls = []
            self.exception = None
            self.init_kwargs = None

    state = State()

    class FakeGroq:
        def __init__(self, **kwargs):
            state.init_kwargs = kwargs
            self.chat = type("Chat", (), {"completions": FakeCompletions(state)})()

    monkeypatch.setattr(status, "Groq", FakeGroq)
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
