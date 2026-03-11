"""Log viewing API routes."""

from fastapi import APIRouter, HTTPException

from mado.backend.logging_system import MADOLogger

router = APIRouter()


@router.get("/{project_id}")
async def get_logs(project_id: str, log_type: str = None, limit: int = 100):
    """Get structured logs for a project."""
    logger = MADOLogger(project_id)
    logs = logger.get_logs(log_type=log_type, limit=limit)
    return {"project_id": project_id, "logs": logs}
