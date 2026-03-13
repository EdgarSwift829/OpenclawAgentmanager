"""Agent management API routes."""


from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

# In-memory store of active agent sessions per project
_active_sessions: dict = {}


class AgentInfo(BaseModel):
    role: str
    model: str
    status: str
    workspace_path: str


@router.get("/{project_id}")
async def list_agents(project_id: str):
    """List all agents for a project."""
    session = _active_sessions.get(project_id, {})
    agents = []
    for role, agent in session.items():
        agents.append({
            "role": role,
            "model": agent.model.get("name", "unknown"),
            "status": "active",
        })
    return {"project_id": project_id, "agents": agents}


@router.get("/{project_id}/{role}")
async def get_agent(project_id: str, role: str):
    """Get details of a specific agent."""
    session = _active_sessions.get(project_id, {})
    agent = session.get(role)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {role}")
    return {
        "role": role,
        "model": agent.model,
        "workspace_path": agent.workspace_path,
        "tools": [t.__class__.__name__ for t in agent.tools] if agent.tools else [],
    }


def register_session(project_id: str, agents: dict):
    """Register active agents for a project (called by orchestrator)."""
    _active_sessions[project_id] = agents


def get_session(project_id: str) -> dict:
    """Get active agents for a project."""
    return _active_sessions.get(project_id, {})
