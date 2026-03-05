import os
import shutil
import uuid
import json
import asyncio
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from langchain_core.messages import HumanMessage
from pydantic import BaseModel
from contextlib import asynccontextmanager
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from my_agent.agent import create_excel_analysis_graph
from my_agent.core.execution_var import set_current_session_id
from my_agent.helpers.sandbox import SESSIONS_DIR

# Module-level graph reference (set during app lifespan)
graph = None

# SQLite checkpointer DB path
DB_PATH = Path("data/checkpoints.db")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage the AsyncSqliteSaver lifecycle — open on startup, close on shutdown."""
    global graph
    async with AsyncSqliteSaver.from_conn_string(str(DB_PATH)) as checkpointer:
        graph = create_excel_analysis_graph(checkpointer=checkpointer)
        print(f"✅ Graph initialized with SQLite checkpointer at {DB_PATH}")
        yield
    graph = None

app = FastAPI(title="Excel Analysis Agent API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure directory exists for uploaded Excel files
UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Default static datasource — used when no file_path is provided in the request
DEFAULT_SOURCE_FILE = str(Path("data/source.csv").absolute())

# Ensure sessions root exists
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


class AnalyzeRequest(BaseModel):
    query: str
    file_path: Optional[str] = None
    thread_id: Optional[str] = None


def clean_artifacts(artifacts, thread_id: str = "default"):
    """Clean up the format of artifacts to make image paths absolute URLs relative to the server.
    
    Plot URLs are now session-scoped: /plots/{thread_id}/{filename}
    """
    if not isinstance(artifacts, list):
        return []
    processed = []
    for artifact in artifacts:
        content = artifact.get("content", "")
        # Map 'description' to 'title' so the frontend can display artifact names
        if "description" in artifact and "title" not in artifact:
            artifact["title"] = artifact["description"]
        if artifact.get("type") == "plot" and isinstance(content, str):
            filename = Path(content).name
            artifact["url"] = f"/plots/{thread_id}/{filename}"
        processed.append(artifact)
    return processed


# ---------------------------------------------------------------------------
# Dynamic per-session plot/table file serving
# ---------------------------------------------------------------------------

@app.get("/plots/{session_id}/{filename}")
async def serve_plot(session_id: str, filename: str):
    """Serve a plot file from a session-scoped directory."""
    plot_path = SESSIONS_DIR / session_id / "plots" / filename
    if not plot_path.exists():
        raise HTTPException(status_code=404, detail="Plot not found")
    return FileResponse(str(plot_path))


@app.get("/tables/{session_id}/{filename}")
async def serve_table(session_id: str, filename: str):
    """Serve a table file from a session-scoped directory."""
    table_path = SESSIONS_DIR / session_id / "tables" / filename
    if not table_path.exists():
        raise HTTPException(status_code=404, detail="Table not found")
    return FileResponse(str(table_path))


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload a file and return its path for analysis"""
    try:
        if not file or not file.filename:
            raise HTTPException(status_code=400, detail="No file uploaded")
            
        file_ext = Path(file.filename).suffix
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = UPLOAD_DIR / unique_filename
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        return {
            "success": True,
            "file_path": str(file_path.absolute()),
            "filename": file.filename
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/analyze")
async def analyze_excel(request: AnalyzeRequest):
    """One-time response route for complete analysis execution"""
    try:
        thread_id = request.thread_id or str(uuid.uuid4())

        # Set session ID context so tools use the correct sandbox session
        set_current_session_id(thread_id)

        # Only pass the new message — checkpointer handles history via thread_id
        input_state = {
            "messages": [HumanMessage(content=request.query)],
            "excel_file_path": request.file_path or DEFAULT_SOURCE_FILE,
        }
            
        # Invoke the graph
        config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 100}
        print("Executing graph with thread_id:", thread_id)
        result = await graph.ainvoke(input_state, config)
        
        # Extract relevant info to return
        final_analysis = result.get("final_analysis")
        # If there's no final_analysis, fallback to the last message
        if not final_analysis and result.get("messages"):
            last_message = result["messages"][-1]
            final_analysis = last_message.content
            
        artifacts = result.get("artifacts", [])
        
        return {
            "success": True,
            "final_analysis": final_analysis,
            "artifacts": clean_artifacts(artifacts, thread_id=thread_id),
            "route_decision": result.get("route_decision", {})
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


def serialize_state_update(node: str, state_update: dict, is_subgraph: bool = False, thread_id: str = "default"):
    """Helper to sanitize and serialize state updates for streaming"""
    safe_update = {}
    for key, val in state_update.items():
        if key == "messages":
            safe_msgs = []
            for msg in val:
                if hasattr(msg, "content"):
                    safe_msg = {
                        "type": msg.__class__.__name__,
                        "content": msg.content
                    }
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        safe_msg["tool_calls"] = []
                        for tc in msg.tool_calls:
                            safe_msg["tool_calls"].append({
                                "name": tc["name"],
                                "args": tc["args"]
                            })
                    safe_msgs.append(safe_msg)
            safe_update[key] = safe_msgs
        elif key == "artifacts":
            safe_update[key] = clean_artifacts(val, thread_id=thread_id)
        else:
            safe_update[key] = val
            
    return json.dumps({
        "node": node,
        "is_subgraph": is_subgraph,
        "update": safe_update
    }, default=str)


@app.post("/api/analyze/stream")
async def analyze_excel_stream(request: AnalyzeRequest):
    """Streaming response route that emits detailed events for each graph node step"""
    try:
        async def event_generator():
            try:
                thread_id = request.thread_id or str(uuid.uuid4())

                # Set session ID context so tools use the correct sandbox session
                set_current_session_id(thread_id)

                # Only pass the new message — checkpointer handles history via thread_id
                input_state = {
                    "messages": [HumanMessage(content=request.query)],
                    "excel_file_path": request.file_path or DEFAULT_SOURCE_FILE,
                }
                    
                config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 100}
                
                # Emit thread_id as the first event so the frontend can track it
                yield f"data: {json.dumps({'thread_id': thread_id})}\n\n"
                
                # Stream the state updates
                async for namespace, chunk in graph.astream(input_state, config, stream_mode="updates", subgraphs=True):
                    is_subgraph = len(namespace) > 0
                    for node_name, state_update in chunk.items():
                        serialized = serialize_state_update(node_name, state_update, is_subgraph=is_subgraph, thread_id=thread_id)
                        yield f"data: {serialized}\n\n"
                        await asyncio.sleep(0.01)
                
                yield f"data: {json.dumps({'status': 'completed'})}\n\n"
            except Exception as e:
                import traceback
                traceback.print_exc()
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=True,
        reload_excludes=[
            ".sandbox", ".sandbox/**", 
            "data", "data/**", 
            "web", "web/**", 
            "*.db", "*.sqlite", "*.db-*"
        ]
    )
