"""LangGraph Workflow Graph and Execution Orchestrator.

Purpose:
    Constructs, compiles, and executes the LangGraph state machine governing
    autonomous lesson generation, deterministic checking, LLM judging, and revisions.

Inputs/Outputs:
    Inputs: Initial AgentState dictionary.
    Outputs: Final evaluated AgentState dictionary with terminal status.

What it must NOT do:
    - Must NOT import UI or API transport components.
    - Must NOT allow retries beyond max_retries hard cap.
    - Must NOT swallow BudgetExhaustedError or infrastructure errors as passing runs.
"""
import logging
from typing import Literal

from langgraph.graph import END, StateGraph

from agent.nodes import (
    deterministic_checks_node,
    generate_node,
    judge_node,
    persist_node,
    persist_rejection_node,
    prepare_revision_node,
    release_gate_node,
    revise_node,
    validate_input_node,
)
from agent.state import AgentState
from evaluation.judge import JudgeEvaluationError
from memory.store import RunModel, get_db_context
from shared.enums import RunStatus
from shared.llm_client import BudgetExhaustedError, InfrastructureExhaustedError

logger = logging.getLogger("lesson_generator.graph")


def route_after_validate(
    state: AgentState,
) -> Literal["generate", "persist_rejection"]:
    """Routes after validation. Halts if cancelled.

    Args:
        state: Current AgentState.

    Returns:
        Next node name to execute.
    """
    if state.get("cancel_requested") or state.get("status") == RunStatus.CANCELLED:
        return "persist_rejection"
    return "generate"


def route_after_generate(
    state: AgentState,
) -> Literal["deterministic_checks", "persist_rejection"]:
    """Routes after generation. Halts if cancelled.

    Args:
        state: Current AgentState.

    Returns:
        Next node name to execute.
    """
    if state.get("cancel_requested") or state.get("status") == RunStatus.CANCELLED:
        return "persist_rejection"
    return "deterministic_checks"


def route_after_revise(
    state: AgentState,
) -> Literal["deterministic_checks", "persist_rejection"]:
    """Routes after revision. Halts if cancelled.

    Args:
        state: Current AgentState.

    Returns:
        Next node name to execute.
    """
    if state.get("cancel_requested") or state.get("status") == RunStatus.CANCELLED:
        return "persist_rejection"
    return "deterministic_checks"


def route_after_deterministic(
    state: AgentState,
) -> Literal["judge", "prepare_revision", "persist_rejection"]:
    """Routes execution after deterministic checks. Skips judge if checks fail.

    Args:
        state: Current AgentState.

    Returns:
        Name of next target node: 'judge', 'prepare_revision', or 'persist_rejection'.
    """
    if state.get("cancel_requested") or state.get("status") == RunStatus.CANCELLED:
        return "persist_rejection"

    if state.get("deterministic_failed", False):
        attempt = state.get("current_attempt", 1)
        max_retries = state.get("max_retries", 1)
        if attempt <= max_retries:
            return "prepare_revision"
        return "persist_rejection"
    return "judge"


def route_after_release_gate(
    state: AgentState,
) -> Literal["persist", "prepare_revision", "persist_rejection"]:
    """Routes execution after release gate verdict.

    Args:
        state: Current AgentState.

    Returns:
        Name of next target node: 'persist', 'prepare_revision', or 'persist_rejection'.
    """
    if state.get("cancel_requested") or state.get("status") == RunStatus.CANCELLED:
        return "persist_rejection"

    decision = state.get("release_decision")
    if decision and decision.passed:
        return "persist"

    attempt = state.get("current_attempt", 1)
    max_retries = state.get("max_retries", 1)
    if attempt <= max_retries:
        return "prepare_revision"
    return "persist_rejection"


def create_lesson_graph():
    """Builds and compiles the lesson generator LangGraph workflow.

    Returns:
        Compiled StateGraph runnable.
    """
    workflow = StateGraph(AgentState)

    workflow.add_node("validate_input", validate_input_node)
    workflow.add_node("generate", generate_node)
    workflow.add_node("deterministic_checks", deterministic_checks_node)
    workflow.add_node("judge", judge_node)
    workflow.add_node("release_gate", release_gate_node)
    workflow.add_node("prepare_revision", prepare_revision_node)
    workflow.add_node("revise", revise_node)
    workflow.add_node("persist", persist_node)
    workflow.add_node("persist_rejection", persist_rejection_node)

    workflow.set_entry_point("validate_input")
    workflow.add_conditional_edges(
        "validate_input",
        route_after_validate,
        {
            "generate": "generate",
            "persist_rejection": "persist_rejection",
        },
    )
    workflow.add_conditional_edges(
        "generate",
        route_after_generate,
        {
            "deterministic_checks": "deterministic_checks",
            "persist_rejection": "persist_rejection",
        },
    )

    workflow.add_conditional_edges(
        "deterministic_checks",
        route_after_deterministic,
        {
            "judge": "judge",
            "prepare_revision": "prepare_revision",
            "persist_rejection": "persist_rejection",
        },
    )

    workflow.add_edge("judge", "release_gate")

    workflow.add_conditional_edges(
        "release_gate",
        route_after_release_gate,
        {
            "persist": "persist",
            "prepare_revision": "prepare_revision",
            "persist_rejection": "persist_rejection",
        },
    )

    workflow.add_edge("prepare_revision", "revise")
    workflow.add_conditional_edges(
        "revise",
        route_after_revise,
        {
            "deterministic_checks": "deterministic_checks",
            "persist_rejection": "persist_rejection",
        },
    )
    workflow.add_edge("persist", END)
    workflow.add_edge("persist_rejection", END)

    return workflow.compile()


lesson_graph = create_lesson_graph()


def execute_lesson_workflow(initial_state: AgentState) -> AgentState:
    """Executes the compiled LangGraph workflow with global error boundary management.

    Args:
        initial_state: Configured input state.

    Returns:
        Final evaluated state with terminal status.
    """
    run_id = initial_state["run_id"]
    try:
        final_state = lesson_graph.invoke(initial_state)
        return final_state

    except BudgetExhaustedError as exc:
        logger.error("Run %s halted: Token budget exhausted: %s", run_id, exc)
        with get_db_context() as db:
            run = db.get(RunModel, run_id)
            if run:
                run.status = RunStatus.BUDGET_EXHAUSTED.value
                run.error_message = str(exc)
        initial_state["status"] = RunStatus.BUDGET_EXHAUSTED
        initial_state["error_message"] = str(exc)
        return initial_state

    except (InfrastructureExhaustedError, JudgeEvaluationError) as exc:
        logger.error("Run %s failed with service/infrastructure error: %s", run_id, exc)
        with get_db_context() as db:
            run = db.get(RunModel, run_id)
            if run:
                run.status = RunStatus.ERROR.value
                run.error_message = str(exc)
        initial_state["status"] = RunStatus.ERROR
        initial_state["error_message"] = str(exc)
        return initial_state

    except Exception as exc:
        logger.exception("Run %s encountered unhandled system error: %s", run_id, exc)
        with get_db_context() as db:
            run = db.get(RunModel, run_id)
            if run:
                run.status = RunStatus.ERROR.value
                run.error_message = f"Internal error: {exc}"
        initial_state["status"] = RunStatus.ERROR
        initial_state["error_message"] = str(exc)
        return initial_state
