# Sandbox Execution Server Setup

This document explains the microservice-based sandbox architecture for the Excel Analysis Agent.

## Architecture Overview

The Excel Analysis Agent uses a **microservice architecture** for code execution:

```
┌─────────────────────────┐         HTTP API          ┌──────────────────────────┐
│   Main Application      │◄─────────────────────────►│  Sandbox Server          │
│   (LangGraph)           │      localhost:8765       │  (FastAPI/Uvicorn)       │
│                         │                           │                          │
│  - Data Inspector       │                           │  - Code Execution        │
│  - Supervisor           │                           │  - Session Management    │
│  - Coding Agent         │                           │  - Package Installation  │
│    └─ Tools:            │                           │  - In-memory State       │
│       • python_repl_tool│  ──── HTTP POST ────►    │                          │
│       • bash_tool       │  ◄──── JSON Response ──   │  Virtual Environment:    │
│       • think_tool      │                           │  - pandas, numpy         │
└─────────────────────────┘                           │  - matplotlib, openpyxl  │
                                                       │  - tabulate              │
                                                       └──────────────────────────┘
```

### Benefits

1. **Complete Isolation** - Server runs in separate process/terminal
2. **No Pickling** - State stays in-memory on the server (faster!)
3. **Better Performance** - No subprocess spawn overhead per execution
4. **Session Management** - Clean session-based state tracking
5. **Easier Debugging** - Inspect server logs separately
6. **Scalability** - Could run on different machine if needed

## Setup Instructions

### 1. Install Dependencies

First, install the required packages:

```bash
pip install -r requirements.txt
```

This installs:
- Core: `langchain`, `langchain-core`, `langchain-openai`, `langgraph`
- Data: `pandas`, `numpy`, `openpyxl`, `matplotlib`, `tabulate`
- HTTP: `httpx` (client), `fastapi`, `uvicorn` (server)

### 2. Initialize the Sandbox Environment

Create the isolated virtual environment:

```bash
python setup_sandbox.py
```

This creates `.sandbox/venv/` with base packages pre-installed.

### 3. Start the Sandbox Server

**IMPORTANT:** The sandbox server must be running before using the agent.

Open a **separate terminal** and run:

```bash
python run_sandbox_server.py
```

You should see:

```
======================================================================
🚀 Excel Analysis Agent - Sandbox Execution Server
======================================================================

Starting server on http://localhost:8765

Keep this terminal open while using the agent.
Press Ctrl+C to stop the server.

======================================================================

INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://localhost:8765 (Press CTRL+C to quit)
```

**Keep this terminal open!** The main application will communicate with this server.

### 4. Run the Main Application

In your **main terminal**, start the Excel Analysis Agent:

```bash
langgraph dev
```

Or use your preferred method to run the agent.

## How It Works

### Tool Execution Flow

1. **Agent decides to execute code** → Calls `python_repl_tool("print('hello')")`

2. **Main app** → Makes HTTP POST to `http://localhost:8765/execute`
   ```json
   {
     "code": "print('hello')",
     "session_id": "default"
   }
   ```

3. **Sandbox server**:
   - Retrieves session context from memory
   - Executes code in isolated environment
   - Detects plots, formats DataFrames
   - Updates session context
   - Returns results

4. **Main app** ← Receives JSON response:
   ```json
   {
     "success": true,
     "output": "hello\n",
     "error": null,
     "plots": [],
     "tables": []
   }
   ```

5. **Agent** → Processes results and continues

### Package Installation

When the agent needs additional packages:

1. **Agent** → Calls `bash_tool("pip install statsmodels")`
2. **Main app** → POST to `http://localhost:8765/install`
3. **Server** → Installs in sandbox venv
4. **Agent** → Can now import and use the package

### Session Management

Each analysis session has its own context:
- Variables persist across code executions
- DataFrames, arrays, imports are remembered
- Different sessions are isolated from each other
- Sessions are managed in-memory (no pickle files!)

## API Endpoints

The sandbox server exposes:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Check if server is running |
| `/execute` | POST | Execute Python code |
| `/install` | POST | Install Python package |
| `/reset` | POST | Reset session context |
| `/sessions` | GET | List active sessions |

## Troubleshooting

### Server Not Running

**Error:** `Cannot connect to sandbox server at http://localhost:8765`

**Solution:** Start the server in a separate terminal:
```bash
python run_sandbox_server.py
```

### Port Already in Use

**Error:** `Address already in use`

**Solution:** Kill the existing process or change the port in:
- `sandbox_server.py` (line with `port=8765`)
- `sandbox_client.py` (line with `SANDBOX_SERVER_URL`)

### Package Installation Fails

**Error:** Package installation timeout or failure

**Solution:**
1. Check internet connection
2. Try installing manually:
   ```bash
   .sandbox/venv/Scripts/pip install <package>  # Windows
   .sandbox/venv/bin/pip install <package>      # Linux/Mac
   ```

### Server Crashes

**Solution:**
1. Check server terminal for error messages
2. Restart the server
3. If issues persist, clean and recreate sandbox:
   ```bash
   # Delete .sandbox folder
   python setup_sandbox.py
   python run_sandbox_server.py
   ```

## Development Notes

### Files

- **`sandbox.py`** - Virtual environment management (setup, cleanup)
- **`sandbox_server.py`** - FastAPI server for code execution
- **`sandbox_client.py`** - HTTP client for making requests
- **`tools.py`** - LangChain tools that use the client
- **`run_sandbox_server.py`** - Convenience script to start server
- **`setup_sandbox.py`** - One-time sandbox initialization

### State Persistence

- **Old approach:** Pickle files between subprocess calls
- **New approach:** In-memory dictionary (`SESSION_CONTEXTS`)
- No serialization/deserialization overhead
- State cleared when server restarts

### Stopping the Server

Press `Ctrl+C` in the server terminal to gracefully shut down.

## Migration from Old Approach

If you previously used the subprocess-based sandbox:

1. **No code changes needed** - Tools have same interface
2. **Just start the server** before running the agent
3. **Faster execution** - No more pickle overhead
4. **Cleaner logs** - Separate server and agent logs

The old pickle-based functions have been removed from `sandbox.py`.
