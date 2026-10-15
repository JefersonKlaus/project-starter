import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Security, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from machine import generate_architecture_script, load_text_model
from models import PayloadRequisicao

from rag import MotorRAG

logger = logging.getLogger(__name__)
load_dotenv()
API_SECRET = os.environ.get("API_SECRET")

# Global AI state
ia_state = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Run when the server starts
    print("Starting heavy services (LLM models and vector database)...")
    ia_state["rag"] = MotorRAG()

    llm = load_text_model()
    ia_state["llm"] = llm

    yield
    ia_state.clear()


app = FastAPI(title="Cloud Specialist - RAG and Code Engine", lifespan=lifespan)
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
            detail="Access denied: invalid API key",
        )
    return chave_enviada


@app.post("/analisar", dependencies=[Security(validar_api_key)])
async def gerar_arquitetura(payload: PayloadRequisicao):
    try:
        motor_rag = ia_state["rag"]
        llm = ia_state["llm"]

        # Search for reference implementations in the vector database
        contexto_rag, documentos = motor_rag.buscar_gabaritos(payload.prompt)

        # Unified generation and extraction through LangChain
        resposta_final = generate_architecture_script(
            llm=llm, prompt_text=payload.prompt, contexto_rag=contexto_rag
        )

        if isinstance(resposta_final, list) and len(resposta_final) > 0:
            resposta_final = resposta_final[0]
        if not isinstance(resposta_final, dict):
            raise ValueError(
                f"Unexpected JSON format from the model. Type: {type(resposta_final).__name__}"
            )

        # Add RAG references to the response for auditing
        resposta_final["rag_references"] = [
            doc.metadata.get("source", "unknown") for doc in documentos
        ]

        return resposta_final

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to analyze the architecture")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not process the architecture: {e}",
        ) from e
