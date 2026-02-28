"""Planning node for creating detailed analysis plans."""

import json
import re
from typing import Any, Dict, List, cast

from langchain_core.messages import HumanMessage, SystemMessage

from my_agent.core.config import ModelConfig
from my_agent.core.llm import get_llm
from my_agent.models.schemas import PlanOutput
from my_agent.models.state import ExcelAnalysisState
from my_agent.prompts.prompts import PLANNING_SYS_PROMPT, PLANNING_USER_PROMPT


async def planning_node(state: ExcelAnalysisState) -> Dict[str, Any]:
    """
    Planning Node - Creates a detailed analysis plan.

    This node:
    1. Takes the user query and data context
    2. Uses an LLM to generate a comprehensive analysis plan
    3. Parses structured steps for tracking
    4. Returns the plan for the coding agent

    Args:
        state: Current state containing user query and data_context

    Returns:
        Dictionary with analysis_plan and analysis_steps updates
    """
    print("📋 Planning: Creating analysis plan...")

    try:
        # --------------------------------------------------
        # 1️⃣ Extract Structured Inputs
        # --------------------------------------------------

        user_query = state.get("user_query", "Analyze the data")

        data_context = state.get("data_context")
        if not data_context:
            raise Exception("No data context found in state")

        dataset_profile = data_context.get("dataset_profile", {})
        summary = data_context.get("summary", {})

        route_decision = state.get("route_decision", {})
        if not route_decision:
            raise Exception("No route decision found in state")

        analysis_type = route_decision.get("analysis_type")
        entity_type = route_decision.get("entity_type")
        # comparison_dimension = route_decision.get("comparison_dimension")
        requires_chart = route_decision.get("requires_chart", False)
        # requires_statistical_metric = route_decision.get(
        #     "requires_statistical_metric", False
        # )

        structure_type = dataset_profile.get("structure_type")
        has_scenarios = dataset_profile.get("has_scenarios", False)
        metrics = dataset_profile.get("metrics", [])
        dimensions = dataset_profile.get("dimensions", [])
        semantic_roles = dataset_profile.get("semantic_roles", {})

        # --------------------------------------------------
        # 2️⃣ Build Strategy Hints Dynamically
        # --------------------------------------------------

        strategy_hints: List[str] = []

        # Forecast comparison hint
        if analysis_type == "forecast_comparison":
            strategy_hints.append(
                """
    - Treat scenario dimension as projection version.
    - Pivot entity vs scenario.
    - Compute volatility metrics: range, std deviation, percent change.
    - Rank entities by instability score.
    """
            )

        # Variance / ranking
        if analysis_type in ["variance_analysis", "ranking"]:
            strategy_hints.append(
                """
    - Perform group-by aggregation.
    - Compute contribution %, variance, std deviation.
    - Rank entities based on metric magnitude or dispersion.
    """
            )

        # Trend analysis
        if analysis_type == "trend_analysis":
            strategy_hints.append(
                """
    - Identify true time dimension.
    - Aggregate metric chronologically.
    - Compute growth rates and rolling averages.
    - Visualize time-series line chart.
    """
            )

        # Snapshot structure warning
        if structure_type == "snapshot_based_forecast":
            strategy_hints.append(
                """
    - Dataset is snapshot-based forecast.
    - Do NOT treat scenario labels as chronological time-series.
    - Compare across projection versions instead of rolling trends.
    """
            )

        # Scenario presence
        if has_scenarios:
            strategy_hints.append(
                """
    - Scenario column exists.
    - Consider scenario-based comparisons where relevant.
    """
            )

        # Statistical metric requirement
    #     if requires_statistical_metric:
    #         strategy_hints.append(
    #             """
    # - Include appropriate statistical measures (std deviation, variance, percent change).
    # """
    #         )

        # Chart requirement
        if requires_chart:
            strategy_hints.append(
                """
    - Include appropriate visualization (bar chart, line chart, heatmap as relevant).
    """
            )

        # --------------------------------------------------
        # 3️⃣ Define Strict Structured Output Schema
        # --------------------------------------------------

        # Initialize LLM
        llm = await get_llm(ModelConfig.PLANNING_MODEL, temperature=0)

        # Create prompts
        system_prompt = SystemMessage(content=PLANNING_SYS_PROMPT)
        user_prompt = HumanMessage(
            content=PLANNING_USER_PROMPT.format(
                user_query=user_query,
                data_context=json.dumps(
                    {
                        "user_query": user_query,
                        "analysis_type": analysis_type,
                        "entity_type": entity_type,
                        # "comparison_dimension": comparison_dimension,
                        "dataset_profile": {
                            "structure_type": structure_type,
                            "metrics": metrics,
                            "dimensions": dimensions,
                            "semantic_roles": semantic_roles,
                        },
                        "summary": summary,
                        "strategy_hints": strategy_hints,
                    }
                ),
            )
        )

        # Generate the plan — use function_calling method for broader schema support
        llm_with_structure = llm.with_structured_output(PlanOutput, method="function_calling")
        response_raw = await llm_with_structure.ainvoke([system_prompt, user_prompt])

        if isinstance(response_raw, dict):
            response = PlanOutput(**response_raw)
        else:
            response = cast(PlanOutput, response_raw)

        structured_steps = [
            {
                "description": step.description,
                "status": "pending",
                "order": step.order,
                "result_summary": "",
            }
            for step in response.steps
        ]

        if structured_steps:
            # Hard cap: never allow more than 5 steps regardless of LLM output
            MAX_PLAN_STEPS = 5
            if len(structured_steps) > MAX_PLAN_STEPS:
                print(f"⚠️ Planner generated {len(structured_steps)} steps, truncating to {MAX_PLAN_STEPS}")
                structured_steps = structured_steps[:MAX_PLAN_STEPS]
            print(f"✅ Created {len(structured_steps)} structured analysis steps")
        else:
            print("⚠️ No structured steps found, using text plan only")

        print(f"✅ Planning: Analysis plan created")

        return {"analysis_plan": response.plan_text, "analysis_steps": structured_steps}

    except Exception as e:
        print(f"⚠️ Planning fallback triggered: {e}")

        fallback_plan = """1. Load dataset
2. Perform exploratory analysis
3. Apply relevant aggregations
4. Create necessary visualizations
5. Summarize findings"""

        fallback_steps = [
            {
                "description": "Load dataset",
                "status": "pending",
                "order": 1,
                "result_summary": "",
            },
            {
                "description": "Perform exploratory analysis",
                "status": "pending",
                "order": 2,
                "result_summary": "",
            },
            {
                "description": "Apply relevant aggregations",
                "status": "pending",
                "order": 3,
                "result_summary": "",
            },
            {
                "description": "Create necessary visualizations",
                "status": "pending",
                "order": 4,
                "result_summary": "",
            },
            {
                "description": "Summarize findings",
                "status": "pending",
                "order": 5,
                "result_summary": "",
            },
        ]

        return {"analysis_plan": fallback_plan, "analysis_steps": fallback_steps}
