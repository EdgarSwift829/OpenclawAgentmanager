"""Agent profile management API routes.

Global named profiles that live under each role and can be
reused across projects.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from mado.backend.orchestrator.workspace_manager import get_workspace_manager

router = APIRouter()


class ProfileCreate(BaseModel):
    name: str
    additional_prompt: str = ""
    clone_from: Optional[str] = None


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    additional_prompt: Optional[str] = None


@router.get("/")
async def list_all_profiles():
    """Return all profiles grouped by role."""
    wm = get_workspace_manager()
    return wm.get_all_profiles()


@router.get("/{role}")
async def list_role_profiles(role: str):
    """Return profiles for a specific role."""
    wm = get_workspace_manager()
    return {"role": role, "profiles": wm.get_role_profiles(role)}


@router.post("/{role}")
async def create_profile(role: str, data: ProfileCreate):
    """Create a new profile under a role (new or cloned)."""
    if not data.name.strip():
        raise HTTPException(status_code=400, detail="Profile name is required")
    wm = get_workspace_manager()
    profile = wm.create_profile(
        role=role,
        name=data.name.strip(),
        additional_prompt=data.additional_prompt,
        clone_from=data.clone_from,
    )
    return profile


@router.put("/{role}/{profile_id}")
async def update_profile(role: str, profile_id: str, data: ProfileUpdate):
    """Update a non-preset profile."""
    wm = get_workspace_manager()
    updates = data.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = wm.update_profile(role, profile_id, updates)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Profile not found or is a preset (immutable)",
        )
    return result


@router.delete("/{role}/{profile_id}")
async def delete_profile(role: str, profile_id: str):
    """Delete a non-preset profile."""
    wm = get_workspace_manager()
    deleted = wm.delete_profile(role, profile_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Profile not found or is a preset (cannot delete)",
        )
    return {"deleted": True}
