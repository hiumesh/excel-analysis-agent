"""Python REPL tool for code execution in the Excel Analysis Agent."""

from typing import Any, Dict

from langchain_core.tools import tool

from my_agent.helpers.sandbox_client import (
    execute_code_via_server,
    install_package_via_server,
    reset_context_via_server,
)


async def reset_execution_context():
    """Reset the execution context in the sandbox server."""
    await reset_context_via_server()


@tool(parse_docstring=True)
def think_tool(reflection: str) -> str:
    """Tool for strategic reflection on code execution progress and decision-making.

    Use this tool after each code execution to analyze results and plan next steps systematically.
    This creates a deliberate pause in the coding workflow for quality decision-making.

    When to use:
    - After receiving code execution results: What did the code produce? Was it successful?
    - After encountering errors: What went wrong? How can I fix it?
    - Before deciding next steps: Do I need to write more code or is the analysis complete?
    - When assessing progress: Have I addressed all steps in the analysis plan?
    - Before concluding: Can I provide a comprehensive final analysis now?

    Reflection should address:
    1. Analysis of current results - What did the code output? Were there any errors?
    2. Gap assessment - What parts of the analysis plan are still incomplete?
    3. Quality evaluation - Do I have sufficient data/insights for a good answer?
    4. Strategic decision - Should I continue coding, fix errors, or finalize the analysis?

    Args:
        reflection: Your detailed reflection on code execution progress, findings, errors, and next steps

    Returns:
        Confirmation that reflection was recorded for decision-making
    """

    return f"Reflection recorded: {reflection}"


@tool
async def python_repl_tool(reasoning: str, code: str) -> Dict[str, Any]:
    """
    Execute Python code in a sandboxed environment with persistent context.

    This tool executes Python code via HTTP request to a sandbox server running
    in a separate process. The execution context persists across multiple calls,
    allowing variables, DataFrames, and imports to be reused.

    The sandbox has the following libraries pre-installed:
    - Data: pandas, numpy, openpyxl
    - Visualization: matplotlib, seaborn
    - Statistics & ML: scipy, statsmodels, scikit-learn
    - Utilities: tabulate, python-dateutil

    The tool automatically:
    - Detects and saves matplotlib plots to disk
    - Formats pandas DataFrames as markdown tables
    - Returns structured output for creating artifacts

    Args:
        reasoning: A brief, natural language explanation of WHY you are writing this code and what it achieves.
        code: Python code to execute. Should be valid Python code that can include
              imports, variable assignments, data processing, and print statements.
              Variables and imports persist across calls within the same session.

    Returns:
        Dictionary containing:
            - success: Boolean indicating if execution was successful
            - output: Captured stdout from the code execution
            - error: Error message if execution failed, None otherwise
            - plots: List of saved plot file paths
            - tables: List of formatted markdown tables with descriptions

    Example:
        >>> await python_repl_tool("Initializing simple dataframe.", "import pandas as pd\\ndf = pd.DataFrame({'a': [1, 2, 3]})")
        {'success': True, 'output': '', 'error': None, 'plots': [], 'tables': []}
    """
    return await execute_code_via_server(code)


@tool
async def bash_tool(reasoning: str, command: str) -> Dict[str, Any]:
    """
    Execute bash commands in the sandbox environment, primarily for installing packages.

    This tool allows you to install Python packages in the sandbox environment
    via HTTP request to the sandbox server without affecting the main application.

    Common use cases:
    - Install additional Python packages: "pip install statsmodels"
    - Install specific versions: "pip install scikit-learn==1.3.0"
    - Install multiple packages: "pip install seaborn scipy"

    Args:
        reasoning: A brief explanation of WHY you are running this command (e.g. what package is needed).
        command: Bash command to execute. Currently supports pip install commands.

    Returns:
        Dictionary containing:
            - success: Boolean indicating if command was successful
            - output: Command output
            - error: Error message if command failed, None otherwise

    Example:
        >>> await bash_tool("Need statsmodels for regression analysis.", "pip install statsmodels")
        {'success': True, 'output': 'Successfully installed statsmodels...', 'error': None}
    """
    import re

    # Only allow pip install commands
    if not command.strip().startswith("pip install"):
        return {
            "success": False,
            "output": "",
            "error": "Only 'pip install' commands are supported in the sandbox. Example: pip install statsmodels"
        }

    parts = command.strip().split()
    if len(parts) < 3:
        return {
            "success": False,
            "output": "",
            "error": "Invalid pip install command. Usage: pip install <package_name>"
        }

    # Validate each package name to prevent command injection
    # Allow: letters, digits, hyphens, underscores, dots, brackets, version specifiers
    package_pattern = re.compile(r'^[a-zA-Z0-9._\-\[\]>=<!]+$')
    package_names = parts[2:]

    for pkg in package_names:
        if not package_pattern.match(pkg):
            return {
                "success": False,
                "output": "",
                "error": f"Invalid package name '{pkg}'. Only alphanumeric characters, hyphens, underscores, dots, and version specifiers are allowed."
            }

    package_spec = " ".join(package_names)
    return await install_package_via_server(package_spec)
