import logging
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware

from models import PayloadRequisicao
from rag import MotorRAG
from machine import load_text_model, generate_architecture_script

logger = logging.getLogger(__name__)
load_dotenv()
API_SECRET = os.environ.get("API_SECRET")

# Variáveis globais de estado da IA
ia_state = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Executa ao iniciar o servidor
    print("Iniciando serviços pesados (Modelos LLM e Banco Vetorial)...")
    ia_state["rag"] = MotorRAG()

    llm = load_text_model()
    ia_state["llm"] = llm

    yield
    ia_state.clear()


app = FastAPI(title="Especialista Cloud - Motor de RAG e Código", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],            
    allow_credentials=True,
    allow_methods=["*"],            
    allow_headers=["*"],            
)
header_chave_api = APIKeyHeader(name="X-API-Key", auto_error=True)


def validar_api_key(chave_enviada: str = Security(header_chave_api)):
    if chave_enviada != API_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Acesso negado: API Key inválida",
        )
    return chave_enviada


@app.post("/analisar", dependencies=[Security(validar_api_key)])
async def gerar_arquitetura(payload: PayloadRequisicao):
    try:
        motor_rag = ia_state["rag"]
        llm = ia_state["llm"]

        # Busca os gabaritos no banco vetorial
        contexto_rag, documentos = motor_rag.buscar_gabaritos(payload.prompt)

        # Geração e Extração unificadas via LangChain ---
        resposta_final = generate_architecture_script(
            llm=llm, prompt_text=payload.prompt, contexto_rag=contexto_rag
        )

        if isinstance(resposta_final, list) and len(resposta_final) > 0:
            resposta_final = resposta_final[0]
        if not isinstance(resposta_final, dict):
            raise ValueError(
                f"Formato JSON inesperado do modelo. Tipo: {type(resposta_final).__name__}"
            )

        # Adiciona a auditoria do RAG na resposta
        resposta_final["rag_references"] = [
            doc.metadata.get("source", "desconhecido") for doc in documentos
        ]

        return resposta_final

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Falha ao analisar a arquitetura")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Não foi possível processar a arquitetura: {e}",
        ) from e
