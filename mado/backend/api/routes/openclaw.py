"""OpenClaw integration API routes."""

from fastapi import APIRouter

from mado.backend.integrations.openclaw import OpenClawIntegration

router = APIRouter()
openclaw = OpenClawIntegration()


@router.get("/status")
async def openclaw_status():
    """Check if OpenClaw is installed and get version."""
    try:
        installed = openclaw.is_installed()
        version = openclaw.get_version() if installed else None
        return {"installed": installed, "version": version}
    except Exception as e:
        return {"installed": False, "version": None, "check_error": str(e)}


@router.post("/install")
async def install_openclaw():
    """Install OpenClaw if not present."""
    result = openclaw.ensure_installed()
    return result


@router.post("/gateway/start")
async def start_gateway():
    """Start OpenClaw gateway."""
    result = openclaw.start_gateway()
    return result


@router.get("/sessions")
async def list_sessions():
    """List active OpenClaw sessions."""
    result = await openclaw.list_sessions()
    return result
