import os
import time
from datetime import date

from groq import BadRequestError
from langchain_core.exceptions import OutputParserException
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from .models import AWSArchitecture

# Business rules (system prompt, kept in Portuguese on purpose)
SYSTEM_RULES = """Você é um Arquiteto Cloud especialista em AWS Serverless e engenheiro Python sênior.
Você gera infraestrutura (Terraform HCL) e código (Python) prontos para rodar.

REGRAS CRÍTICAS (SOBREPÕEM QUALQUER CONTEXTO):

ARQUITETURA
1. UMA LAMBDA POR AÇÃO: é PROIBIDO criar Lambdas monolíticas. Deduza da DESCRIÇÃO DO PRODUTO cada ação que o usuário pode executar e crie uma Lambda para cada uma, com seu próprio arquivo Python (ex: get_item.py, create_item.py) e seu próprio `aws_lambda_function`. Listar todos e consultar por id são ações distintas. Se a descrição não deixar as ações claras, assuma um CRUD completo: create, list, get por id, update e delete. Não crie ações que a descrição não sugere.
2. SEM ROTEAMENTO INTERNO: nenhum arquivo Python pode conter `httpMethod` nem `if event[...]` para escolher a ação. O API Gateway já chama a Lambda certa.
3. CONTEXTO RAG: use o [CONTEXTO RAG] só como referência de lógica de negócio e uso do `boto3`. Se o contexto for monolítico, QUEBRE em várias Lambdas conforme a regra 1. Nunca copie caminhos, nomes de tabela ou ARNs do contexto.

TERRAFORM
4. Para CADA Lambda crie recursos dedicados: `aws_lambda_function`, `aws_iam_role`, `aws_iam_role_policy` (menor privilégio: só as ações e o ARN da tabela que essa Lambda usa), `aws_iam_role_policy_attachment` com a policy gerenciada `arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole` (para gravar logs) e `aws_lambda_permission`.
5. Crie também os recursos de infraestrutura que o pedido exige: `aws_dynamodb_table` (billing_mode = "PAY_PER_REQUEST"), `aws_api_gateway_rest_api` com resource, method e integration para cada rota, e um `aws_cloudwatch_log_group` (name = "/aws/lambda/<function_name>") para cada Lambda; a Lambda deve ter `depends_on` apontando para o seu log group.
6. DEPLOY DO API GATEWAY: o `aws_api_gateway_deployment` NUNCA tem `stage_name`. O stage é um `aws_api_gateway_stage` separado. Siga este padrão (substitua <...> pelos nomes reais):

   resource "aws_api_gateway_deployment" "api" {
     rest_api_id = aws_api_gateway_rest_api.<api>.id
     triggers = {
       redeployment = sha1(jsonencode([
         aws_api_gateway_integration.<integracao_1>.id,
         aws_api_gateway_integration.<integracao_2>.id
       ]))
     }
     lifecycle {
       create_before_destroy = true
     }
     depends_on = [aws_api_gateway_integration.<integracao_1>, aws_api_gateway_integration.<integracao_2>]
   }

   resource "aws_api_gateway_stage" "prod" {
     rest_api_id   = aws_api_gateway_rest_api.<api>.id
     deployment_id = aws_api_gateway_deployment.api.id
     stage_name    = "prod"
   }

   Liste TODAS as integrations no `triggers` e no `depends_on`.
7. EMPACOTAMENTO: `aws_lambda_function` NUNCA usa um `.py` em `filename`. Para cada Lambda use um `data "archive_file"` e referencie o zip:

   data "archive_file" "<acao>" {
     type        = "zip"
     source_file = "${path.module}/lambda/<arquivo>.py"
     output_path = "${path.module}/build/<acao>.zip"
   }
   (na função: filename = data.archive_file.<acao>.output_path e source_code_hash = data.archive_file.<acao>.output_base64sha256)

8. `aws_lambda_permission` usa `source_arn` com o ARN de execução do API Gateway (`${aws_api_gateway_rest_api.<nome>.execution_arn}/*/*`). NUNCA `source_arn = "*"`.
9. Use `runtime = "python3.12"`. Configure o `provider "aws"` com `region = var.region`. Todas as variáveis declaradas em `variables.tf` devem ser usadas. Passe o nome da tabela para a Lambda em `environment { variables = { TABLE_NAME = ... } }`.
10. Inclua `outputs.tf` com a URL da API, usando `aws_api_gateway_stage.prod.invoke_url`. O `main.tf` NÃO pode conter blocos `output`; todos os outputs ficam só em `outputs.tf`. Chaves do dicionário terraform: `main.tf`, `variables.tf`, `outputs.tf`.

PYTHON
11. Leia configuração com `os.environ["TABLE_NAME"]`, NUNCA de `event["region"]` ou `event["table_name"]`. Crie o cliente boto3 fora do handler. Importe tudo que usar (`os`, `json`, `logging`, `boto3`, `ClientError`).
12. Retorne SEMPRE um dict no formato do API Gateway proxy:
   {"statusCode": 200, "headers": {"Content-Type": "application/json"}, "body": json.dumps(dados, default=str)}
   NUNCA escreva `return json.dumps(...)` direto no handler.
13. Trate erros: item inexistente retorna 404 (`response.get("Item")` vazio), entrada inválida retorna 400, `ClientError` retorna 500 com mensagem genérica. NUNCA devolva `e.response` ao cliente. Registre o erro com `logging`.
14. Nunca devolva o `response` bruto do DynamoDB (contém ResponseMetadata). Devolva só os dados.
15. Inclua `requirements.txt` só com o que realmente precisa (o `boto3` já existe no runtime da Lambda).

GERAÇÃO
16. Escreva TODO o código HCL e Python completo, de TODAS as Lambdas, linha por linha. É PROIBIDO abreviar com "[CÓDIGO AQUI]", "...", "omitted for brevity" ou "repita para as demais".
17. O diagrama Mermaid deve usar exatamente os mesmos nomes das Lambdas e arquivos que você gerou, nem mais nem menos.
18. FORMATO JSON: cada arquivo é UMA string JSON, com quebras de linha como \\n e aspas internas escapadas. Para reduzir erros de escape, no código Python prefira aspas simples. O objeto `terraform` contém os TRÊS arquivos (main.tf, variables.tf, outputs.tf) e só fecha depois do último. Revise as chaves e vírgulas antes de responder.
19. Responda SOMENTE com o JSON pedido, sem texto antes ou depois."""

# Model hosted on Groq (change here to try another one)
GROQ_MODEL = "openai/gpt-oss-120b"
MAX_ATTEMPTS = 3

# Output budget per request. gpt-oss is a reasoning model: its "thinking" tokens
# count against this limit too, and a full CRUD (5 Lambdas, each with role,
# policy, log group, permission, method and integration) is ~10k tokens of
# Terraform alone. Groq allows up to 65,536 completion tokens for this model.
MAX_TOKENS = 32000


def load_text_model():
    """Create the Groq client. The key comes from the GROQ_API_KEY variable (.env)."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY not found. Add GROQ_API_KEY=gsk_... to the .env file"
        )

    print(f"Connecting to Groq with model {GROQ_MODEL}...")
    return ChatGroq(
        api_key=api_key,
        model=GROQ_MODEL,
        temperature=0.1,
        max_tokens=MAX_TOKENS,
        max_retries=2,
        timeout=120,
        # Forces a valid JSON response (the prompt already mentions JSON via format_instructions)
        model_kwargs={"response_format": {"type": "json_object"}},
    )


class GenerationTruncatedError(RuntimeError):
    """The model hit MAX_TOKENS before finishing the JSON document."""


def _failed_generation(error):
    """Text the model produced before Groq rejected it (json_validate_failed), if any."""
    body = getattr(error, "body", None)
    if not isinstance(body, dict):
        return None
    failed = (body.get("error") or {}).get("failed_generation")
    return failed if isinstance(failed, str) else None


def _is_truncated(error):
    """A json_validate_failed whose output never reached the closing brace was cut
    off by MAX_TOKENS, not malformed: retrying with the same limit cannot succeed."""
    failed = _failed_generation(error)
    return failed is not None and not failed.rstrip().endswith("}")


def _invoke_with_retry(chain, payload):
    """Retry when the model returns invalid JSON (intermittent escaping failure)."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return chain.invoke(payload)
        except (BadRequestError, OutputParserException) as e:
            # Other 400 errors (bad key, bad parameters) are not worth retrying
            if isinstance(e, BadRequestError) and "json_validate_failed" not in str(e):
                raise
            if isinstance(e, BadRequestError) and _is_truncated(e):
                raise GenerationTruncatedError(
                    f"The model output was cut off at {MAX_TOKENS} tokens before the "
                    "JSON was complete. Simplify the product description or raise "
                    "MAX_TOKENS in ai/machine.py"
                ) from e
            if attempt == MAX_ATTEMPTS:
                raise
            print(
                f"Invalid JSON from the model, attempt {attempt + 1}/{MAX_ATTEMPTS}..."
            )
            time.sleep(2 * attempt)  # eases the tokens-per-minute rate limit


def generate_architecture_script(llm, prompt_text, rag_context):
    print("\nGenerating architecture, Mermaid diagram and code...")

    # The Pydantic parser validates the JSON against the AWSArchitecture schema
    parser = PydanticOutputParser(pydantic_object=AWSArchitecture)

    # With a chat API the manual ChatML tags are no longer needed: Groq applies the model template
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "{system_rules}"),
            (
                "user",
                "[CONTEXTO RAG]:\n{context}\n\n"
                "[DESCRIÇÃO DO PRODUTO]:\n{product}\n\n"
                "[TAREFA]:\n"
                "Projete a arquitetura AWS Serverless para este produto e gere o "
                "Terraform (HCL) e o código Python das Lambdas, seguindo as regras do sistema.\n"
                "Use analysis_date = {today_date}.\n\n"
                "{format_instructions}",
            ),
        ]
    ).partial(format_instructions=parser.get_format_instructions())

    chain = prompt | llm | parser

    result_pydantic = _invoke_with_retry(
        chain,
        {
            "system_rules": SYSTEM_RULES,
            "context": rag_context,
            "product": prompt_text,
            "today_date": date.today().isoformat(),
        },
    )

    result = result_pydantic.model_dump()
    result["analysis_date"] = (
        date.today().isoformat()
    )  # guarantees the date even if the model gets it wrong
    result["mermaid_diagram"] = unescape_newlines(result["mermaid_diagram"])
    for files in result["generated_code"].values():
        for name, content in files.items():
            files[name] = unescape_newlines(content)
    return result


def unescape_newlines(text):
    r"""Undo double-escaped line breaks.

    The model sometimes writes "\\n" inside the JSON strings, which decodes to
    the two characters backslash + n instead of a line break, leaving a whole
    file on one line. Only applies when the text has no real line break at all;
    a multi-line file is never touched. (In a double-escaped file a "\n" inside
    a Python string literal is indistinguishable from a line break, so it is
    restored as a line break too: a rare, visible slip instead of a one-line file.)
    """
    if "\n" in text or "\\n" not in text:
        return text
    return text.replace("\\n", "\n")
