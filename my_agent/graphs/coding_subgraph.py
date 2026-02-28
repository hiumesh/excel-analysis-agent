"""Coding Agent Subgraph - Handles code execution and iteration."""

from langgraph.graph import END, StateGraph

from my_agent.models.state import (
    CodingSubgraphInput,
    CodingSubgraphOutput,
    CodingSubgraphState,
)
from my_agent.nodes.coding_agent import (
    coding_agent_node,
    finalize_analysis_node,
    should_continue_coding,
    tool_execution_node,
)


def create_coding_subgraph():
    """
    Create the Coding Agent subgraph with properly isolated state.

    This subgraph uses:
    - CodingSubgraphInput: Controls what flows FROM parent TO subgraph (no messages)
    - CodingSubgraphState: Internal state with ALL messages including tool calls
    - CodingSubgraphOutput: Controls what flows FROM subgraph TO parent (only final message)

    This ensures:
    - Parent graph messages DON'T enter the subgraph
    - Tool calls and internal messages stay INSIDE the subgraph
    - Only the clean final analysis message flows back to parent

    Workflow:
    1. Coding Agent generates code and decides to use tools
    2. Tools are executed (messages stay in subgraph)
    3. Results are fed back to the Coding Agent (internal loop)
    4. Process repeats until analysis is complete or max iterations reached
    5. Final analysis is compiled and sent to parent graph

    The subgraph uses conditional routing to handle:
    - Tool execution when the agent calls tools
    - Continuation when more reasoning is needed
    - Finalization when the analysis is complete

    Returns:
        Compiled LangGraph subgraph for coding agent with input/output schemas
    """
    # Initialize the subgraph with isolated state
    workflow = StateGraph(CodingSubgraphState, input=CodingSubgraphInput, output=CodingSubgraphOutput)

    # Add nodes
    workflow.add_node("coding_agent", coding_agent_node)
    workflow.add_node("execute_tools", tool_execution_node)
    workflow.add_node("finalize", finalize_analysis_node)

    # Set entry point
    workflow.set_entry_point("coding_agent")

    # Add conditional routing from coding_agent
    workflow.add_conditional_edges(
        "coding_agent",
        should_continue_coding,
        {
            "execute_tools": "execute_tools",
            "finalize": "finalize",
            "continue": "coding_agent",
        },
    )

    # After tool execution, go back to coding agent for next iteration
    workflow.add_edge("execute_tools", "coding_agent")

    # After finalization, end the subgraph
    workflow.add_edge("finalize", END)

    # Compile with input/output schemas for proper state isolation.
    # CodingSubgraphInput excludes messages — parent messages won't enter.
    # CodingSubgraphOutput only includes final_analysis, artifacts, analysis_steps,
    # and messages (the clean final message) — tool calls stay inside.
    return workflow.compile()
