"""Centralized configuration for the Excel Analysis Agent.

All model names, temperature defaults, and tuneable limits live here
so they can be overridden via environment variables without touching node code.
"""

import os


class ModelConfig:
    """LLM model identifiers — override via environment variables.

    Default assignments optimised for cost + accuracy across providers:
      - gemini-2.0-flash : cheapest, fast — for simple classification / chat
      - gemini-2.5-flash : thinking model — for plan generation (reasoning helps)
      - gpt-4.1-mini     : strong coding + reliable tool calling — for code execution
    """

    ROUTER_MODEL: str = os.getenv("ROUTER_MODEL", "gemini-2.0-flash")
    SUPERVISOR_MODEL: str = os.getenv("SUPERVISOR_MODEL", "gemini-2.0-flash")
    PLANNING_MODEL: str = os.getenv("PLANNING_MODEL", "gemini-2.5-flash")
    CODING_MODEL: str = os.getenv("CODING_MODEL", "gpt-4.1-mini")
    CHAT_MODEL: str = os.getenv("CHAT_MODEL", "gemini-2.0-flash")
    FOLLOWUP_MODEL: str = os.getenv("FOLLOWUP_MODEL", "gemini-2.0-flash")


class AgentConfig:
    """Runtime tunables for the agent graph."""

    # Coding subgraph iteration limits
    CODING_MAX_ITERATIONS: int = int(os.getenv("CODING_MAX_ITERATIONS", "15"))
    CODING_SOFT_WARNING: int = int(os.getenv("CODING_SOFT_WARNING", "8"))

    # Sandbox server
    SANDBOX_SERVER_URL: str = os.getenv("SANDBOX_SERVER_URL", "http://localhost:8765")
    SANDBOX_TIMEOUT: float = float(os.getenv("SANDBOX_TIMEOUT", "120.0"))

    # Data inspector — large file handling
    DATA_INSPECTOR_SAMPLE_ROWS: int = int(os.getenv("DATA_INSPECTOR_SAMPLE_ROWS", "5000"))
    LARGE_FILE_THRESHOLD_MB: float = float(os.getenv("LARGE_FILE_THRESHOLD_MB", "10.0"))
