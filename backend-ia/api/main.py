import asyncio
import logging
import os
import secrets
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Security, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from machine import generate_architecture_script, load_text_model
from models import RequestPayload

from rag import RAGEngine

logger = logging.getLogger(__name__)
load_dotenv()
API_SECRET = os.environ.get("API_SECRET")
CORS_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CORS_ORIGINS", "").split(",")
    if origin.strip()
]

# Global AI state
ai_state = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not API_SECRET:
        raise RuntimeError("API_SECRET must be configured before starting the API")

    # Run when the server starts
    print("Starting heavy services (LLM models and vector database)...")
    ai_state["rag"] = RAGEngine()

    llm = load_text_model()
    ai_state["llm"] = llm

    yield
    ai_state.clear()


app = FastAPI(title="Cloud Specialist - RAG and Code Engine", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)


def validate_api_key(provided_key: str = Security(api_key_header)):
    if not API_SECRET or not secrets.compare_digest(provided_key, API_SECRET):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access denied: invalid API key",
        )
    return provided_key


@app.post("/create", dependencies=[Security(validate_api_key)])
async def create_architecture(payload: RequestPayload):
    try:
        rag_engine = ai_state["rag"]
        llm = ai_state["llm"]

        # Search for reference implementations in the vector database
        rag_context, documents = rag_engine.find_references(payload.prompt)

        # Unified generation and extraction through LangChain
        final_response = await asyncio.to_thread(
            generate_architecture_script,
            llm=llm,
            prompt_text=payload.prompt,
            rag_context=rag_context,
        )

        if isinstance(final_response, list) and len(final_response) > 0:
            final_response = final_response[0]
        if not isinstance(final_response, dict):
            raise ValueError(
                f"Unexpected JSON format from the model. Type: {type(final_response).__name__}"
            )

        # Add RAG references to the response for auditing
        final_response["rag_references"] = [
            doc.metadata.get("source", "unknown") for doc in documents
        ]

        return final_response

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to analyze the architecture")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not process the architecture: {e}",
        ) from e
