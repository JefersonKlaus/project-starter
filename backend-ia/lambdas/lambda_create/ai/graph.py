"""LangGraph workflow: generate the project, validate it and ask the model to fix it.

    START -> retrieve_references -> generate -> link_code
          -> validate_python -> validate_terraform -> validate_layout -> validate_deployment
          -> review --(errors, attempts and time left)--> generate (repair)
                   \\--(valid, or out of attempts/time)--> finalize -> END

retrieve_references  RAG search and the project layout of the reference project
generate             one Groq call; on a repair, the previous answer + the errors
link_code            make the Terraform package/invoke the generated Python files
validate_*           the four stages of ai/validation (python, terraform, layout, deployment)
review               keeps the best draft (fewest errors) and decides what comes next
finalize             the response: best draft + validation report

Limits (environment): MAX_REPAIR_ATTEMPTS (default 2) extra generations, and no repair
starts when GENERATION_TIME_BUDGET_SECONDS (default 600) would be exceeded.
"""

import json
import logging
import os
import time
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from .code_linker import link_generated_code
from .machine import generate_draft, repair_messages
from .project_layout import DEFAULT_LAYOUT, ProjectLayout, infer_layout
from .validation import (
    summarize,
    validate_deployment,
    validate_layout,
    validate_python,
    validate_terraform,
)
from .validation.issues import warning
from .validation.terraform_model import parse_project

logger = logging.getLogger(__name__)

STAGES = ("python", "terraform", "layout", "deployment")
DEFAULT_MAX_REPAIR_ATTEMPTS = 2
DEFAULT_TIME_BUDGET_SECONDS = 600


class ArchitectureState(TypedDict, total=False):
    prompt: str
    rag_context: str
    documents: list
    layout: ProjectLayout
    started_at: float
    max_repairs: int
    time_budget: float
    # current draft
    attempt: int  # generations done
    architecture: dict
    files: dict  # project path -> content
    fixes: list  # repairs made by the code linker
    terraform_project: Any
    python_issues: list
    terraform_issues: list
    layout_issues: list
    deployment_issues: list
    last_generation_seconds: float
    repair_error: str
    # across attempts
    history: list
    best: dict
    result: dict


def _int_env(name, default):
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def _model_answer(architecture):
    """The previous answer, as the model wrote it (no derived fields)."""
    code = architecture["generated_code"]
    return json.dumps(
        {
            "analysis_date": architecture["analysis_date"],
            "mermaid_diagram": architecture["mermaid_diagram"],
            "aws_services": architecture["aws_services"],
            "generated_code": {
                "terraform": code.get("terraform", {}),
                "python": code.get("python", {}),
            },
        },
        ensure_ascii=False,
    )


def _issues(state):
    return [issue for stage in STAGES for issue in state.get(f"{stage}_issues") or []]


def build_workflow(llm, rag_engine=None):
    """Compile the graph. rag_engine may be None when the state brings the context."""

    def retrieve_references(state):
        if state.get("layout") is not None or rag_engine is None:
            return {"layout": state.get("layout") or DEFAULT_LAYOUT}
        # Search for reference implementations in the index
        rag_context, documents = rag_engine.find_references(state["prompt"])
        # The generated project follows the layout of the reference project the RAG
        # found (the whole index is passed so sibling files of the retrieved ones are
        # visible); with no usable reference the default layout is used
        layout = infer_layout(documents, getattr(rag_engine, "documents", ()))
        logger.info("Project layout (%s): %s", layout.origin, layout.to_dict())
        return {"rag_context": rag_context, "documents": documents, "layout": layout}

    def generate(state):
        attempt = state.get("attempt", 0) + 1
        repair = ()
        if state.get("architecture"):
            errors, _ = summarize(_issues(state))
            repair = repair_messages(
                _model_answer(state["architecture"]), [str(e) for e in errors]
            )
            logger.info(
                "Repair attempt %d: %d error(s) sent back", attempt, len(errors)
            )
        started = time.monotonic()
        try:
            architecture = generate_draft(
                llm,
                state["prompt"],
                state.get("rag_context", ""),
                state["layout"],
                repair=repair,
            )
        except Exception as e:
            if not repair:
                raise  # nothing generated yet: the request fails
            logger.exception("Repair attempt %d failed", attempt)
            return {"attempt": attempt, "repair_error": f"{type(e).__name__}: {e}"}
        return {
            "attempt": attempt,
            "architecture": architecture,
            "last_generation_seconds": time.monotonic() - started,
        }

    def link_code(state):
        fixes = []
        issues = link_generated_code(
            state["architecture"]["generated_code"], state["layout"], fixes=fixes
        )
        # What the linker could not repair is re-checked (as errors) by the validators
        return {
            "files": state["architecture"]["generated_code"]["files"],
            "fixes": fixes,
            "layout_issues": [warning("layout", issue) for issue in issues],
        }

    def python_stage(state):
        return {"python_issues": validate_python(state["files"])}

    def terraform_stage(state):
        project = parse_project(state["files"])
        return {
            "terraform_project": project,
            "terraform_issues": validate_terraform(state["files"], project),
        }

    def layout_stage(state):
        linker_notes = state.get("layout_issues") or []
        return {
            "layout_issues": linker_notes
            + validate_layout(
                state["files"], state["layout"], state["terraform_project"]
            )
        }

    def deployment_stage(state):
        return {
            "deployment_issues": validate_deployment(
                state["files"], state["layout"], state["terraform_project"]
            )
        }

    def review(state):
        errors, warnings = summarize(_issues(state))
        history = list(state.get("history") or [])
        history.append(
            {
                "attempt": state["attempt"],
                "errors": len(errors),
                "warnings": len(warnings),
            }
        )
        logger.info(
            "Validation of attempt %d: %d error(s), %d warning(s)",
            state["attempt"],
            len(errors),
            len(warnings),
        )
        best = state.get("best")
        if best is None or len(errors) < len(best["errors"]):
            best = {
                "attempt": state["attempt"],
                "architecture": state["architecture"],
                "fixes": state.get("fixes") or [],
                "errors": errors,
                "warnings": warnings,
                "issues": {
                    stage: state.get(f"{stage}_issues") or [] for stage in STAGES
                },
            }
        return {"history": history, "best": best}

    def after_review(state):
        if not state["best"]["errors"]:
            return "finalize"
        if state["attempt"] > state["max_repairs"]:
            logger.warning("Out of repair attempts (%d)", state["max_repairs"])
            return "finalize"
        elapsed = time.monotonic() - state["started_at"]
        if elapsed + state.get("last_generation_seconds", 0) > state["time_budget"]:
            logger.warning("No time left for a repair (%.0f s elapsed)", elapsed)
            return "finalize"
        return "generate"

    def after_generate(state):
        return "finalize" if state.get("repair_error") else "link_code"

    def finalize(state):
        best = state["best"]
        result = dict(best["architecture"])
        errors, warnings = best["errors"], best["warnings"]
        checks = {
            stage: {
                "errors": sum(
                    1 for i in best["issues"][stage] if i.severity == "error"
                ),
                "warnings": sum(
                    1 for i in best["issues"][stage] if i.severity == "warning"
                ),
            }
            for stage in STAGES
        }
        validation = {
            "valid": not errors,
            "attempts": state["attempt"],
            "returned_attempt": best["attempt"],
            "checks": checks,
            "errors": [issue.to_dict() for issue in errors],
            "warnings": [issue.to_dict() for issue in warnings],
            "fixes": best["fixes"],
            "history": state["history"],
        }
        if state.get("repair_error"):
            validation["repair_error"] = state["repair_error"]
        result["validation"] = validation
        # Every remaining problem as text (kept for clients of the previous format)
        result["warnings"] = [str(issue) for issue in errors + warnings]
        result["project_layout"] = state["layout"].to_dict()
        if state.get("documents") is not None:
            # RAG references in the response, for auditing
            result["rag_references"] = [
                doc.metadata.get("source", "unknown") for doc in state["documents"]
            ]
        return {"result": result}

    graph = StateGraph(ArchitectureState)
    graph.add_node("retrieve_references", retrieve_references)
    graph.add_node("generate", generate)
    graph.add_node("link_code", link_code)
    graph.add_node("validate_python", python_stage)
    graph.add_node("validate_terraform", terraform_stage)
    graph.add_node("validate_layout", layout_stage)
    graph.add_node("validate_deployment", deployment_stage)
    graph.add_node("review", review)
    graph.add_node("finalize", finalize)

    graph.add_edge(START, "retrieve_references")
    graph.add_edge("retrieve_references", "generate")
    graph.add_conditional_edges(
        "generate", after_generate, {"link_code": "link_code", "finalize": "finalize"}
    )
    graph.add_edge("link_code", "validate_python")
    graph.add_edge("validate_python", "validate_terraform")
    graph.add_edge("validate_terraform", "validate_layout")
    graph.add_edge("validate_layout", "validate_deployment")
    graph.add_edge("validate_deployment", "review")
    graph.add_conditional_edges(
        "review", after_review, {"generate": "generate", "finalize": "finalize"}
    )
    graph.add_edge("finalize", END)
    return graph.compile()


def run_architecture_workflow(
    llm, prompt, rag_engine=None, rag_context="", layout=None, max_repairs=None
):
    """Run the workflow and return the response body (architecture + validation)."""
    if max_repairs is None:
        max_repairs = _int_env("MAX_REPAIR_ATTEMPTS", DEFAULT_MAX_REPAIR_ATTEMPTS)
    state = {
        "prompt": prompt,
        "rag_context": rag_context,
        "started_at": time.monotonic(),
        "max_repairs": max(0, max_repairs),
        "time_budget": _int_env(
            "GENERATION_TIME_BUDGET_SECONDS", DEFAULT_TIME_BUDGET_SECONDS
        ),
    }
    if layout is not None:
        state["layout"] = layout
    # Each generation runs 8 nodes; LangGraph stops runaway graphs at recursion_limit
    limit = 8 * (max_repairs + 1) + 5
    final = build_workflow(llm, rag_engine).invoke(state, {"recursion_limit": limit})
    return final["result"]
