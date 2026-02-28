#!/usr/bin/env python
"""
Convenience script to run the sandbox execution server.

This script ensures the sandbox is set up and then starts the FastAPI server.

Run this in a separate terminal before using the Excel Analysis Agent:
    python run_sandbox_server.py

The server will run on http://localhost:8765
"""

import sys
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

if __name__ == "__main__":
    from my_agent.helpers.sandbox_server import app
    import uvicorn

    print("=" * 70)
    print("🚀 Excel Analysis Agent - Sandbox Execution Server")
    print("=" * 70)
    print()
    print("Starting server on http://localhost:8765")
    print()
    print("Keep this terminal open while using the agent.")
    print("Press Ctrl+C to stop the server.")
    print()
    print("=" * 70)
    print()

    uvicorn.run(app, host="localhost", port=8765, log_level="info")
