from typing import Dict, List

from pydantic import BaseModel, Field


class AWSService(BaseModel):
    service: str = Field(
        description="AWS service name (e.g., AWS Lambda, Amazon API Gateway)"
    )
    resource_name: str = Field(description="Resource name in the architecture")


class GeneratedCode(BaseModel):
    terraform: Dict[str, str] = Field(
        description="Dictionary with 'main.tf', 'variables.tf' and 'outputs.tf' as keys (paths relative to the Terraform folder given in [ESTRUTURA DO PROJETO]) and complete generated HCL scripts as values."
    )
    python: Dict[str, str] = Field(
        description="Dictionary with paths relative to the Lambda code folder given in [ESTRUTURA DO PROJETO] (e.g., 'create_item.py' or 'create_item/handler.py', plus 'requirements.txt') as keys and complete Python scripts as values. Each Lambda file is the one packaged by its archive_file and named by its handler in the Terraform."
    )


class AWSArchitecture(BaseModel):
    analysis_date: str = Field(description="Analysis date in YYYY-MM-DD format")
    mermaid_diagram: str = Field(
        description="Complete Mermaid diagram code reflecting the microservices flow"
    )
    aws_services: List[AWSService] = Field(
        description="List of AWS services used in this architecture"
    )
    generated_code: GeneratedCode = Field(
        description="All generated infrastructure and application code"
    )
