"""MADO FastAPI Application - Main entry point."""

import os

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from mado.backend.api.routes import agents, app_tasks, logs, models, openclaw, orchestrator, profiles, projects, websocket
from mado.backend.logging_config import setup_logging
from mado.backend.safety.auth import is_auth_enabled, require_auth

# Initialize structured logging before anything else
setup_logging()

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

# Apply auth dependency to all protected routes when MADO_API_KEY is set
_auth_deps = [Depends(require_auth)] if is_auth_enabled() else []

app.include_router(projects.router, prefix="/api/projects", tags=["projects"], dependencies=_auth_deps)
app.include_router(agents.router, prefix="/api/agents", tags=["agents"], dependencies=_auth_deps)
app.include_router(models.router, prefix="/api/models", tags=["models"], dependencies=_auth_deps)
app.include_router(orchestrator.router, prefix="/api/orchestrator", tags=["orchestrator"], dependencies=_auth_deps)
app.include_router(websocket.router, prefix="/api/ws", tags=["websocket"])  # WS auth handled in endpoint
app.include_router(logs.router, prefix="/api/logs", tags=["logs"], dependencies=_auth_deps)
app.include_router(openclaw.router, prefix="/api/openclaw", tags=["openclaw"], dependencies=_auth_deps)
app.include_router(profiles.router, prefix="/api/profiles", tags=["profiles"], dependencies=_auth_deps)
app.include_router(app_tasks.router, prefix="/api/app", tags=["app-tasks"], dependencies=_auth_deps)


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "mado", "auth_enabled": is_auth_enabled()}
