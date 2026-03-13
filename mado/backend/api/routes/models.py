"""Model management API routes."""


from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from mado.backend.models.model_manager import ModelManager

router = APIRouter()
model_manager = ModelManager()


class ModelUpdate(BaseModel):
    role: str
    new_model: str


class ModelRegister(BaseModel):
    name: str
    provider: str
    context: int = 32768
    capabilities: list = []


class RoleOrder(BaseModel):
    roles: list[str]


@router.get("/")
async def list_models():
    """List all registered models."""
    return {"models": model_manager.list_models()}


@router.get("/assignments")
async def get_assignments():
    """Get current agent-model assignments."""
    return {"assignments": model_manager.agent_assignments}


@router.put("/switch")
async def switch_model(data: ModelUpdate):
    """Switch model for an agent role at runtime."""
    try:
        model_manager.update_model(data.role, data.new_model)
        return {"status": "switched", "role": data.role, "new_model": data.new_model}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/register")
async def register_model(data: ModelRegister):
    """Register a new model."""
    model_manager.register_model(data.name, {
        "provider": data.provider,
        "context": data.context,
        "capabilities": data.capabilities,
    })
    return {"status": "registered", "model": data.name}


@router.put("/reorder")
async def reorder_roles(data: RoleOrder):
    """Reorder agent roles (affects execution priority)."""
    current = model_manager.agent_assignments
    # Validate all roles exist
    for role in data.roles:
        if role not in current:
            raise HTTPException(status_code=400, detail=f"Unknown role: {role}")
    # Rebuild assignments dict in new order
    reordered = {role: current[role] for role in data.roles}
    # Keep any roles not in the list at the end
    for role in current:
        if role not in reordered:
            reordered[role] = current[role]
    model_manager.agent_assignments = reordered
    model_manager.save_assignments()
    return {"status": "reordered", "roles": list(reordered.keys())}


@router.post("/reload")
async def reload_models():
    """Reload models from config files."""
    model_manager.reload_models()
    return {"status": "reloaded"}


@router.get("/metrics")
async def get_llm_metrics():
    """Get LLM call metrics for monitoring."""
    from mado.backend.models.router import metrics
    return {"metrics": metrics.to_dict()}
