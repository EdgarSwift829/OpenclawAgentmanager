"""OpenClaw Integration - Check, install, and communicate with OpenClaw Gateway."""

import subprocess
import json
import asyncio
import shutil
from typing import Optional


OPENCLAW_WS_URL = "ws://127.0.0.1:18789"


class OpenClawIntegration:
    """Manage OpenClaw: check installation, install if missing, communicate via WebSocket."""

    def __init__(self, ws_url: str = OPENCLAW_WS_URL):
        self.ws_url = ws_url

    def is_installed(self) -> bool:
        """Check if OpenClaw is installed globally.

        Tries multiple detection methods:
        1. Direct 'openclaw --version' command
        2. 'npm list -g openclaw' to check npm global packages
        3. shutil.which() to find openclaw in PATH
        """
        # Method 1: Direct command
        try:
            result = subprocess.run(
                ["openclaw", "--version"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass

        # Method 2: Check PATH via shutil.which
        if shutil.which("openclaw") is not None:
            return True

        # Method 3: Check npm global packages
        try:
            result = subprocess.run(
                ["npm", "list", "-g", "openclaw", "--depth=0"],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0 and "openclaw" in result.stdout:
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass

        return False

    def get_version(self) -> Optional[str]:
        """Get installed OpenClaw version."""
        # Try direct command first
        try:
            result = subprocess.run(
                ["openclaw", "--version"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass

        # Fallback: parse from npm list
        try:
            result = subprocess.run(
                ["npm", "list", "-g", "openclaw", "--depth=0"],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0 and "openclaw@" in result.stdout:
                for line in result.stdout.splitlines():
                    if "openclaw@" in line:
                        # Extract version from "openclaw@x.y.z"
                        idx = line.index("openclaw@")
                        ver = line[idx:].split()[0]
                        return ver
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass

        return None

    def install(self) -> dict:
        """Install OpenClaw via npm."""
        # Check if npm is available first
        if shutil.which("npm") is None:
            return {
                "success": False,
                "error": "npm is not installed or not in PATH. Please install Node.js/npm first.",
                "error_code": "npm_not_found",
            }

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
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Install timed out (300s)", "error_code": "timeout"}
        except Exception as e:
            return {"success": False, "error": str(e), "error_code": "unknown"}

    def ensure_installed(self) -> dict:
        """Check if installed, install if missing."""
        if self.is_installed():
            return {"status": "already_installed", "version": self.get_version()}

        result = self.install()
        if result.get("success"):
            # Re-verify after install
            version = self.get_version()
            if self.is_installed():
                return {"status": "installed", "version": version}
            # Install reported success but verification failed
            return {"status": "installed", "version": version, "note": "install_ok_but_verify_uncertain"}

        return {
            "status": "install_failed",
            "error": result.get("error", result.get("stderr", "Unknown error")),
            "error_code": result.get("error_code", "install_error"),
        }

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
