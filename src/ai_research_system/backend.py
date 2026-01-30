"""
FastAPI backend for the AI Research System.

Exposes:
- MCP-style endpoints (via `mcp_server.router`)
- Agent orchestration endpoints for the web UI
"""

import uuid
from typing import Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .agent import AgentStatus, QueryPayload, spawn_agent_task, task_store
from .mcp_server import router as mcp_router


def create_app() -> FastAPI:
    app = FastAPI(title="AI Research System", version="0.1.0")

    # Allow local UIs (Streamlit) to talk to the API
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health() -> Dict[str, str]:
        return {"status": "ok"}

    app.include_router(mcp_router)

    @app.post("/agent/start", response_model=AgentStatus)
    async def start_agent(payload: QueryPayload) -> AgentStatus:
        """
        Start an asynchronous research task and return the initial status.
        """
        task_id = str(uuid.uuid4())
        status = task_store.create(task_id)
        spawn_agent_task(task_id, payload)
        return status

    @app.get("/agent/status/{task_id}", response_model=AgentStatus)
    async def get_status(task_id: str) -> AgentStatus:
        status = task_store.get(task_id)
        if status is None:
            raise HTTPException(status_code=404, detail="Unknown task_id")
        return status

    return app


app = create_app()


