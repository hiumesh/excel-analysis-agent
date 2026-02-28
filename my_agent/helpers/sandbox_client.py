"""HTTP client for interacting with the sandbox execution server.

This module provides functions to communicate with the sandbox server
running on localhost:8765.
"""

from typing import Any, Dict

import httpx

SANDBOX_SERVER_URL = "http://localhost:8765"
DEFAULT_TIMEOUT = 120.0  # 2 minutes for long-running operations


class SandboxClient:
    """Client for interacting with the sandbox execution server."""

    def __init__(
        self, server_url: str = SANDBOX_SERVER_URL, session_id: str = "default"
    ):
        self.server_url = server_url
        self.session_id = session_id

    async def health_check(self) -> Dict[str, Any]:
        """Check if the sandbox server is running and healthy."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.server_url}/health")
                response.raise_for_status()
                return response.json()
        except httpx.ConnectError:
            raise ConnectionError(
                f"Cannot connect to sandbox server at {self.server_url}. "
                "Make sure the server is running:\n"
                "  python -m my_agent.helpers.sandbox_server"
            )
        except Exception as e:
            raise Exception(f"Health check failed: {str(e)}")

    async def execute_code(self, code: str) -> Dict[str, Any]:
        """
        Execute Python code in the sandbox environment.

        Args:
            code: Python code to execute

        Returns:
            Dictionary containing:
                - success: Boolean indicating if execution was successful
                - output: Captured stdout from the code execution
                - error: Error message if execution failed, None otherwise
                - plots: List of saved plot file paths
                - tables: List of formatted markdown tables with descriptions
        """
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                response = await client.post(
                    f"{self.server_url}/execute",
                    json={"code": code, "session_id": self.session_id},
                )
                response.raise_for_status()
                return response.json()
        except httpx.ConnectError:
            raise ConnectionError(
                f"Cannot connect to sandbox server at {self.server_url}. "
                "Make sure the server is running:\n"
                "  python -m my_agent.helpers.sandbox_server"
            )
        except httpx.TimeoutException:
            return {
                "success": False,
                "output": "",
                "error": "Code execution timed out after 120 seconds",
                "plots": [],
                "tables": [],
            }
        except Exception as e:
            return {
                "success": False,
                "output": "",
                "error": f"Error communicating with sandbox server: {str(e)}",
                "plots": [],
                "tables": [],
            }

    async def install_package(self, package_name: str) -> Dict[str, Any]:
        """
        Install a Python package in the sandbox environment.

        Args:
            package_name: Name of the package to install (e.g., "statsmodels")

        Returns:
            Dictionary with success status and output/error messages
        """
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                response = await client.post(
                    f"{self.server_url}/install", json={"package_name": package_name}
                )
                response.raise_for_status()
                return response.json()
        except httpx.ConnectError:
            raise ConnectionError(
                f"Cannot connect to sandbox server at {self.server_url}. "
                "Make sure the server is running:\n"
                "  python -m my_agent.helpers.sandbox_server"
            )
        except httpx.TimeoutException:
            return {
                "success": False,
                "output": "",
                "error": f"Installation of {package_name} timed out after 120 seconds",
            }
        except Exception as e:
            return {
                "success": False,
                "output": "",
                "error": f"Error installing package: {str(e)}",
            }

    async def reset_context(self) -> Dict[str, Any]:
        """Reset the execution context for this session."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(
                    f"{self.server_url}/reset", json={"session_id": self.session_id}
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            return {"success": False, "message": f"Error resetting context: {str(e)}"}


# Global client instance (can be configured)
_default_client = None


def get_client(session_id: str = "default") -> SandboxClient:
    """Get or create the default sandbox client."""
    global _default_client
    if _default_client is None or _default_client.session_id != session_id:
        _default_client = SandboxClient(session_id=session_id)
    return _default_client


async def execute_code_via_server(
    code: str, session_id: str = "default"
) -> Dict[str, Any]:
    """
    Execute Python code by making an HTTP request to the sandbox server.

    This is a convenience function that creates/reuses a client and executes code.

    Args:
        code: Python code to execute
        session_id: Session identifier for maintaining state

    Returns:
        Dictionary with execution results
    """
    client = get_client(session_id)
    return await client.execute_code(code)


async def install_package_via_server(
    package_name: str, session_id: str = "default"
) -> Dict[str, Any]:
    """
    Install a package by making an HTTP request to the sandbox server.

    Args:
        package_name: Package to install
        session_id: Session identifier

    Returns:
        Dictionary with installation results
    """
    client = get_client(session_id)
    return await client.install_package(package_name)


async def reset_context_via_server(session_id: str = "default"):
    """Reset the execution context on the sandbox server."""
    client = get_client(session_id)
    await client.reset_context()
    print("🔄 Execution context reset on sandbox server")


async def check_server_health() -> bool:
    """Check if the sandbox server is running and healthy."""
    try:
        client = get_client()
        health = await client.health_check()
        print(f"✅ Sandbox server is healthy: {health}")
        return True
    except Exception as e:
        print(f"❌ Sandbox server health check failed: {e}")
        return False
