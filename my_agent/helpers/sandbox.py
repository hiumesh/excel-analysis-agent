"""Virtual environment management for the sandbox execution server.

This module handles creation and management of the isolated Python virtual
environment used by the sandbox server. The actual code execution happens
in sandbox_server.py via HTTP API.
"""

import shutil
import subprocess
import sys
import venv
from pathlib import Path

# Path to the shared sandbox venv
SANDBOX_DIR = Path(__file__).parent.parent.parent / ".sandbox"
VENV_DIR = SANDBOX_DIR / "venv"
PLOTS_DIR = SANDBOX_DIR / "plots"
TABLES_DIR = SANDBOX_DIR / "tables"


def get_python_executable() -> str:
    """Get the path to the Python executable in the sandbox venv."""
    if sys.platform == "win32":
        return str(VENV_DIR / "Scripts" / "python.exe")
    else:
        return str(VENV_DIR / "bin" / "python")


def get_pip_executable() -> str:
    """Get the path to pip in the sandbox venv."""
    if sys.platform == "win32":
        return str(VENV_DIR / "Scripts" / "pip.exe")
    else:
        return str(VENV_DIR / "bin" / "pip")


def ensure_sandbox_exists() -> bool:
    """
    Ensure the sandbox virtual environment exists.

    Creates the venv if it doesn't exist and installs base packages.

    Returns:
        True if sandbox exists or was created successfully, False otherwise
    """
    if VENV_DIR.exists() and get_python_executable():
        # Venv already exists
        return True

    print("🏗️  Creating sandbox virtual environment (first-time setup)...")

    try:
        # Create sandbox directory
        SANDBOX_DIR.mkdir(parents=True, exist_ok=True)
        PLOTS_DIR.mkdir(parents=True, exist_ok=True)
        TABLES_DIR.mkdir(parents=True, exist_ok=True)

        # Create virtual environment
        print("   Creating venv...")
        venv.create(VENV_DIR, with_pip=True, clear=True)

        # Upgrade pip
        print("   Upgrading pip...")
        result = subprocess.run(
            [get_pip_executable(), "install", "--upgrade", "pip"],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print(f"   ⚠️  Warning: pip upgrade failed (non-critical)")
            print(f"   Error: {result.stderr}")
            # Continue anyway - base pip should work

        # Install base packages
        base_packages = [
            # Data manipulation
            "pandas",
            "numpy",
            "openpyxl",
            # Visualization
            "matplotlib",
            "seaborn",
            # Statistics & ML
            "scipy",
            "statsmodels",
            "scikit-learn",
            # Utilities
            "tabulate",
            "python-dateutil",
        ]
        print(f"   Installing base packages ({len(base_packages)} packages)...")
        print(f"   This may take a few minutes on first setup...")
        result = subprocess.run(
            [get_pip_executable(), "install"] + base_packages,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print(f"   ❌ Package installation failed!")
            print(f"   stdout: {result.stdout}")
            print(f"   stderr: {result.stderr}")
            raise Exception(f"Failed to install base packages: {result.stderr}")

        print("✅ Sandbox environment created successfully!")
        return True

    except Exception as e:
        print(f"❌ Failed to create sandbox: {e}")
        return False


def cleanup_sandbox():
    """Clean up the sandbox environment (delete venv and context)."""
    if SANDBOX_DIR.exists():
        shutil.rmtree(SANDBOX_DIR)
        print("🧹 Sandbox cleaned up")
