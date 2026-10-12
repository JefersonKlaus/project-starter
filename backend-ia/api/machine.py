import os
from datetime import date

from models import ArquiteturaAWS

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser

# Business rules (system prompt, kept in Portuguese on purpose)
REGRAS_SISTEMA = """Você é um Arquiteto Cloud especialista em AWS Serverless e engenheiro Python sênior.
Você gera infraestrutura (Terraform HCL) e código (Python) prontos para rodar.

REGRAS CRÍTICAS (SOBREPÕEM QUALQUER CONTEXTO):

ARQUITETURA
1. UMA LAMBDA POR AÇÃO: é PROIBIDO criar Lambdas monolíticas. Deduza da DESCRIÇÃO DO PRODUTO cada ação que o usuário pode executar e crie uma Lambda para cada uma, com seu próprio arquivo Python (ex: get_item.py, create_item.py) e seu próprio `aws_lambda_function`. Listar todos e consultar por id são ações distintas. Se a descrição não deixar as ações claras, assuma um CRUD completo: create, list, get por id, update e delete. Não crie ações que a descrição não sugere.
2. SEM ROTEAMENTO INTERNO: nenhum arquivo Python pode conter `httpMethod` nem `if event[...]` para escolher a ação. O API Gateway já chama a Lambda certa.
3. CONTEXTO RAG: use o [CONTEXTO RAG] só como referência de lógica de negócio e uso do `boto3`. Se o contexto for monolítico, QUEBRE em várias Lambdas conforme a regra 1. Nunca copie caminhos, nomes de tabela ou ARNs do contexto.

TERRAFORM
4. Para CADA Lambda crie recursos dedicados: `aws_lambda_function`, `aws_iam_role`, `aws_iam_role_policy` (menor privilégio: só as ações e o ARN da tabela que essa Lambda usa) e `aws_lambda_permission`.
5. Crie também os recursos de infraestrutura que o pedido exige: `aws_dynamodb_table` (billing_mode = "PAY_PER_REQUEST"), `aws_api_gateway_rest_api` com resource, method, integration e deployment para cada rota, e `aws_cloudwatch_log_group` quando houver Lambda.
6. `aws_lambda_permission` usa `source_arn` com o ARN de execução do API Gateway (`${aws_api_gateway_rest_api.<nome>.execution_arn}/*/*`). NUNCA `source_arn = "*"`.
7. Use `runtime = "python3.12"`. Configure o `provider "aws"` com `region = var.region`. Todas as variáveis declaradas em `variables.tf` devem ser usadas. Passe o nome da tabela para a Lambda em `environment { variables = { TABLE_NAME = ... } }`.
8. Inclua `outputs.tf` com a URL da API. O `main.tf` NÃO pode conter blocos `output`;
   todos os outputs ficam só em `outputs.tf`. Chaves do dicionário terraform: `main.tf`, `variables.tf`, `outputs.tf`.

PYTHON
9. Leia configuração com `os.environ["TABLE_NAME"]`, NUNCA de `event["region"]` ou `event["table_name"]`. Crie o cliente boto3 fora do handler.
10. Retorne SEMPRE um dict no formato do API Gateway proxy:
   {"statusCode": 200, "headers": {"Content-Type": "application/json"}, "body": json.dumps(dados, default=str)}
   NUNCA escreva `return json.dumps(...)` direto no handler.
11. Trate erros: item inexistente retorna 404 (`response.get("Item")` vazio), entrada inválida retorna 400, `ClientError` retorna 500 com mensagem genérica. NUNCA devolva `e.response` ao cliente. Registre o erro com `logging`.
12. Nunca devolva o `response` bruto do DynamoDB (contém ResponseMetadata). Devolva só os dados.
13. Inclua `requirements.txt` só com o que realmente precisa (o `boto3` já existe no runtime da Lambda).

GERAÇÃO
14. Escreva todo o código HCL e Python completo, linha por linha, sem marcadores como "[CÓDIGO AQUI]" nem "...". Verifique vírgulas, parênteses e aspas.
15. O diagrama Mermaid deve mostrar exatamente as Lambdas e recursos que você gerou no Terraform, nem mais nem menos.
16. Responda SOMENTE com o JSON pedido, sem texto antes ou depois."""

# Model hosted on Groq (change here to try another one)
GROQ_MODEL = "openai/gpt-oss-120b"


def load_text_model():
    """Create the Groq client. The key comes from the GROQ_API_KEY variable (.env)."""
    if not os.environ.get("GROQ_API_KEY"):
        raise RuntimeError(
            "GROQ_API_KEY not found. Add GROQ_API_KEY=gsk_... to the .env file"
        )

    print(f"Connecting to Groq with model {GROQ_MODEL}...")
    return ChatGroq(
        model=GROQ_MODEL,
        temperature=0.1,
        max_tokens=12000,  # gpt-oss is a reasoning model: part of the tokens goes to its "thinking"
        max_retries=2,
        timeout=120,
        # Forces a valid JSON response (the prompt already mentions JSON via format_instructions)
        model_kwargs={"response_format": {"type": "json_object"}},
    )


def generate_architecture_script(llm, prompt_text, contexto_rag):
    print("\nGenerating architecture, Mermaid diagram and code...")

    # The Pydantic parser validates the JSON against the ArquiteturaAWS schema
    parser = PydanticOutputParser(pydantic_object=ArquiteturaAWS)

    # With a chat API the manual ChatML tags are no longer needed: Groq applies the model template
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "{regras}"),
            (
                "user",
                "[CONTEXTO RAG]:\n{contexto}\n\n"
                "[DESCRIÇÃO DO PRODUTO]:\n{produto}\n\n"
                "[TAREFA]:\n"
                "Projete a arquitetura AWS Serverless para este produto e gere o "
                "Terraform (HCL) e o código Python das Lambdas, seguindo as regras do sistema.\n"
                "Use analysis_date = {data_hoje}.\n\n"
                "{format_instructions}",
            ),
        ]
    ).partial(format_instructions=parser.get_format_instructions())

    chain = prompt | llm | parser

    result_pydantic = chain.invoke(
        {
            "regras": REGRAS_SISTEMA,
            "contexto": contexto_rag,
            "produto": prompt_text,
            "data_hoje": date.today().isoformat(),
        }
    )

    result = result_pydantic.model_dump()
    result["analysis_date"] = date.today().isoformat()  # guarantees the date even if the model gets it wrong
    return result