import os
import shutil
import uuid
import json
import asyncio
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Security, Depends
from fastapi.security import APIKeyHeader
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
from my_agent.helpers.sandbox_client import preload_file_via_server

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

API_KEY_NAME = "X-API-Key"
API_KEY = os.environ.get("UPLOAD_API_KEY", "secret-upload-key")
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

async def get_api_key(api_key: str = Security(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Could not validate API key")
    return api_key

# Ensure directory exists for uploaded Excel files
UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_PATH = Path("data/default_config.json")

def get_default_source_file() -> str:
    """Read the current default source file path from config, or use fallback."""
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)
            file_path = config.get("default_file_path")
            if file_path and Path(file_path).exists():
                return str(Path(file_path).absolute())
        except Exception as e:
            print(f"Error reading config: {e}")
    # Fallback default
    return str(Path("data/source.csv").absolute())

# Default static datasource
DEFAULT_SOURCE_FILE = get_default_source_file()

# Ensure sessions root exists
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


class AnalyzeRequest(BaseModel):
    query: str
    file_path: Optional[str] = None
    thread_id: Optional[str] = None
    email: Optional[str] = None


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
async def upload_file(file: UploadFile = File(...), api_key: str = Depends(get_api_key)):
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

@app.post("/api/upload-default")
async def upload_default_file(file: UploadFile = File(...), api_key: str = Depends(get_api_key)):
    """Upload a new file and set it as the global default data source"""
    global DEFAULT_SOURCE_FILE
    try:
        if not file or not file.filename:
            raise HTTPException(status_code=400, detail="No file uploaded")
            
        file_ext = Path(file.filename).suffix.lower()
        unique_id = uuid.uuid4().hex[:8]
        
        # Save the raw uploaded file first
        raw_filename = f"default_source_{unique_id}_raw{file_ext}"
        raw_file_path = UPLOAD_DIR / raw_filename
        
        with open(raw_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        final_path = raw_file_path
        
        # If it's an Excel file, convert it to CSV
        if file_ext in [".xls", ".xlsx"]:
            import pandas as pd
            csv_filename = f"default_source_{unique_id}.csv"
            csv_file_path = UPLOAD_DIR / csv_filename
            
            # Read excel and write to CSV
            df = pd.read_excel(raw_file_path)
            df.to_csv(csv_file_path, index=False)
            
            # Set the final path to the converted CSV
            final_path = csv_file_path
            
            # Optionally remove the raw excel file to save space (commented out for now just in case)
            # raw_file_path.unlink(missing_ok=True)
            
        absolute_path = str(final_path.absolute())
        
        # Write to config to persist across restarts
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({"default_file_path": absolute_path}, f)
            
        # Update global memory
        DEFAULT_SOURCE_FILE = absolute_path
        
        # Async fire-and-forget signal to sandbox server to preload the new global default
        await preload_file_via_server(file_path=absolute_path, shared=True)
            
        return {
            "success": True,
            "file_path": absolute_path,
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
                
                if request.email:
                    print(f"📧 Analysis requested by: {request.email}")

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


# ---------------------------------------------------------------------------
# Chatbot Widget — served as a static single-page app for iframe embedding
# ---------------------------------------------------------------------------
DIST_DIR = Path("static/dist")

if DIST_DIR.exists():
    # Serve the widget bundle (contains index.html for UI and JS/CSS)
    # The vite config outputs to static/dist/widget and static/dist/embed
    widget_path = DIST_DIR / "widget"
    embed_path = DIST_DIR / "embed"
    
    assets_path = DIST_DIR / "assets"
    globals_path = DIST_DIR / "globals"
    
    if widget_path.exists():
        app.mount("/widget", StaticFiles(directory=str(widget_path), html=True), name="widget-static")
    if embed_path.exists():
        app.mount("/embed", StaticFiles(directory=str(embed_path), html=True), name="embed-static")
    if assets_path.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_path)), name="assets-static")
    if globals_path.exists():
        app.mount("/globals", StaticFiles(directory=str(globals_path)), name="globals-static")


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
