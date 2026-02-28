"""Pydantic structured-output schemas used by LLM nodes.

Centralised here so they can be:
- Imported in tests without running node logic.
- Reused if any node needs to reference another's schema.
- Maintained in one place when fields are added/removed.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RouterOutput(BaseModel):
    """Structured output schema for the Router node."""

    route: str = Field(
        description="Classification: 'chat', 'analysis', or 'analysis_followup'"
    )
    reasoning: str = Field(description="Explanation for this classification")

    analysis_type: str | None = Field(
        default=None,
        description=(
            "The type of analysis requested (trend_analysis, variance_analysis, "
            "forecast_comparison, anomaly_detection, ranking, simulation, distribution_analysis)"
        ),
    )
    entity_type: str | None = Field(
        default=None,
        description=(
            "The main entity or column being analyzed "
            "(revenue, expense, fund_code, department, generic)"
        ),
    )
    # comparison_dimension: str | None = Field(
    #     default=None,
    #     description=(
    #         "The dimension to compare or pivot across "
    #         "(month, projection_version, scenario, category, none)"
    #     ),
    # )
    requires_chart: bool | None = Field(
        default=None,
        description="Whether a chart or visualization is explicitly requested or naturally fits the query",
    )
    # requires_statistical_metric: bool | None = Field(
    #     default=None,
    #     description="Whether the query requests statistical metrics",
    # )
    requires_simulation: bool | None = Field(
        default=None,
        description="Whether the query requests forecasting, predictive modeling, or what-if simulations",
    )
    confidence: float = Field(
        default=1.0,
        description="Confidence score in the routing decision (0.0 to 1.0)",
    )


class SupervisorOutput(BaseModel):
    """Structured output schema for the Supervisor node."""

    needs_analysis: bool = Field(
        description="True if new code execution needed, False if can answer from context"
    )
    reuse_previous_results: bool = Field(
        description="True if the query can reuse results from the previous analysis"
    )
    scope_changed: bool = Field(
        description="True if the entity scope or type has changed from previous queries"
    )
    entity_mismatch: bool = Field(
        description="True if the requested entity is not found in the dataset profile"
    )
    data_sufficient: bool = Field(
        description="True if the dataset contains the necessary columns for the query"
    )
    reasoning: str = Field(description="Explanation for this decision")


class PlanStep(BaseModel):
    """A single step in the analysis plan."""

    description: str = Field(description="What needs to be done in this step")
    order: int = Field(description="Order of execution (1, 2, 3, ...)")


class PlanOutput(BaseModel):
    """Structured output schema for the Planning node."""

    plan_text: str = Field(description="Human-readable numbered plan")
    steps: List[PlanStep] = Field(
        description="List of structured steps with description and order. Maximum 5 steps.",
        max_length=5,
    )
