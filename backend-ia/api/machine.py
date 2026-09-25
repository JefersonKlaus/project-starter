from models import ArquiteturaAWS

from unsloth import FastLanguageModel
from transformers import pipeline
from langchain_huggingface import HuggingFacePipeline
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser


# Regras de Negócio
INSTRUCAO = """Você é um Arquiteto Cloud especialista em AWS Serverless.
Sua missão é gerar infraestrutura (Terraform HCL) e código (Python) para a descrição fornecida.

REGRAS CRÍTICAS DE ARQUITETURA (ESTAS REGRAS SOBREPÕEM QUALQUER CONTEXTO):
1. SEPARAÇÃO ESTRITA (MICROSERVIÇOS): É ESTRITAMENTE PROIBIDO criar Lambdas monolíticas. CADA ação (GET, POST, PUT, DELETE) DEVE ter seu próprio arquivo Python isolado (ex: get_item.py, post_item.py) e seu próprio `aws_lambda_function` no Terraform.
2. PROIBIDO ROTEAMENTO INTERNO: NENHUM arquivo Python gerado pode conter validações como `if event['httpMethod']`. A Lambda já deve assumir que foi chamada pelo método correto via API Gateway.
3. CONTEXTO RAG: Use o [CONTEXTO RAG] fornecido apenas como referência para a lógica de negócio e uso do `boto3`. SE o contexto for monolítico, VOCÊ DEVE QUEBRÁ-LO em múltiplas Lambdas respeitando a Regra 1.
4. TERRAFORM COMPLETO: Crie `aws_lambda_function`, `aws_iam_role` e `aws_lambda_permission` separados e dedicados para CADA Lambda gerada.
5. GERAÇÃO REAL: Escreva todo o código HCL e Python linha por linha, sem usar marcações como "[CÓDIGO AQUI]". Converta o retorno da Lambda sempre com `json.dumps()`.

[CONTEXTO RAG]:
"""


def load_text_model():
    print("Carregando Qwen2.5-Coder-7B-Instruct na VRAM...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name="unsloth/Qwen2.5-Coder-7B-Instruct-bnb-4bit",
        load_in_4bit=True,
        use_gradient_checkpointing="unsloth",
    )
    FastLanguageModel.for_inference(model)

    # Transformamos o modelo local em um pipeline do HuggingFace
    pipe = pipeline(
        "text-generation",
        model=model,
        tokenizer=tokenizer,
        max_new_tokens=8192,
        temperature=0.6,  # Temperatura ideal para forçar a geração de código criativo
        top_p=0.9,
        repetition_penalty=1.02,
        return_full_text=False,
    )

    return HuggingFacePipeline(pipeline=pipe)


def generate_architecture_script(llm, prompt_text, contexto_rag):
    print("\nGerando arquitetura, Mermaid e código...")

    # O Parser Pydantic que força a saída do JSON correto
    parser = PydanticOutputParser(pydantic_object=ArquiteturaAWS)

    # O Template com as tags ChatML para o Qwen não travar
    prompt_template = PromptTemplate(
        template=(
            "<|im_start|>system\nVocê é um Arquiteto Cloud e engenheiro de software.<|im_end|>\n"
            "<|im_start|>user\n"
            "{instrucao}\n{contexto}\n\n"
            "[DESCRIÇÃO DO PRODUTO]:\n{produto}\n\n"
            "{format_instructions}\n"
            "<|im_end|>\n"
            "<|im_start|>assistant\n"
        ),
        input_variables=["instrucao", "contexto", "produto"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )

    # LCEL (LangChain Expression Language)
    chain = prompt_template | llm | parser

    # Invocação e conversão final para Dicionário
    resultado_pydantic = chain.invoke(
        {"instrucao": INSTRUCAO, "contexto": contexto_rag, "produto": prompt_text}
    )

    return resultado_pydantic.model_dump()
