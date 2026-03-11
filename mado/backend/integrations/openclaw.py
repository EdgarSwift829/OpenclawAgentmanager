"""OpenClaw Integration - Check, install, and communicate with OpenClaw Gateway."""

import subprocess
import json
import asyncio
from typing import Optional


OPENCLAW_WS_URL = "ws://127.0.0.1:18789"


class OpenClawIntegration:
    """Manage OpenClaw: check installation, install if missing, communicate via WebSocket."""

    def __init__(self, ws_url: str = OPENCLAW_WS_URL):
        self.ws_url = ws_url

    def is_installed(self) -> bool:
        """Check if OpenClaw is installed globally."""
        try:
            result = subprocess.run(
                ["openclaw", "--version"],
                capture_output=True, text=True, timeout=10,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def get_version(self) -> Optional[str]:
        """Get installed OpenClaw version."""
        try:
            result = subprocess.run(
                ["openclaw", "--version"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return None

    def install(self) -> dict:
        """Install OpenClaw via npm."""
        try:
            result = subprocess.run(
                ["npm", "install", "-g", "openclaw@latest"],
                capture_output=True, text=True, timeout=300,
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def ensure_installed(self) -> dict:
        """Check if installed, install if missing."""
        if self.is_installed():
            return {"status": "already_installed", "version": self.get_version()}
        result = self.install()
        if result.get("success"):
            return {"status": "installed", "version": self.get_version()}
        return {"status": "install_failed", **result}

    def start_gateway(self) -> dict:
        """Start OpenClaw gateway server."""
        try:
            process = subprocess.Popen(
                ["openclaw", "gateway"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            return {"status": "started", "pid": process.pid}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def send_message(self, session_id: str, content: str) -> dict:
        """Send a message to OpenClaw via WebSocket."""
        try:
            import websockets
            async with websockets.connect(self.ws_url) as ws:
                message = json.dumps({
                    "method": "sessions_send",
                    "params": {"session_id": session_id, "content": content},
                })
                await ws.send(message)
                response = await asyncio.wait_for(ws.recv(), timeout=30)
                return json.loads(response)
        except ImportError:
            return {"error": "websockets package not installed. Run: pip install websockets"}
        except Exception as e:
            return {"error": str(e)}

    async def list_sessions(self) -> dict:
        """List active OpenClaw sessions."""
        try:
            import websockets
            async with websockets.connect(self.ws_url) as ws:
                await ws.send(json.dumps({"method": "sessions_list"}))
                response = await asyncio.wait_for(ws.recv(), timeout=10)
                return json.loads(response)
        except Exception as e:
            return {"error": str(e)}
