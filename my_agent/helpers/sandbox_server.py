"""FastAPI server for sandboxed Python code execution.

This server runs in a separate process and maintains execution contexts
for multiple sessions. Tool calls from the main application are HTTP requests.

Run this server in a separate terminal:
    python -m my_agent.helpers.sandbox_server

The server will run on http://localhost:8765
"""

import asyncio
import io
import shutil
import sys
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from my_agent.helpers.sandbox import (
    SANDBOX_DIR,
    VENV_DIR,
    ensure_sandbox_exists,
    get_pip_executable,
    get_session_plots_dir,
    get_session_tables_dir,
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
# Track last activity time per session (epoch seconds)
SESSION_LAST_ACTIVE: Dict[str, float] = {}

# Cleanup configuration
SESSION_TTL_MINUTES: int = 30        # Sessions inactive for this long are removed
CLEANUP_INTERVAL_SECONDS: int = 300  # Run cleanup every 5 minutes

# Background file preload cache: key = "session_id::file_path", value = DataFrame
PRELOAD_CACHE: Dict[str, Any] = {}
# Shared preload cache for default/common files — never evicted by session reset
# key = absolute file_path, value = DataFrame
SHARED_PRELOAD: Dict[str, Any] = {}
_preload_lock = threading.Lock()

app = FastAPI(title="Sandbox Execution Server")


def _sync_preload_default():
    """Eagerly load the default data source at startup (blocking, runs once)."""
    default_source = str(Path("data/source.csv").absolute())
    if not Path(default_source).exists():
        print(f"⚠️  Default source file not found: {default_source} — skipping preload")
        return

    import pandas as pd
    try:
        if default_source.lower().endswith(".csv"):
            df = pd.read_csv(default_source)
        else:
            df = pd.read_excel(default_source)
        SHARED_PRELOAD[default_source] = df
        print(f"✅ Default file preloaded at startup: {default_source} ({len(df)} rows)")
    except Exception as e:
        print(f"❌ Failed to preload default file: {e}")


def _cleanup_session(session_id: str) -> None:
    """Remove a single session: context, preload cache entries, and on-disk files."""
    # 1. Remove in-memory state
    SESSION_CONTEXTS.pop(session_id, None)
    SESSION_LAST_ACTIVE.pop(session_id, None)

    # 2. Evict preload cache entries
    with _preload_lock:
        keys = [k for k in PRELOAD_CACHE if k.startswith(f"{session_id}::")]
        for k in keys:
            del PRELOAD_CACHE[k]

    # 3. Delete on-disk session directory (plots, tables)
    from my_agent.helpers.sandbox import get_session_dir
    session_dir = get_session_dir(session_id)
    if session_dir.exists():
        shutil.rmtree(str(session_dir), ignore_errors=True)

    print(f"🗑️  Cleaned up session: {session_id}")


async def _session_cleanup_worker():
    """Background task that periodically removes inactive sessions."""
    print(f"🧹 Session cleanup worker started (TTL={SESSION_TTL_MINUTES}min, interval={CLEANUP_INTERVAL_SECONDS}s)")
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
        now = time.time()
        ttl_seconds = SESSION_TTL_MINUTES * 60
        expired = [
            sid for sid, last in list(SESSION_LAST_ACTIVE.items())
            if (now - last) > ttl_seconds
        ]
        if expired:
            print(f"🧹 Cleaning {len(expired)} inactive session(s): {expired}")
            for sid in expired:
                _cleanup_session(sid)
        # Also report stats periodically
        print(
            f"📊 Sessions: {len(SESSION_CONTEXTS)} active, "
            f"{len(PRELOAD_CACHE)} preloaded, "
            f"{len(SHARED_PRELOAD)} shared"
        )


@app.on_event("startup")
async def startup_tasks():
    """Preload default data source and start the cleanup worker."""
    _sync_preload_default()
    asyncio.create_task(_session_cleanup_worker())


class ExecuteRequest(BaseModel):
    code: str
    session_id: str = "default"


class InstallRequest(BaseModel):
    package_name: str


class ResetRequest(BaseModel):
    session_id: str = "default"


class PreloadRequest(BaseModel):
    file_path: str
    session_id: str = "default"
    shared: bool = False  # If True, store in SHARED_PRELOAD (reused across all sessions)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "sandbox_dir": str(SANDBOX_DIR),
        "active_sessions": len(SESSION_CONTEXTS),
        "preloaded_files": len(PRELOAD_CACHE),
    }


@app.post("/preload", status_code=202)
async def preload_file(request: PreloadRequest) -> Dict[str, Any]:
    """Start background file loading into the preload cache.

    Returns 202 immediately while the file loads in a background thread.
    The cached DataFrame will be injected into execution contexts automatically.

    If ``shared=True``, the file is stored in SHARED_PRELOAD and reused by
    every session that uses the same file path (ideal for the default source).
    """
    abs_path = str(Path(request.file_path).absolute())

    # Always record the file path in the session context so `/execute`
    # can look it up in SHARED_PRELOAD even if this preload is a no-op.
    if request.session_id not in SESSION_CONTEXTS:
        session_plots_dir = get_session_plots_dir(request.session_id)
        SESSION_CONTEXTS[request.session_id] = {
            "plots_dir": str(session_plots_dir),
            "__file_path": abs_path,
        }
    else:
        SESSION_CONTEXTS[request.session_id]["__file_path"] = abs_path

    # Track activity for cleanup worker
    SESSION_LAST_ACTIVE[request.session_id] = time.time()

    # Check if already in the shared cache
    if abs_path in SHARED_PRELOAD:
        return {"status": "already_cached_shared", "file_path": abs_path}

    cache_key = f"{request.session_id}::{abs_path}"

    with _preload_lock:
        if cache_key in PRELOAD_CACHE:
            return {"status": "already_cached", "cache_key": cache_key}

    def _load():
        try:
            import pandas as pd

            if abs_path.lower().endswith(".csv"):
                df = pd.read_csv(abs_path)
            else:
                df = pd.read_excel(abs_path)

            with _preload_lock:
                if request.shared:
                    SHARED_PRELOAD[abs_path] = df
                    print(f"✅ Preloaded (shared) {abs_path} ({len(df)} rows)")
                else:
                    PRELOAD_CACHE[cache_key] = df
                    print(f"✅ Preloaded {abs_path} ({len(df)} rows) for session {request.session_id}")
        except Exception as e:
            print(f"❌ Preload failed for {abs_path}: {e}")

    threading.Thread(target=_load, daemon=True).start()
    return {"status": "loading", "cache_key": cache_key}


@app.post("/execute")
async def execute_code(request: ExecuteRequest) -> Dict[str, Any]:
    """
    Execute Python code in the sandbox environment with persistent session state.

    Each session gets its own plots/tables directories and isolated stdout capture.

    Args:
        request: Contains code to execute and session_id

    Returns:
        Dictionary with success, output, error, plots, and tables
    """
    session_id = request.session_id
    code = request.code

    # Per-session artifact directories
    session_plots_dir = get_session_plots_dir(session_id)
    session_tables_dir = get_session_tables_dir(session_id)

    # Get or create session context
    if session_id not in SESSION_CONTEXTS:
        SESSION_CONTEXTS[session_id] = {
            # Inject session-scoped plots_dir so agent code can use it directly
            "plots_dir": str(session_plots_dir),
            "__file_path": "",  # Will be set by preload hints
        }
        print(f"📝 Created new session: {session_id}")

    # Track activity for cleanup worker
    SESSION_LAST_ACTIVE[session_id] = time.time()

    execution_context = SESSION_CONTEXTS[session_id]
    # Always ensure plots_dir is up-to-date for this session
    execution_context["plots_dir"] = str(session_plots_dir)

    # Inject preloaded DataFrame if available — check shared cache first,
    # then per-session cache.  The shared cache is used for the default file
    # so all users share the same in-memory copy.
    file_path_hint = execution_context.get("__file_path", "")

    def _try_inject_preloaded() -> bool:
        """Try to find and inject preloaded df. Returns True if found."""
        if file_path_hint and file_path_hint in SHARED_PRELOAD:
            execution_context["__preloaded_df"] = SHARED_PRELOAD[file_path_hint]
            return True
        for ck, cdf in list(PRELOAD_CACHE.items()):
            if ck.startswith(f"{session_id}::"):
                execution_context["__preloaded_df"] = cdf
                execution_context["__file_path"] = ck.split("::", 1)[1]
                return True
        # Fallback: try absolute path in shared cache
        if file_path_hint:
            abs_file = str(Path(file_path_hint).absolute())
            if abs_file in SHARED_PRELOAD:
                execution_context["__preloaded_df"] = SHARED_PRELOAD[abs_file]
                return True
        return False

    if not _try_inject_preloaded() and file_path_hint:
        # A preload might be in-flight — wait up to 10s for it to finish
        # Use asyncio.sleep to avoid blocking the event loop
        for _ in range(20):  # 20 × 0.5s = 10s max
            await asyncio.sleep(0.5)
            if _try_inject_preloaded():
                print(f"✅ Preload arrived while waiting — injected __preloaded_df")
                break
        else:
            print(f"⏳ Preload not ready after 10s — agent code will load the file itself")

    # Ensure session plots directory exists
    session_plots_dir.mkdir(parents=True, exist_ok=True)

    # Snapshot existing plot files BEFORE execution so we can detect new ones
    existing_plots = set(session_plots_dir.glob("*.*"))

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

    plots_saved = []
    tables_found = []

    try:
        import asyncio

        if "__builtins__" not in execution_context:
            execution_context["__builtins__"] = __builtins__

        # Thread-safe stdout capture: use a per-execution StringIO buffer
        # instead of redirecting the global sys.stdout
        output_buffer = io.StringIO()

        def _exec_with_capture():
            """Run exec() with captured stdout, isolated from other sessions."""
            import contextlib
            with contextlib.redirect_stdout(output_buffer):
                exec(code, execution_context)

        # Wrap exec in asyncio.to_thread with a server-side timeout to prevent
        # zombie executions that consume CPU/memory after the client gives up.
        try:
            await asyncio.wait_for(
                asyncio.to_thread(_exec_with_capture),
                timeout=120.0,
            )
        except asyncio.TimeoutError:
            output = output_buffer.getvalue()
            return {
                "success": False,
                "output": output,
                "error": "Code execution timed out after 120 seconds. For large datasets, use vectorized pandas operations instead of .apply() or row-by-row loops.",
                "plots": plots_saved,
                "tables": tables_found,
            }

        # Get captured output
        output = output_buffer.getvalue()

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
                    plot_path = session_plots_dir / f"{safe_label}.png"
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
        current_plots = set(session_plots_dir.glob("*.*"))
        new_plots = current_plots - existing_plots
        plots_saved = [str(p) for p in sorted(new_plots)]

        if plots_saved:
            print(f"🖼️  Detected {len(plots_saved)} new plot(s): {[Path(p).name for p in plots_saved]}")

        # Auto-detect and format pandas DataFrames, save to session tables dir
        try:
            import pandas as pd

            session_tables_dir.mkdir(parents=True, exist_ok=True)

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
                        csv_path = session_tables_dir / f"{var_name}.csv"
                        md_path = session_tables_dir / f"{var_name}.md"
                        var_value.to_csv(str(csv_path), index=True)
                        with open(str(md_path), "w", encoding="utf-8") as f:
                            f.write(f"# {var_name}\n\n")
                            f.write(markdown_table)
                        print(f"📋 Saved table '{var_name}' → {csv_path.name}, {md_path.name}")

        except ImportError:
            pass
        except Exception as e:
            print(f"Warning: Could not format DataFrames: {e}")

        # Get final output (may have been extended by auto-save messages)
        output = output_buffer.getvalue()

        return {
            "success": True,
            "output": output,
            "error": None,
            "plots": plots_saved,
            "tables": tables_found,
        }

    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
        output = output_buffer.getvalue()

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
    """Reset the execution context for a session and clean up its preload cache."""
    session_id = request.session_id

    # Clean up preload cache entries for this session
    with _preload_lock:
        keys_to_remove = [k for k in PRELOAD_CACHE if k.startswith(f"{session_id}::")]
        for k in keys_to_remove:
            del PRELOAD_CACHE[k]
            print(f"🗑️  Evicted preload cache: {k}")

    if session_id in SESSION_CONTEXTS:
        session_plots_dir = get_session_plots_dir(session_id)
        # Re-initialize with pre-defined variables
        SESSION_CONTEXTS[session_id] = {
            "plots_dir": str(session_plots_dir),
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
        "preloaded_files": len(PRELOAD_CACHE),
    }


if __name__ == "__main__":
    import uvicorn

    print("=" * 70)
    print("🚀 Starting Sandbox Execution Server")
    print("=" * 70)
    print()
    print(f"Sandbox directory: {SANDBOX_DIR}")
    print()
    print("Server will run on: http://localhost:8765")
    print()
    print("Endpoints:")
    print("  POST /execute  - Execute Python code")
    print("  POST /install  - Install Python package")
    print("  POST /preload  - Preload file into cache")
    print("  POST /reset    - Reset session context")
    print("  GET  /health   - Health check")
    print("  GET  /sessions - List active sessions")
    print()
    print("=" * 70)
    print()

    uvicorn.run(app, host="localhost", port=8765, log_level="info")
