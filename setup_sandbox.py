#!/usr/bin/env python
"""
Setup script to initialize the sandbox environment for the Excel Analysis Agent.

This script creates a virtual environment with pre-installed libraries
(pandas, numpy, matplotlib, openpyxl, tabulate) in a sandboxed location.

Run this script before using the agent to ensure the sandbox is ready.
"""

import sys
from pathlib import Path

# Add the project root to the path so we can import from my_agent
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from my_agent.helpers.sandbox import ensure_sandbox_exists, SANDBOX_DIR, VENV_DIR


def main():
    """Initialize the sandbox environment."""
    print("=" * 70)
    print("Excel Analysis Agent - Sandbox Setup")
    print("=" * 70)
    print()
    print("This script will create a sandboxed Python environment for code execution.")
    print("The sandbox will be isolated from your main Python environment.")
    print()
    print(f"Sandbox location: {SANDBOX_DIR}")
    print(f"Virtual environment: {VENV_DIR}")
    print()
    print("Base packages to be installed:")
    print("  - pandas")
    print("  - numpy")
    print("  - matplotlib")
    print("  - openpyxl")
    print("  - tabulate")
    print()
    print("-" * 70)
    print()

    # Create the sandbox
    success = ensure_sandbox_exists()

    print()
    print("-" * 70)
    if success:
        print("✅ Sandbox setup completed successfully!")
        print()
        print("The agent is now ready to use.")
        print("The sandbox will be reused for all analysis sessions.")
        print()
        print("To clean up the sandbox, delete the .sandbox folder:")
        print(f"   {SANDBOX_DIR}")
        return 0
    else:
        print("❌ Sandbox setup failed!")
        print()
        print("Please check the error messages above and try again.")
        print("Common issues:")
        print("  - Python venv module not installed")
        print("  - No internet connection (needed to download packages)")
        print("  - Insufficient disk space")
        return 1


if __name__ == "__main__":
    sys.exit(main())
