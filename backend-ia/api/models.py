from pydantic import BaseModel, Field
from typing import List, Dict


class PayloadRequisicao(BaseModel):
    prompt: str


class AWSService(BaseModel):
    service: str = Field(
        description="Nome do serviço AWS (ex: AWS Lambda, Amazon API Gateway)"
    )
    resource_name: str = Field(description="Nome do recurso na arquitetura")


class GeneratedCode(BaseModel):
    terraform: Dict[str, str] = Field(
        description="Dicionário onde as chaves são 'main.tf' e 'variables.tf', e os valores são os scripts HCL completos gerados linha por linha."
    )
    python: Dict[str, str] = Field(
        description="Dicionário onde as chaves são os nomes dos arquivos (ex: 'create_item.py', 'requirements.txt') e os valores são os scripts Python completos."
    )


class ArquiteturaAWS(BaseModel):
    analysis_date: str = Field(description="Data da análise no formato YYYY-MM-DD")
    mermaid_diagram: str = Field(
        description="O código completo do diagrama mermaid refletindo o fluxo de microsserviços"
    )
    aws_services: List[AWSService] = Field(
        description="Lista de serviços AWS utilizados nesta arquitetura"
    )
    generated_code: GeneratedCode = Field(
        description="Todos os códigos de infraestrutura e aplicação gerados"
    )
