"""Service: generate an AWS architecture (diagram, Terraform and Python) for a product description."""

from .ai.machine import generate_architecture_script
from .service_ai import get_ai_state


def create_architecture(prompt: str) -> dict:
    state = get_ai_state()
    rag_engine = state["rag"]
    llm = state["llm"]

    # Search for reference implementations in the vector database
    rag_context, documents = rag_engine.find_references(prompt)

    # Unified generation and extraction through LangChain
    final_response = generate_architecture_script(
        llm=llm,
        prompt_text=prompt,
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
