import pytest
from pydantic import ValidationError

from models import AWSArchitecture, GeneratedCode, RequestPayload


def test_request_payload_accepts_prompt():
    payload = RequestPayload(prompt="Create a CRUD API")

    assert payload.prompt == "Create a CRUD API"


def test_request_payload_rejects_missing_prompt():
    with pytest.raises(ValidationError):
        RequestPayload()


def test_aws_architecture_accepts_nested_generated_code():
    architecture = AWSArchitecture(
        analysis_date="2026-10-28",
        mermaid_diagram="graph TD; A --> B",
        aws_services=[{"service": "AWS Lambda", "resource_name": "create_item"}],
        generated_code=GeneratedCode(
            terraform={"main.tf": "resource {}", "variables.tf": ""},
            python={"create_item.py": "def handler(): pass"},
        ),
    )

    assert architecture.aws_services[0].service == "AWS Lambda"
    assert architecture.generated_code.terraform["main.tf"] == "resource {}"


def test_aws_architecture_rejects_invalid_service_shape():
    with pytest.raises(ValidationError):
        AWSArchitecture(
            analysis_date="2026-10-28",
            mermaid_diagram="graph TD; A --> B",
            aws_services=[{"service": "AWS Lambda"}],
            generated_code={"terraform": {}, "python": {}},
        )
