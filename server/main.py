"""FastAPI backend for LangGraph Harness.

Provides:
  - POST /api/chat          — send a message, get streaming SSE response
  - GET  /api/files         — list files in workspace
  - GET  /api/files/{path}  — read a file
  - POST /api/permission    — approve/deny a pending permission
  - GET  /api/session       — get current session state
  - GET  /api/tasks         — list all tasks (sorted by time)
  - POST /api/tasks         — create a new task
  - POST /api/tasks/load    — load a task (switch workspace)
  - GET  /api/context-length — get current context length
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path
from typing import Optional

# Load .env file if it exists
try:
    from dotenv import load_dotenv
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    pass  # python-dotenv not installed, skip

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from harness.core.graph import GraphBuilder
from harness.core.registry import PluginRegistry
from harness.core.state import make_initial_state
from harness.llm.openai_client import OpenAILLM
from harness.plugins.memory import MemoryPlugin
from harness.plugins.memory_store import MemoryStorePlugin
from harness.plugins.mcp import MCPPlugin, MCPServerConfig
from harness.plugins.permissions import PermissionsPlugin
from harness.plugins.tools import ToolsPlugin


app = FastAPI(title="LangGraph Harness API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Agent Session Manager ---

class AgentSession:
    def __init__(self, workspace: str = ".", project_name: str = "default"):
        self.workspace = workspace
        self.project_name = project_name
        self.thread_id = str(uuid.uuid4())[:8]
        self.messages = []
        self.tool_events = []
        self.pending_interrupt = None
        self._agent = None
        self.context_tokens = 0
        self.mcp_plugin = MCPPlugin()
        self.current_task_id = None  # Track which task is active
        self.cancelled = False  # Cancellation flag for stopping running tasks

    def _create_agent(self):
        """Create and cache the agent."""
        llm = OpenAILLM(
            base_url=os.environ.get("LLM_BASE_URL", "https://llm.polixir.site/v1"),
            api_key=os.environ.get("LLM_API_KEY", ""),
            model=os.environ.get("LLM_MODEL", "glm-5.2"),
        )
        registry = PluginRegistry()
        registry.register(ToolsPlugin(workspace=self.workspace))
        registry.register(PermissionsPlugin())
        registry.register(MemoryPlugin(workspace=self.workspace))
        registry.register(MemoryStorePlugin(workspace=self.workspace))
        registry.register(self.mcp_plugin)
        builder = GraphBuilder(llm=llm, registry=registry)
        self._agent = builder.build()

    @property
    def agent(self):
        if self._agent is None:
            self._create_agent()
        return self._agent

    def get_config(self):
        return {"configurable": {"thread_id": self.thread_id}}

    def estimate_tokens(self, text: str) -> int:
        """Rough token estimation (1 token ≈ 4 chars for English, 1-2 for Chinese)."""
        return len(text) // 2

    def update_context_length(self):
        """Update total context token count."""
        total = 0
        for msg in self.messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total += self.estimate_tokens(content)
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and "text" in block:
                        total += self.estimate_tokens(block["text"])
        self.context_tokens = total


# Global session (single-user for demo)
_session = AgentSession()


# --- API Endpoints ---

class ChatRequest(BaseModel):
    message: str


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """Send a message and stream back events as SSE."""
    if _session.pending_interrupt:
        raise HTTPException(400, "Cannot send message while permission is pending")

    _session.cancelled = False
    state = make_initial_state(req.message)
    _session.messages.append({"role": "user", "content": req.message})

    async def event_generator():
        try:
            async for event in _session.agent.astream(state, config=_session.get_config(), stream_mode="updates"):
                if _session.cancelled:
                    yield f"data: {json.dumps({'type': 'stopped'})}\n\n"
                    return
                for node_name, node_output in event.items():
                    if _session.cancelled:
                        yield f"data: {json.dumps({'type': 'stopped'})}\n\n"
                        return
                    if node_name == "agent":
                        for msg in node_output.get("messages", []):
                            msg_dict = _msg_to_dict(msg)
                            _session.messages.append(msg_dict)
                            yield f"data: {json.dumps({'type': 'message', 'data': msg_dict})}\n\n"
                    elif node_name == "tools":
                        for msg in node_output.get("messages", []):
                            msg_dict = _msg_to_dict(msg)
                            _session.messages.append(msg_dict)
                            yield f"data: {json.dumps({'type': 'tool_result', 'data': msg_dict})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'data': str(e)})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


class PermissionRequest(BaseModel):
    approved: bool


@app.post("/api/permission")
async def handle_permission(req: PermissionRequest):
    """Approve or deny a pending permission."""
    if not _session.pending_interrupt:
        raise HTTPException(400, "No pending permission")

    # TODO: implement resume logic
    _session.pending_interrupt = None
    return {"status": "approved" if req.approved else "denied"}


@app.get("/api/session")
async def get_session():
    """Get current session state."""
    return get_session_data()


@app.get("/api/files")
async def list_files(path: str = "."):
    """List files in workspace."""
    root = Path(_session.workspace) / path
    if not root.exists():
        raise HTTPException(404, "Path not found")
    entries = []
    for entry in sorted(root.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
        if entry.name.startswith("."):
            continue
        entries.append({
            "name": entry.name,
            "path": str(entry.relative_to(_session.workspace)),
            "is_dir": entry.is_dir(),
        })
    return entries


@app.get("/api/files/{file_path:path}")
async def read_file(file_path: str):
    """Read a file."""
    full = Path(_session.workspace) / file_path
    if not full.is_file():
        raise HTTPException(404, "File not found")
    try:
        content = full.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = "[Binary file]"
    return {"path": file_path, "content": content}


def _msg_to_dict(msg):
    """Convert a LangChain message to a dict."""
    if hasattr(msg, "type") and hasattr(msg, "content"):
        return {
            "type": msg.type,
            "content": msg.content,
            "tool_calls": getattr(msg, "tool_calls", None),
        }
    return {"type": "unknown", "content": str(msg)}


# --- Task Management ---

TASKS_DIR = Path(__file__).parent / "tasks"
TASKS_DIR.mkdir(exist_ok=True)


class TaskInfo(BaseModel):
    id: str | None = None
    subject: str | None = None
    workspace: str = "."
    status: str = "pending"  # pending, in_progress, completed
    created_at: str | None = None


class TaskLoadRequest(BaseModel):
    id: str


@app.get("/api/tasks")
async def list_tasks():
    """List all tasks sorted by creation time (newest first)."""
    tasks = []
    if TASKS_DIR.exists():
        for f in TASKS_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                tasks.append(data)
            except:
                pass
    # Sort by created_at descending (newest first)
    tasks.sort(key=lambda t: t.get("created_at", ""), reverse=True)
    return tasks


@app.post("/api/tasks")
async def create_task(task: TaskInfo):
    """Create a new task."""
    import datetime
    task_id = f"task_{uuid.uuid4().hex[:8]}"
    thread_id = str(uuid.uuid4())[:8]
    
    # Create a workspace directory for this task
    workspace_base = Path(__file__).parent.parent / "workspaces"
    workspace_base.mkdir(exist_ok=True)
    task_workspace = workspace_base / task_id
    task_workspace.mkdir(exist_ok=True)
    
    task_data = {
        "id": task_id,
        "subject": task.subject,
        "workspace": str(task_workspace),
        "status": "pending",
        "created_at": datetime.datetime.now().isoformat(),
        "thread_id": thread_id,
        "messages": [],
        "tool_events": [],
    }
    task_file = TASKS_DIR / f"{task_id}.json"
    task_file.write_text(json.dumps(task_data, ensure_ascii=False, indent=2))

    # Set session to use this new task
    _session.current_task_id = task_id
    _session.thread_id = thread_id
    _session.messages = []
    _session.tool_events = []
    _session.workspace = str(task_workspace)
    _session.project_name = task.subject
    _session._agent = None  # Reset agent cache

    return task_data


@app.post("/api/tasks/load")
async def load_task(req: TaskLoadRequest):
    """Load a task (switch to its workspace and conversation)."""
    global _session
    task_file = TASKS_DIR / f"{req.id}.json"
    if not task_file.exists():
        raise HTTPException(404, "Task not found")

    data = json.loads(task_file.read_text())
    _session = AgentSession(workspace=data["workspace"], project_name=data["subject"])
    _session.thread_id = data.get("thread_id", str(uuid.uuid4())[:8])
    _session.current_task_id = req.id  # Set current task ID
    _session.messages = data.get("messages", [])
    _session.tool_events = data.get("tool_events", [])
    _session.update_context_length()

    # Update task status to in_progress
    data["status"] = "in_progress"
    task_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    return {"status": "loaded", "session": get_session_data()}


@app.post("/api/tasks/save")
async def save_task():
    """Save current session to the active task."""
    if not _session.current_task_id:
        raise HTTPException(404, "No active task")

    task_file = TASKS_DIR / f"{_session.current_task_id}.json"
    if not task_file.exists():
        raise HTTPException(404, "Task file not found")

    data = json.loads(task_file.read_text())
    data["messages"] = _session.messages
    data["tool_events"] = _session.tool_events
    data["workspace"] = _session.workspace
    task_file.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    return {"status": "saved", "task_id": data["id"]}


@app.post("/api/tasks/{task_id}/stop")
async def stop_task(task_id: str):
    """Stop a running task by setting cancellation flag."""
    if _session.current_task_id == task_id:
        _session.cancelled = True
        return {"status": "stopped", "task_id": task_id}
    raise HTTPException(404, "Task not running")


@app.get("/api/context-length")
async def get_context_length():
    """Get current context length in tokens."""
    _session.update_context_length()
    return {
        "tokens": _session.context_tokens,
        "messages": len(_session.messages),
        "limit": 100000,  # Approximate model limit
        "percentage": (_session.context_tokens / 100000) * 100,
    }


# --- MCP Server Management ---

class MCPServerRequest(BaseModel):
    name: str
    transport: str  # "stdio" or "sse"
    command: str | None = None
    args: list[str] = []
    url: str | None = None
    env: dict[str, str] = {}


@app.get("/api/mcp/servers")
async def list_mcp_servers():
    """List configured MCP servers."""
    return _session.mcp_plugin.list_servers()


@app.post("/api/mcp/servers")
async def add_mcp_server(req: MCPServerRequest):
    """Add and connect to an MCP server."""
    config = MCPServerConfig(
        name=req.name,
        transport=req.transport,
        command=req.command,
        args=req.args,
        url=req.url,
        env=req.env,
    )
    result = await _session.mcp_plugin.add_server(config)

    # Invalidate cached agent so it picks up new MCP tools
    _session._agent = None

    return result


@app.delete("/api/mcp/servers/{server_name}")
async def remove_mcp_server(server_name: str):
    """Disconnect and remove an MCP server."""
    result = await _session.mcp_plugin.remove_server(server_name)

    # Invalidate cached agent
    _session._agent = None

    return result


def get_session_data():
    """Get session data for response."""
    _session.update_context_length()
    return {
        "thread_id": _session.thread_id,
        "workspace": _session.workspace,
        "task_name": _session.project_name,
        "messages": _session.messages,
        "tool_events": _session.tool_events,
        "pending_interrupt": _session.pending_interrupt,
        "context_tokens": _session.context_tokens,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
