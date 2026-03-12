from typing import Annotated, Any, Dict, List, Optional
from typing_extensions import TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph import MessagesState, add_messages


def add_artifacts(left: List["Artifact"], right: List["Artifact"]) -> List["Artifact"]:
    """
    Reducer function to accumulate artifacts without duplicates.

    Appends new artifacts to the existing list, ensuring each 'content'
    is unique (e.g., same plot or table doesn't appear twice).

    Args:
        left: Existing artifacts
        right: New artifacts to add

    Returns:
        Combined list of unique artifacts
    """
    if not left:
        return right
    if not right:
        return left

    # Keep the latest version of the artifact if the content matches
    latest_versions = {}
    for a in left + right:
        if a.get("content"):
            latest_versions[a.get("content")] = a

    # Convert back to list, preserving the original order of appearance
    result = []
    seen = set()
    for a in left + right:
        content = a.get("content")
        if content and content not in seen:
            result.append(latest_versions[content])
            seen.add(content)
    
    return result


def update_analysis_steps(left: List["AnalysisStep"], right: List["AnalysisStep"]) -> List["AnalysisStep"]:
    """
    Reducer function to update analysis steps.

    Merges step updates based on order. If a step with the same order exists,
    it gets updated; otherwise, new steps are appended.

    Args:
        left: Existing steps
        right: New or updated steps

    Returns:
        Updated list of steps
    """
    if not left:
        return right
    if not right:
        return left

    # Create a dictionary from left steps using order as key
    steps_dict = {step.get("order"): step for step in left}

    # Update or add steps from right
    for step in right:
        order = step.get("order")
        if order is not None:
            steps_dict[order] = step

    # Return sorted by order
    return sorted(steps_dict.values(), key=lambda x: x.get("order", 0))


class RouterDecision(TypedDict, total=False):
    """
    Structure for router decisions.

    Attributes:
        route: Where to route ("chat", "analysis", "analysis_followup")
        reasoning: Why this route was chosen
        analysis_type: The type of analysis requested
        entity_type: The main entity or column being analyzed
        comparison_dimension: The dimension to compare or pivot across
        requires_chart: Whether a chart is requested
        requires_statistical_metric: Whether stat metrics are requested
        requires_simulation: Whether a simulation is requested
        confidence: Confidence level in the routing decision
    """
    route: str  # "chat", "analysis", "analysis_followup"
    reasoning: str
    analysis_type: Optional[str]
    entity_type: Optional[str]
    # comparison_dimension: Optional[str]
    requires_chart: Optional[bool]
    # requires_statistical_metric: Optional[bool]
    requires_simulation: Optional[bool]
    confidence: Optional[float]


class SupervisorDecision(TypedDict, total=False):
    """
    Structure for supervisor decisions.

    Attributes:
        needs_analysis: Whether new code execution is needed
        reuse_previous_results: Whether the query can reuse previous results
        scope_changed: Whether the entity scope or type has changed
        entity_mismatch: Whether the requested entity exists in data
        data_sufficient: Whether data contains needed columns
        reasoning: Why this decision was made
    """
    needs_analysis: bool
    reuse_previous_results: bool
    scope_changed: bool
    entity_mismatch: bool
    data_sufficient: bool
    reasoning: str


class Artifact(TypedDict, total=False):
    """
    Structure for storing analysis artifacts (plots, tables, insights).

    Attributes:
        type: Type of artifact ('plot', 'table', 'insight', 'code')
        content: The actual content (file path for plots, markdown for tables, text for insights)
        description: Human-readable description of the artifact
        timestamp: When the artifact was created
    """
    type: str
    content: str
    description: str
    timestamp: str


class AnalysisStep(TypedDict, total=False):
    """
    Structure for tracking individual steps in the analysis plan.

    Attributes:
        description: What needs to be done in this step
        status: Current status ('pending', 'in_progress', 'completed', 'skipped')
        order: Order of execution (1, 2, 3, ...)
        result_summary: Brief summary after completion
    """
    description: str
    status: str
    order: int
    result_summary: str


class ExcelAnalysisState(MessagesState):
    """
    State for the Excel Analysis Agent workflow.

    Extends MessagesState to automatically handle message history with the
    add_messages reducer, while adding custom fields for our use case.

    Attributes:
        messages: List of messages (inherited from MessagesState) - ONLY user queries, plans, final analysis
        excel_file_path: Path to the Excel file being analyzed
        data_context: Structured dict with file info and description generated by Data Inspector
        route_decision: Router's decision on where to route the query
        supervisor_decision: Supervisor's decision on whether analysis is needed
        analysis_plan: Detailed plan of action generated by Planning Node
        user_query: Extracted user query to pass to coding subgraph
        code_iterations: Number of code execution attempts (defaults to 0)
        execution_result: Result from the coding agent's execution (defaults to empty)
        final_analysis: Final analysis output from the coding agent (defaults to empty)
        artifacts: List of analysis artifacts (plots, tables, insights) accumulated across the workflow
        analysis_steps: Structured list of analysis steps with status tracking
    """

    excel_file_path: Optional[str]  # Optional - provided as input parameter
    data_context: Optional[Dict[str, Any]]  # Structured dict with file_path, description, summary
    route_decision: Optional[RouterDecision]  # Router's classification
    supervisor_decision: Optional[SupervisorDecision]  # Supervisor's needs_analysis decision
    analysis_plan: Optional[str]
    user_query: Optional[str]  # Extracted user query for coding subgraph
    code_iterations: int
    execution_result: Optional[str]
    final_analysis: Optional[str]
    artifacts: Annotated[List[Artifact], add_artifacts]
    analysis_steps: Annotated[List[AnalysisStep], update_analysis_steps]


class CodingSubgraphInput(TypedDict, total=False):
    """
    Input state for the Coding Agent Subgraph.

    This defines what data flows FROM parent TO subgraph.
    Intentionally excludes messages to prevent parent messages from entering subgraph.

    Attributes:
        excel_file_path: Path to the Excel file being analyzed
        data_context: Structured dict with file info and description
        analysis_plan: Detailed plan of action to execute
        user_query: The original user query (extracted from parent messages)
        analysis_steps: Structured list of analysis steps with status tracking
    """
    excel_file_path: str
    data_context: Dict[str, Any]  # Structured dict
    analysis_plan: str
    user_query: str
    analysis_steps: List[AnalysisStep]


class CodingSubgraphOutput(TypedDict, total=False):
    """
    Output state for the Coding Agent Subgraph.

    This defines what data flows FROM subgraph TO parent.
    Only includes the final analysis message and artifacts, not tool calls.

    Attributes:
        messages: Only the final analysis message (clean, no tool calls)
        artifacts: List of analysis artifacts (plots, tables, insights)
        analysis_steps: Updated analysis steps with completion status
        final_analysis: Final analysis text
    """
    messages: List
    artifacts: List[Artifact]
    analysis_steps: List[AnalysisStep]
    final_analysis: str


class CodingSubgraphState(TypedDict, total=False):
    """
    Internal state for the Coding Agent Subgraph - ISOLATED from parent.

    This state does NOT extend MessagesState to prevent automatic message merging.
    Messages are handled explicitly with add_messages reducer only within subgraph.
    This ensures tool calls and internal messages stay INSIDE the subgraph.

    Attributes:
        messages: List of internal messages (tool calls, etc.) - NOT merged with parent
        excel_file_path: Path to the Excel file being analyzed
        data_context: Structured dict with file info and description
        analysis_plan: Detailed plan of action to execute
        user_query: The original user query
        code_iterations: Number of code execution attempts (defaults to 0)
        final_analysis: Final analysis output (defaults to empty)
        artifacts: List of analysis artifacts generated during code execution
        analysis_steps: Structured list of analysis steps with status tracking
    """

    messages: Annotated[List[BaseMessage], add_messages]
    excel_file_path: str
    data_context: Dict[str, Any]  # Structured dict
    analysis_plan: str
    user_query: str
    code_iterations: int
    final_analysis: str
    artifacts: Annotated[List[Artifact], add_artifacts]
    analysis_steps: Annotated[List[AnalysisStep], update_analysis_steps]
