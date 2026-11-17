"""Service: generate an AWS architecture (diagram, Terraform and Python) for a product description.

The work is a LangGraph workflow (ai/graph.py): RAG search -> generation -> validation
of the Python, the Terraform, the project layout and the deployment -> repair by the
model while there are errors.
"""

from ai.graph import run_architecture_workflow
from service_ai import get_ai_state


def create_architecture(prompt: str) -> dict:
    state = get_ai_state()
    return run_architecture_workflow(
        llm=state["llm"], prompt=prompt, rag_engine=state["rag"]
    )
