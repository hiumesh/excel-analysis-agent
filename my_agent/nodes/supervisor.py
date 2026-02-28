"""Supervisor node — evaluates whether a new analysis run is needed."""

import logging
from typing import Any, cast, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from my_agent.core.config import ModelConfig
from my_agent.core.llm import get_llm
from my_agent.models.schemas import SupervisorOutput
from my_agent.models.state import ExcelAnalysisState
from my_agent.prompts.prompts import SUPERVISOR_SYS_PROMPT, SUPERVISOR_USER_PROMPT

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper: build a fallback decision dict
# ---------------------------------------------------------------------------

def _fallback_decision(reason: str) -> Dict[str, Any]:
    """Return a supervisor_decision that defaults to *requiring* new analysis."""
    return {
        "supervisor_decision": {
            "needs_analysis": True,
            "reuse_previous_results": False,
            "scope_changed": False,
            "entity_mismatch": False,
            "data_sufficient": True,
            "reasoning": reason,
        }
    }


# ---------------------------------------------------------------------------
# Helper: extract inputs from state
# ---------------------------------------------------------------------------

def _extract_inputs(state: ExcelAnalysisState) -> tuple[
    Dict[str, Any],   # router_output
    str,               # user_query
    Dict[str, Any],    # dataset_summary
]:
    """Pull router output, user query, and dataset summary from state.

    Raises ``ValueError`` if the router output is missing.
    """
    router_output = state.get("route_decision")
    if not router_output:
        raise ValueError("No router output found in state")

    # Latest user query
    user_messages = [
        msg for msg in state["messages"] if isinstance(msg, HumanMessage)
    ]
    user_query = user_messages[-1].content if user_messages else "Analyze the data"

    # Dataset summary from data_context
    data_context = state.get("data_context") or {}
    dataset_summary = data_context.get("summary", {}) if data_context else {}

    return router_output, user_query, dataset_summary


# ---------------------------------------------------------------------------
# Helper: invoke the LLM for a structured supervisor decision
# ---------------------------------------------------------------------------

async def _classify_with_llm(
    user_query: str,
    router_output: Dict[str, Any],
    dataset_summary: Dict[str, Any],
) -> SupervisorOutput:
    """Call the supervisor LLM and return a validated ``SupervisorOutput``."""
    llm = await get_llm(ModelConfig.SUPERVISOR_MODEL, temperature=0)

    system_prompt = SystemMessage(content=SUPERVISOR_SYS_PROMPT)
    user_prompt = HumanMessage(
        content=SUPERVISOR_USER_PROMPT.format(
            user_query=user_query,
            router_output=router_output,
            previous_metadata={},  # Scope tracking not yet persisted
            dataset_summary=dataset_summary,
        )
    )

    llm_structured = llm.with_structured_output(
        SupervisorOutput, method="function_calling"
    )
    response_raw = await llm_structured.ainvoke([system_prompt, user_prompt])

    if isinstance(response_raw, dict):
        return SupervisorOutput(**response_raw)
    return cast(SupervisorOutput, response_raw)


# ---------------------------------------------------------------------------
# Main node
# ---------------------------------------------------------------------------

async def supervisor_node(state: ExcelAnalysisState) -> Dict[str, Any]:
    """Supervisor Node — decides whether a new code-execution analysis is needed.

    Workflow:
        1. Extract router output, user query, and dataset summary from state.
        2. Invoke the LLM for a structured decision.
        3. Log and return the decision.

    On **any** error the node falls back to ``needs_analysis=True`` so the
    graph always proceeds forward (worst case: redundant analysis).
    """
    logger.info("🎯 Supervisor: Evaluating if new analysis is needed...")

    try:
        # 1. Extract inputs ----------------------------------------------------
        router_output, user_query, dataset_summary = _extract_inputs(state)

        # 2. LLM classification ------------------------------------------------
        try:
            response = await _classify_with_llm(
                user_query, router_output, dataset_summary
            )
        except Exception as llm_err:
            logger.error("Supervisor LLM call failed: %s", llm_err, exc_info=True)
            return _fallback_decision(
                f"Supervisor LLM error — defaulting to new analysis: {llm_err}"
            )

        # 3. Build result ------------------------------------------------------
        decision = response.model_dump()

        logger.info(
            "=========== Supervisor Decision ===========\n"
            "  Needs Analysis: %s\n"
            "  Reuse Previous: %s\n"
            "  Scope Changed: %s\n"
            "  Entity Mismatch: %s\n"
            "  Data Sufficient: %s\n"
            "  Reasoning: %s\n"
            "============================================",
            response.needs_analysis,
            response.reuse_previous_results,
            response.scope_changed,
            response.entity_mismatch,
            response.data_sufficient,
            response.reasoning,
        )

        return {"supervisor_decision": decision}

    except Exception as exc:
        # Catch-all — ensures the graph never crashes at this node
        logger.error("Supervisor node failed: %s", exc, exc_info=True)
        return _fallback_decision(
            f"Supervisor error — defaulting to new analysis: {exc}"
        )
