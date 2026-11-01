"""Service: lifecycle of the heavy clients (vector database and LLM).

They are cached at module level so that warm Lambda containers reuse them
instead of reloading on every invocation.
"""

from ai.machine import load_text_model

from ai.rag import RAGEngine

ai_state = {}


def get_ai_state():
    """Lazily initialize the RAG engine and the LLM client on the first invocation."""
    if "rag" not in ai_state:
        print("Starting heavy services (LLM models and vector database)...")
        ai_state["rag"] = RAGEngine()
    if "llm" not in ai_state:
        ai_state["llm"] = load_text_model()
    return ai_state
