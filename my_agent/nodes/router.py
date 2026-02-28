"""Router node for intelligent query classification using LLM."""

import logging
from typing import Any, cast, Dict, List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from my_agent.core.config import ModelConfig
from my_agent.core.llm import get_llm
from my_agent.models.schemas import RouterOutput
from my_agent.models.state import ExcelAnalysisState, RouterDecision
from my_agent.prompts.prompts import ROUTER_SYS_PROMPT, ROUTER_USER_PROMPT

logger = logging.getLogger(__name__)

# Valid routes the router is allowed to emit
VALID_ROUTES = {"chat", "analysis", "analysis_followup"}

# Deterministic keyword rules used as override signals
_RULE_KEYWORDS: Dict[str, List[str]] = {
    "simulation": ["simulate", "what if", "reduce by", "increase by"],
    "followup": ["previous", "above", "more details", "earlier result"],
    "forecast_version": ["proj", "projection", "forecast"],
    "anomaly": ["anomaly", "outlier", "spike"],
}


# ---------------------------------------------------------------------------
# Helper: extract the latest user query from state
# ---------------------------------------------------------------------------
def _extract_user_query(state: ExcelAnalysisState) -> tuple[str, bool]:
    """Return (user_query, found_in_messages).

    ``found_in_messages`` is True when the query came from the messages list
    (as opposed to the ``user_query`` state key).  The caller uses this to
    decide whether an extra ``HumanMessage`` needs to be injected.
    """
    user_messages = [msg for msg in state["messages"] if isinstance(msg, HumanMessage)]

    if user_messages:
        raw_content = user_messages[-1].content
        # LangGraph Studio can send content as a list of dicts
        if isinstance(raw_content, list):
            text_parts = []
            for part in raw_content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text_parts.append(part.get("text", ""))
                elif isinstance(part, str):
                    text_parts.append(part)
            return " ".join(text_parts).strip(), True
        return str(raw_content), True

    # Fallback: UI may provide user_query directly
    return state.get("user_query", ""), False


# ---------------------------------------------------------------------------
# Helper: evaluate deterministic rule flags
# ---------------------------------------------------------------------------
def _evaluate_rule_flags(query_lower: str) -> Dict[str, bool]:
    """Return a dict of boolean flags based on keyword matching."""
    return {
        key: any(kw in query_lower for kw in keywords)
        for key, keywords in _RULE_KEYWORDS.items()
    }


# ---------------------------------------------------------------------------
# Helper: build a human-readable data-context summary
# ---------------------------------------------------------------------------
def _build_data_context_summary(data_context: Optional[Dict[str, Any]]) -> tuple[bool, str]:
    """Return (has_data_context, summary_text)."""
    if not isinstance(data_context, dict) or data_context.get("error"):
        return False, "No data loaded yet."

    summary = data_context.get("summary", {})
    text = (
        f"File: {data_context.get('file_name', 'unknown')}\n"
        f"Rows: {summary.get('num_rows', 0)}, Columns: {summary.get('num_columns', 0)}\n"
        f"Column Names: {summary.get('column_names', [])}\n"
        f"Numeric Columns: {summary.get('numeric_columns', [])}\n"
        f"Categorical Columns: {summary.get('categorical_columns', [])}\n"
        f"Description: {str(data_context.get('description', ''))[:500]}"
    )
    return True, text


# ---------------------------------------------------------------------------
# Helper: build a short conversation summary for the LLM prompt
# ---------------------------------------------------------------------------
def _build_conversation_summary(messages: List[BaseMessage], max_msgs: int = 8) -> str:
    """Return a truncated conversation summary string."""
    recent = messages[-max_msgs:] if len(messages) > max_msgs else messages
    return "\n".join(
        f"{'User' if isinstance(msg, HumanMessage) else 'Assistant'}: {msg.content[:150]}..."
        for msg in recent
    )


# ---------------------------------------------------------------------------
# Helper: invoke the LLM for structured routing
# ---------------------------------------------------------------------------
async def _classify_with_llm(
    user_query: str,
    conversation_summary: str,
    has_data_context: bool,
    data_context_summary: str,
) -> RouterOutput:
    """Call the router LLM and return a validated ``RouterOutput``."""
    llm = await get_llm(ModelConfig.ROUTER_MODEL, temperature=0)

    system_prompt = SystemMessage(content=ROUTER_SYS_PROMPT)
    user_prompt = HumanMessage(
        content=ROUTER_USER_PROMPT.format(
            user_query=user_query,
            conversation_summary=conversation_summary,
            has_data_context="Yes" if has_data_context else "No",
            data_context_summary=data_context_summary,
        )
    )

    llm_structured = llm.with_structured_output(RouterOutput, method="function_calling")
    response_raw = await llm_structured.ainvoke([system_prompt, user_prompt])

    if isinstance(response_raw, dict):
        return RouterOutput(**response_raw)
    return cast(RouterOutput, response_raw)


# ---------------------------------------------------------------------------
# Helper: apply deterministic rule overrides
# ---------------------------------------------------------------------------
def _apply_rule_overrides(
    route: str,
    analysis_type: Optional[str],
    requires_simulation: Optional[bool],
    rule_flags: Dict[str, bool],
    has_data_context: bool,
) -> tuple[str, Optional[str], bool]:
    """Merge keyword-based overrides into the LLM decision.

    Returns (route, analysis_type, requires_simulation).
    """
    if rule_flags["followup"] and has_data_context:
        route = "analysis_followup"

    if rule_flags["simulation"]:
        analysis_type = "simulation"
        requires_simulation = True
        route = "analysis"

    if rule_flags["anomaly"]:
        analysis_type = "anomaly_detection"

    if rule_flags["forecast_version"] and analysis_type is None:
        analysis_type = "forecast_comparison"

    return route, analysis_type, requires_simulation or False


# ---------------------------------------------------------------------------
# Helper: build the final result dict
# ---------------------------------------------------------------------------
def _build_chat_fallback(reason: str) -> Dict[str, Any]:
    """Return a state update that routes to the chat node."""
    return {"route_decision": {"route": "chat", "reasoning": reason}}


# ---------------------------------------------------------------------------
# Main node
# ---------------------------------------------------------------------------
async def router_node(state: ExcelAnalysisState) -> Dict[str, Any]:
    """Router Node — classifies user queries using LLM with structured output.

    Workflow:
        1. Extract the latest user query.
        2. Evaluate deterministic keyword rules.
        3. Enrich with data-context metadata.
        4. Invoke the LLM for structured classification.
        5. Merge rule-based overrides.
        6. Validate and return the routing decision.

    On **any** error the node gracefully falls back to the ``chat`` route
    so the user always gets a response.
    """
    logger.info("🧭 Router: Classifying user query...")

    try:
        # 1. Extract user query -----------------------------------------------
        user_query, found_in_messages = _extract_user_query(state)

        if not user_query:
            logger.warning("No user query found — defaulting to chat")
            return _build_chat_fallback("No user query found")

        logger.info("User Query: %s", user_query)
        query_lower = user_query.lower()

        # 2. Deterministic keyword flags --------------------------------------
        rule_flags = _evaluate_rule_flags(query_lower)

        # 3. Data-context summary ---------------------------------------------
        has_data_context, data_context_summary = _build_data_context_summary(
            state.get("data_context")
        )

        # 4. Conversation summary ---------------------------------------------
        conversation_summary = _build_conversation_summary(state["messages"])

        # 5. LLM classification (may raise on network / parsing errors) --------
        try:
            response = await _classify_with_llm(
                user_query, conversation_summary, has_data_context, data_context_summary
            )
        except Exception as llm_err:
            logger.error("LLM classification failed: %s", llm_err, exc_info=True)
            return _build_chat_fallback(f"Router LLM error — falling back to chat: {llm_err}")

        # 6. Merge rule-based overrides ----------------------------------------
        route, analysis_type, requires_simulation = _apply_rule_overrides(
            response.route,
            response.analysis_type,
            response.requires_simulation,
            rule_flags,
            has_data_context,
        )

        # 7. Validation guardrails ---------------------------------------------
        if route not in VALID_ROUTES:
            route = "chat"

        if route == "analysis" and not analysis_type:
            analysis_type = "generic"

        confidence = min(max(response.confidence, 0.0), 1.0)

        # 8. Assemble route decision -------------------------------------------
        route_decision: Dict[str, Any] = {
            "route": route,
            "reasoning": response.reasoning,
            "analysis_type": analysis_type,
            "entity_type": response.entity_type or "generic",
            "requires_chart": response.requires_chart or False,
            "requires_simulation": requires_simulation,
            "confidence": confidence,
        }

        logger.info(
            "=========== Router Decision ===========\n"
            "  Route: %s\n"
            "  Reasoning: %s\n"
            "  Analysis Type: %s\n"
            "  Entity Type: %s\n"
            "  Requires Chart: %s\n"
            "  Requires Simulation: %s\n"
            "  Confidence: %s\n"
            "=======================================",
            route,
            response.reasoning,
            analysis_type,
            response.entity_type,
            response.requires_chart,
            requires_simulation,
            confidence,
        )

        result: Dict[str, Any] = {
            "route_decision": route_decision,
            "user_query": user_query,
        }

        # Inject user_query as a message if it wasn't already in messages
        if not found_in_messages:
            result["messages"] = [HumanMessage(content=user_query)]

        return result

    except Exception as exc:
        # Catch-all: any unexpected error still produces a valid state update
        logger.error("Router node failed unexpectedly: %s", exc, exc_info=True)
        return _build_chat_fallback(f"Router error — falling back to chat: {exc}")
