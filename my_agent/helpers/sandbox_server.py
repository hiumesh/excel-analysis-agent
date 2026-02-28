"""FastAPI server for sandboxed Python code execution.

This server runs in a separate process and maintains execution contexts
for multiple sessions. Tool calls from the main application are HTTP requests.

Run this server in a separate terminal:
    python -m my_agent.helpers.sandbox_server

The server will run on http://localhost:8765
"""

import sys
import traceback
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from my_agent.helpers.sandbox import (
    PLOTS_DIR,
    SANDBOX_DIR,
    TABLES_DIR,
    VENV_DIR,
    ensure_sandbox_exists,
    get_pip_executable,
)

# CRITICAL: Add venv site-packages to sys.path so exec() can find installed packages
# This ensures packages installed via pip in the venv are available during code execution
if sys.platform == "win32":
    venv_site_packages = VENV_DIR / "Lib" / "site-packages"
else:
    import sysconfig
    python_version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    venv_site_packages = VENV_DIR / "lib" / python_version / "site-packages"

if venv_site_packages.exists():
    sys.path.insert(0, str(venv_site_packages))
    print(f"✅ Added venv site-packages to sys.path: {venv_site_packages}")
else:
    print(f"⚠️  Warning: venv site-packages not found at {venv_site_packages}")

# Ensure sandbox exists on startup
if not ensure_sandbox_exists():
    print("❌ Failed to initialize sandbox environment!")
    sys.exit(1)

# In-memory storage for session execution contexts
SESSION_CONTEXTS: Dict[str, Dict[str, Any]] = {}

app = FastAPI(title="Sandbox Execution Server")


class ExecuteRequest(BaseModel):
    code: str
    session_id: str = "default"


class InstallRequest(BaseModel):
    package_name: str


class ResetRequest(BaseModel):
    session_id: str = "default"


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "sandbox_dir": str(SANDBOX_DIR),
        "active_sessions": len(SESSION_CONTEXTS),
    }


@app.post("/execute")
async def execute_code(request: ExecuteRequest) -> Dict[str, Any]:
    """
    Execute Python code in the sandbox environment with persistent session state.

    Args:
        request: Contains code to execute and session_id

    Returns:
        Dictionary with success, output, error, plots, and tables
    """
    session_id = request.session_id
    code = request.code

    # Get or create session context
    if session_id not in SESSION_CONTEXTS:
        SESSION_CONTEXTS[session_id] = {
            # Inject plots_dir as a pre-defined variable so agent can use it directly
            "plots_dir": str(PLOTS_DIR),
        }
        print(f"📝 Created new session: {session_id}")

    execution_context = SESSION_CONTEXTS[session_id]

    # Ensure plots directory exists
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    # Snapshot existing plot files BEFORE execution so we can detect new ones
    existing_plots = set(PLOTS_DIR.glob("*.*"))

    # Force matplotlib to use non-GUI backend
    try:
        import matplotlib
        matplotlib.use("Agg")
    except ImportError:
        pass

    # Suppress non-interactive warning globally (covers exec threads too)
    import warnings
    warnings.filterwarnings("ignore", message=".*FigureCanvasAgg.*non-interactive.*")
    warnings.filterwarnings("ignore", message=".*Matplotlib.*non-GUI.*")

    # Capture stdout
    old_stdout = sys.stdout
    redirected_output = StringIO()
    sys.stdout = redirected_output

    plots_saved = []
    tables_found = []

    try:
        import asyncio

        if "__builtins__" not in execution_context:
            execution_context["__builtins__"] = __builtins__

        # Wrap exec in asyncio.to_thread to avoid blocking the event loop
        await asyncio.to_thread(
            exec, code, execution_context
        )

        # Get captured output
        output = redirected_output.getvalue()

        # Auto-save any open matplotlib figures that the agent didn't save explicitly
        try:
            import matplotlib.pyplot as plt

            open_figs = plt.get_fignums()
            if open_figs:
                for fig_num in open_figs:
                    fig = plt.figure(fig_num)
                    # Generate a unique filename
                    fig_label = fig.get_label() or f"figure_{fig_num}"
                    # Sanitize the label for use as filename
                    safe_label = "".join(c if c.isalnum() or c in "._-" else "_" for c in fig_label)
                    plot_path = PLOTS_DIR / f"{safe_label}.png"
                    # Only auto-save if NOT already saved to PLOTS_DIR by the agent's code
                    if not plot_path.exists():
                        fig.savefig(str(plot_path), dpi=150, bbox_inches="tight")
                        print(f"📊 Auto-saved figure {fig_num} → {plot_path}")
                # Close all figures to free memory
                plt.close("all")
        except ImportError:
            pass
        except Exception as e:
            print(f"Warning: Could not auto-save matplotlib figures: {e}")

        # Detect ALL new plot files created during execution (both agent-saved and auto-saved)
        current_plots = set(PLOTS_DIR.glob("*.*"))
        new_plots = current_plots - existing_plots
        plots_saved = [str(p) for p in sorted(new_plots)]

        if plots_saved:
            print(f"🖼️  Detected {len(plots_saved)} new plot(s): {[Path(p).name for p in plots_saved]}")

        # Auto-detect and format pandas DataFrames, save to TABLES_DIR
        try:
            import pandas as pd

            TABLES_DIR.mkdir(parents=True, exist_ok=True)

            for var_name, var_value in execution_context.items():
                if isinstance(var_value, pd.DataFrame) and not var_name.startswith("_"):
                    if len(var_value) <= 100:
                        markdown_table = var_value.to_markdown(index=True)
                        tables_found.append(
                            {
                                "name": var_name,
                                "markdown": markdown_table,
                                "shape": var_value.shape,
                            }
                        )

                        # Save table to disk as CSV and Markdown
                        csv_path = TABLES_DIR / f"{var_name}.csv"
                        md_path = TABLES_DIR / f"{var_name}.md"
                        var_value.to_csv(str(csv_path), index=True)
                        with open(str(md_path), "w", encoding="utf-8") as f:
                            f.write(f"# {var_name}\n\n")
                            f.write(markdown_table)
                        print(f"📋 Saved table '{var_name}' → {csv_path.name}, {md_path.name}")

        except ImportError:
            pass
        except Exception as e:
            print(f"Warning: Could not format DataFrames: {e}")

        # Get final output
        output = redirected_output.getvalue()

        # Restore stdout
        sys.stdout = old_stdout

        return {
            "success": True,
            "output": output,
            "error": None,
            "plots": plots_saved,
            "tables": tables_found,
        }

    except Exception as e:
        sys.stdout = old_stdout
        error_msg = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
        output = redirected_output.getvalue()

        return {
            "success": False,
            "output": output,
            "error": error_msg,
            "plots": plots_saved,
            "tables": tables_found,
        }


@app.post("/install")
async def install_package(request: InstallRequest) -> Dict[str, Any]:
    """
    Install a Python package in the sandbox environment.

    Args:
        request: Contains package_name to install

    Returns:
        Dictionary with success status and output/error messages
    """
    package_name = request.package_name

    try:
        print(f"📦 Installing {package_name} in sandbox...")
        import asyncio
        import subprocess

        # Wrap blocking subprocess.run in asyncio.to_thread to avoid blocking the event loop
        result = await asyncio.to_thread(
            subprocess.run,
            [get_pip_executable(), "install", package_name],
            capture_output=True,
            text=True,
            timeout=120,  # 2 minute timeout
        )

        if result.returncode == 0:
            print(f"✅ Successfully installed {package_name}")
            return {"success": True, "output": result.stdout, "error": None}
        else:
            print(f"❌ Failed to install {package_name}")
            return {"success": False, "output": result.stdout, "error": result.stderr}

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "output": "",
            "error": f"Installation of {package_name} timed out after 120 seconds",
        }
    except Exception as e:
        return {
            "success": False,
            "output": "",
            "error": f"Error installing {package_name}: {str(e)}",
        }


@app.post("/reset")
async def reset_session(request: ResetRequest):
    """Reset the execution context for a session."""
    session_id = request.session_id

    if session_id in SESSION_CONTEXTS:
        # Re-initialize with pre-defined variables
        SESSION_CONTEXTS[session_id] = {
            "plots_dir": str(PLOTS_DIR),
        }
        print(f"🔄 Reset session: {session_id}")
        return {"success": True, "message": f"Session {session_id} reset successfully"}
    else:
        return {
            "success": True,
            "message": f"Session {session_id} did not exist (nothing to reset)",
        }


@app.get("/sessions")
async def list_sessions():
    """List all active sessions."""
    return {
        "sessions": list(SESSION_CONTEXTS.keys()),
        "count": len(SESSION_CONTEXTS),
    }


if __name__ == "__main__":
    import uvicorn

    print("=" * 70)
    print("🚀 Starting Sandbox Execution Server")
    print("=" * 70)
    print()
    print(f"Sandbox directory: {SANDBOX_DIR}")
    print(f"Plots directory: {PLOTS_DIR}")
    print(f"Tables directory: {TABLES_DIR}")
    print()
    print("Server will run on: http://localhost:8765")
    print()
    print("Endpoints:")
    print("  POST /execute  - Execute Python code")
    print("  POST /install  - Install Python package")
    print("  POST /reset    - Reset session context")
    print("  GET  /health   - Health check")
    print("  GET  /sessions - List active sessions")
    print()
    print("=" * 70)
    print()

    uvicorn.run(app, host="localhost", port=8765, log_level="info")
