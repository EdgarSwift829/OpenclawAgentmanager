"""MADO FastAPI Application - Main entry point."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from mado.backend.api.routes import projects, agents, models, orchestrator, websocket, logs, openclaw, profiles

app = FastAPI(
    title="MADO - Multi-Agent Dev Orchestrator",
    description="Local platform for managing AI development teams",
    version="0.1.0",
)

_DEFAULT_ORIGINS = ["http://localhost:3000", "http://localhost:3001"]
_cors_origins = os.environ.get("MADO_CORS_ORIGINS", "").strip()
_allowed_origins = [o.strip() for o in _cors_origins.split(",") if o.strip()] if _cors_origins else _DEFAULT_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(models.router, prefix="/api/models", tags=["models"])
app.include_router(orchestrator.router, prefix="/api/orchestrator", tags=["orchestrator"])
app.include_router(websocket.router, prefix="/api/ws", tags=["websocket"])
app.include_router(logs.router, prefix="/api/logs", tags=["logs"])
app.include_router(openclaw.router, prefix="/api/openclaw", tags=["openclaw"])
app.include_router(profiles.router, prefix="/api/profiles", tags=["profiles"])


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "mado"}
