"""Coding Agent node for executing Python code to analyze Excel data."""

from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from my_agent.core.config import AgentConfig, ModelConfig
from my_agent.core.llm import get_llm
from my_agent.helpers.sandbox import PLOTS_DIR
from my_agent.models.state import CodingSubgraphState
from my_agent.prompts.prompts import CODING_AGENT_SYS_PROMPT, CODING_AGENT_USER_PROMPT
from my_agent.tools.tools import bash_tool, python_repl_tool, think_tool


async def coding_agent_node(state: CodingSubgraphState) -> Dict[str, Any]:
    """
    Coding Agent Node - Executes Python code to perform data analysis.

    This node:
    1. Takes the analysis plan from the supervisor
    2. Uses an LLM with tool-calling to write and execute Python code
    3. Analyzes the results and iterates if needed
    4. Returns the final analysis results

    Args:
        state: Current state containing analysis_plan, data_context, excel_file_path

    Returns:
        Dictionary with execution_result and messages updates
    """
    code_iterations = state.get("code_iterations", 0)
    print(f"💻 Coding Agent: Starting iteration {code_iterations + 1}...")

    # Initialize LLM with tool calling
    llm = await get_llm(ModelConfig.CODING_MODEL, temperature=0)

    # Determine tool_choice strategy:
    # Gemini thinking models may emit text-only responses without calling tools.
    # Force tool_choice="any" until at least one real tool execution has occurred,
    # then switch to "auto" so the model can provide its final analysis.
    # OpenAI and Anthropic models handle tool calling reliably without this workaround.
    tool_choice: Optional[str] = None  # None = provider default ("auto")
    if ModelConfig.CODING_MODEL.startswith("gemini"):
        from langchain_core.messages import ToolMessage
        has_tool_executions = any(
            isinstance(m, ToolMessage) and m.name in ("python_repl_tool", "bash_tool")
            for m in state.get("messages", [])
        )
        tool_choice = "auto" if has_tool_executions else "any"

    # Bind all tools to the LLM: Python REPL, bash (for pip install), and think
    bind_kwargs: dict = {}
    if tool_choice is not None:
        bind_kwargs["tool_choice"] = tool_choice
    llm_with_tools = llm.bind_tools(
        [python_repl_tool, bash_tool, think_tool],
        **bind_kwargs,
    )

    # Prepare the messages
    system_prompt = SystemMessage(content=CODING_AGENT_SYS_PROMPT)

    if code_iterations == 0:
        # First iteration: send system prompt + user query + analysis prompt
        # Include original user query for context
        user_query = state.get("user_query", "Analyze the data")
        user_query_msg = HumanMessage(content=f"User Request: {user_query}")

        # Extract data context description from structured dict
        data_context_dict = state.get("data_context")
        data_context_str = ""
        if isinstance(data_context_dict, dict):
            data_context_str = data_context_dict.get("description", "")
        elif isinstance(data_context_dict, str):
            data_context_str = data_context_dict

        analysis_prompt = HumanMessage(
            content=CODING_AGENT_USER_PROMPT.format(
                analysis_plan=state.get("analysis_plan", ""),
                data_context=data_context_str,
                excel_file_path=state.get("excel_file_path", ""),
                plots_dir=str(PLOTS_DIR),
            )
        )
        messages = [system_prompt, user_query_msg, analysis_prompt]
    else:
        # Subsequent iterations: send system prompt + ALL conversation history
        # This includes previous tool calls, tool results, and reflections
        conversation_history = state.get("messages", [])

        # Build a plan-aware reminder so the LLM doesn't forget remaining steps
        analysis_steps = state.get("analysis_steps", [])
        total_steps = len(analysis_steps)
        estimated_current = min(code_iterations // 2, total_steps)

        if analysis_steps and estimated_current < total_steps:
            remaining = analysis_steps[estimated_current:]
            remaining_text = "\n".join(
                f"  - Step {s.get('order', '?')}: {s.get('description', '')}"
                for s in remaining
            )
            # Calculate budget pressure
            budget_pct = (code_iterations + 1) / AgentConfig.CODING_MAX_ITERATIONS
            urgency = ""
            if budget_pct >= 0.7:
                urgency = (
                    "\n⚠️ BUDGET WARNING: You are using "
                    f"{int(budget_pct * 100)}% of your iteration budget. "
                    "COMBINE all remaining work into ONE code block and finalize."
                )
            hint_content = (
                f"[System: Iteration {code_iterations + 1}/{AgentConfig.CODING_MAX_ITERATIONS}. "
                f"You have completed approximately {estimated_current}/{total_steps} steps.\n"
                f"REMAINING STEPS:\n{remaining_text}\n"
                f"CRITICAL INSTRUCTION: Execute the next step(s). If this is a simple query, execute ALL of the remaining steps in a SINGLE comprehensive code block now. If this is a complex modeling or multi-step analysis where you need to inspect intermediate results before proceeding, you may execute step-by-step.{urgency}]"
            )
        else:
            hint_content = (
                f"[System: Iteration {code_iterations + 1}/{AgentConfig.CODING_MAX_ITERATIONS}. "
                f"All planned steps appear complete. You may now provide your final analysis summary.]"
            )

        iteration_hint = HumanMessage(content=hint_content)
        messages = [system_prompt] + conversation_history + [iteration_hint]

    # Invoke the LLM
    response = await llm_with_tools.ainvoke(messages)

    print("✅ Coding Agent: Received response from LLM")

    # Debug: log what the LLM wants to do
    if hasattr(response, "tool_calls") and response.tool_calls:
        for tc in response.tool_calls:
            print(f"\n{'='*60}")
            print(f"📤 TOOL CALL: {tc['name']}")
            if tc['name'] == 'python_repl_tool':
                code = tc['args'].get('code', '')
                code_lines = code.splitlines()
                code_print = '\n'.join(code_lines[:10]) + '\n... (code truncated)' if len(code_lines) > 10 else code
                print(f"📝 CODE:\n{code_print}")
            elif tc['name'] == 'bash_tool':
                print(f"📝 COMMAND: {tc['args'].get('command', '')}")
            elif tc['name'] == 'think_tool':
                thought = tc['args'].get('reflection', '')
                print(f"💭 THOUGHT: {thought[:300]}")
            print(f"{'='*60}")
    elif response.content:
        print(f"\n{'='*60}")
        print(f"📄 LLM RESPONSE (no tool calls):")
        print(f"{response.content[:500]}")
        print(f"{'='*60}")

    # Add the response to messages.
    # On the first iteration we also persist the initial user messages so that
    # subsequent iterations have the complete conversation context.  Without this,
    # the conversation history would start with an AIMessage which violates
    # Gemini's requirement that function-call turns follow user/tool-response turns.
    if code_iterations == 0:
        return {
            "messages": [user_query_msg, analysis_prompt, response],
            "code_iterations": state.get("code_iterations", 0) + 1,
        }
    return {
        "messages": [response],
        "code_iterations": state.get("code_iterations", 0) + 1,
    }


async def tool_execution_node(state: CodingSubgraphState) -> Dict[str, Any]:
    """
    Tool Execution Node - Executes the tools called by the coding agent.

    This node:
    1. Extracts tool calls from the last AI message
    2. Executes each tool call asynchronously (runs blocking code in thread pool)
    3. Returns the results as tool messages

    Args:
        state: Current state containing messages with tool calls

    Returns:
        Dictionary with messages containing tool results
    """
    from langchain_core.messages import ToolMessage
    import json

    print("🔧 Tool Execution: Executing tool calls...")

    # Get the last message (should be from the coding agent with tool calls)
    last_message = state["messages"][-1]

    # Check if there are tool calls
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        print("⚠️ No tool calls found in the last message")
        return {"messages": []}

    tool_messages = []

    # Execute each tool call
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_call_id = tool_call["id"]

        print(f"🔧 Executing tool: {tool_name}")

        # Execute the appropriate tool asynchronously
        if tool_name == "python_repl_tool":
            # Use ainvoke to run the blocking exec() call in a thread pool
            result = await python_repl_tool.ainvoke(tool_args)

            # Create a tool message with the result — use json.dumps so
            # finalize_analysis_node can parse it back with json.loads
            tool_message = ToolMessage(
                content=json.dumps(result, default=str),
                tool_call_id=tool_call_id,
                name=tool_name,
            )
            tool_messages.append(tool_message)

            # Store execution result in state
            if result.get("success"):
                output = result.get('output', '')
                plots = result.get('plots', [])
                tables = result.get('tables', [])
                print(f"✅ Tool execution successful")
                if output:
                    out_lines = output.splitlines()
                    out_print = '\n'.join(out_lines[:10]) + '\n... (output truncated)' if len(out_lines) > 10 else output
                    print(f"📊 OUTPUT:\n{out_print}")
                if plots:
                    print(f"🖼️  PLOTS SAVED: {plots}")
                if tables:
                    print(f"📋 TABLES DETECTED: {[t.get('name', '?') for t in tables]}")
            else:
                print(f"❌ Tool execution failed: {result.get('error', '')[:500]}")

        elif tool_name == "bash_tool":
            # Execute bash_tool for package installation
            result = await bash_tool.ainvoke(tool_args)

            # Create a tool message with the result
            tool_message = ToolMessage(
                content=json.dumps(result, default=str),
                tool_call_id=tool_call_id,
                name=tool_name,
            )
            tool_messages.append(tool_message)

            # Log installation result
            if result.get("success"):
                print("✅ Bash command executed successfully")
            else:
                print(f"❌ Bash command failed: {result.get('error')}")

        elif tool_name == "think_tool":
            # Execute think_tool for reflection (lightweight, no need for thread pool)
            result = await think_tool.ainvoke(tool_args)

            # Create a tool message with the result
            tool_message = ToolMessage(
                content=str(result),
                tool_call_id=tool_call_id,
                name=tool_name,
            )
            tool_messages.append(tool_message)
            print("✅ Reflection recorded")

    return {"messages": tool_messages}


def should_continue_coding(state: CodingSubgraphState) -> str:
    """
    Routing function to determine if coding agent should continue or finish.

    Checks if:
    1. The last message has tool calls (continue to tool execution)
    2. Maximum iterations reached (end) - soft limit, agent should self-regulate
    3. No tool calls and valid response (end)

    Args:
        state: Current state

    Returns:
        "execute_tools" if there are tool calls to execute
        "finalize" if the coding is complete
        "continue" if the agent should continue reasoning
    """
    last_message = state["messages"][-1]
    max_iterations = AgentConfig.CODING_MAX_ITERATIONS
    current_iteration = state.get("code_iterations", 0)

    print(f"🔀 Routing: Iteration {current_iteration}/{max_iterations}")

    # Hard safety limit - only trigger if agent isn't self-regulating
    if current_iteration >= max_iterations:
        print("⚠️ Maximum safety limit reached, forcing finalization...")
        return "finalize"

    # Soft warning if taking too long
    if current_iteration >= AgentConfig.CODING_SOFT_WARNING:
        print("⚠️ Notice: High iteration count - consider if analysis can be completed")

    # Check if the last message has tool calls
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        num_tool_calls = len(last_message.tool_calls)
        tool_names = [tc["name"] for tc in last_message.tool_calls]
        print(f"🔧 Found {num_tool_calls} tool call(s): {tool_names}")
        return "execute_tools"

    # If it's an AI message without tool calls, it's likely the final analysis
    if isinstance(last_message, AIMessage):
        # Guard: don't finalize if no real work (tool executions) has been done yet.
        # Gemini thinking models may emit a text-only planning response before
        # calling tools, which would otherwise cause premature finalization.
        from langchain_core.messages import ToolMessage
        tool_executions = [
            m for m in state["messages"]
            if isinstance(m, ToolMessage) and m.name in ("python_repl_tool", "bash_tool")
        ]
        if not tool_executions and current_iteration < 3:
            print("⚠️ No tool calls AND no prior tool executions — re-prompting agent...")
            return "continue"

        print("✅ No tool calls found, finalizing analysis...")
        return "finalize"

    # Otherwise, continue
    print("🔄 Continuing to coding agent...")
    return "continue"


async def finalize_analysis_node(state: CodingSubgraphState) -> Dict[str, Any]:
    """
    Finalize Analysis Node - Creates the final analysis summary with structured artifacts.

    This node:
    1. Reviews all execution results and extracts findings
    2. Collects all artifacts (plots, tables, code) from tool executions
    3. Creates a comprehensive structured analysis
    4. Returns artifacts and clean message for the parent graph

    Args:
        state: Current state with all execution history

    Returns:
        Dictionary with final_analysis, artifacts, and a clean message for parent
    """
    from datetime import datetime
    from langchain_core.messages import ToolMessage

    print("📝 Finalizing analysis and extracting artifacts...")

    # Collect all artifacts from tool executions
    artifacts = []
    tool_messages = [
        msg for msg in state["messages"]
        if isinstance(msg, ToolMessage) and msg.name == "python_repl_tool"
    ]

    # Extract plots and tables from tool executions
    for tool_msg in tool_messages:
        try:
            import json as json_mod
            # Tool messages contain dict as string, parse it
            content_str = str(tool_msg.content)
            result_dict = json_mod.loads(content_str)

            # Add plots as artifacts
            if result_dict.get("plots"):
                for plot_path in result_dict["plots"]:
                    from pathlib import Path as _P
                    artifacts.append({
                        "type": "plot",
                        "content": plot_path,
                        "description": f"Generated plot: {_P(plot_path).name}",
                        "timestamp": datetime.now().isoformat()
                    })

            # Add tables as artifacts
            if result_dict.get("tables"):
                for table in result_dict["tables"]:
                    artifacts.append({
                        "type": "table",
                        "content": table["markdown"],
                        "description": f"DataFrame '{table['name']}' (shape: {table['shape']})",
                        "timestamp": datetime.now().isoformat()
                    })
        except Exception as e:
            print(f"⚠️  Could not parse tool message for artifacts: {e}")
            print(f"    Raw content (first 200 chars): {str(tool_msg.content)[:200]}")
            continue

    # Get the last AI message which should contain the final analysis text
    ai_messages = [msg for msg in state["messages"] if isinstance(msg, AIMessage)]

    if ai_messages and ai_messages[-1].content:
        final_analysis_text = ai_messages[-1].content
        print(f"✅ Analysis finalized: {len(final_analysis_text)} characters")
    else:
        # Try earlier AI messages with content (thinking models may leave last msg empty)
        content_msgs = [m for m in ai_messages if m.content]
        if content_msgs:
            final_analysis_text = content_msgs[-1].content
            print(f"✅ Analysis finalized from earlier AI message: {len(final_analysis_text)} characters")
        else:
            # Fallback: compile from tool execution results
            print("⚠️ No AI message found, compiling from execution history...")

            if tool_messages:
                final_analysis_text = "## Analysis Results\n\n"
                for i, msg in enumerate(tool_messages[-3:], 1):  # Last 3 executions
                    final_analysis_text += f"### Execution {i}\n{msg.content}\n\n"
            else:
                final_analysis_text = "Analysis completed but no results were captured."

    # Add insights as an artifact
    artifacts.append({
        "type": "insight",
        "content": final_analysis_text,
        "description": "Final analysis and findings",
        "timestamp": datetime.now().isoformat()
    })

    print(f"\n{'='*60}")
    print(f"📊 FINALIZE: Extracted {len(artifacts)} artifacts total")
    for a in artifacts:
        print(f"   {a['type'].upper()}: {a['description']}")
    print(f"{'='*60}")

    from pathlib import Path

    # Ensure final_analysis_text is a string
    final_analysis_str = str(final_analysis_text) if final_analysis_text else "Analysis completed."
    message_content = final_analysis_str + "\n\n"

    # # List plot file paths (plots are saved locally, no base64 embedding)
    # plot_artifacts = [a for a in artifacts if a["type"] == "plot"]
    # if plot_artifacts:
    #     message_content += "## 📊 Generated Plots\n\n"
    #     message_content += "Plots have been saved locally:\n\n"

    #     for plot_artifact in plot_artifacts:
    #         plot_path = plot_artifact["content"]
    #         plot_name = Path(plot_path).name
    #         message_content += f"- **{plot_name}**: `{plot_path}`\n"

    #     message_content += "\n"

    # # Add tables as markdown
    # table_artifacts = [a for a in artifacts if a["type"] == "table"]
    # if table_artifacts:
    #     message_content += "## 📋 Data Tables\n\n"
    #     for table_artifact in table_artifacts:
    #         message_content += f"### {table_artifact['description']}\n\n"
    #         message_content += table_artifact["content"] + "\n\n"

    # Create AI message with plot references and tables
    final_message = AIMessage(content=message_content, name="CodingAgent")

    return {
        "final_analysis": message_content,
        "artifacts": artifacts,  # Return artifacts to be merged into parent state
        "messages": [final_message],  # This clean message with embedded images goes to parent
    }
