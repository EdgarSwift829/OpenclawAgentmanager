"""MADO System Startup Script.

Startup flow:
  1. Check OpenClaw installation (install if missing)
  2. Validate config files
  3. Start FastAPI backend server
"""

import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def check_openclaw():
    """Check if OpenClaw is installed, install if missing."""
    print("[startup] Checking OpenClaw...")
    try:
        result = subprocess.run(["openclaw", "--version"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print(f"[startup] OpenClaw found: {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        pass

    print("[startup] OpenClaw not found. Attempting install...")
    try:
        result = subprocess.run(
            ["npm", "install", "-g", "openclaw@latest"],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode == 0:
            print("[startup] OpenClaw installed successfully.")
            return True
        else:
            print(f"[startup] OpenClaw install failed: {result.stderr}")
            return False
    except FileNotFoundError:
        print("[startup] npm not found. Install Node.js >= 22 to use OpenClaw.")
        return False


def check_config():
    """Validate config files exist."""
    models_yaml = ROOT / "config" / "models.yaml"
    agents_yaml = ROOT / "config" / "agents.yaml"

    if not models_yaml.exists():
        print(f"[startup] WARNING: {models_yaml} not found")
        return False
    if not agents_yaml.exists():
        print(f"[startup] WARNING: {agents_yaml} not found")
        return False

    print("[startup] Config files OK.")
    return True


def start_server(host: str = "0.0.0.0", port: int = 8000):
    """Start the FastAPI backend server."""
    print(f"[startup] Starting MADO server on {host}:{port}")
    subprocess.run([
        sys.executable, "-m", "uvicorn",
        "mado.backend.api.main:app",
        "--host", host,
        "--port", str(port),
        "--reload",
    ], cwd=str(ROOT))


def main():
    print("=" * 50)
    print("  MADO - Multi-Agent Dev Orchestrator")
    print("=" * 50)

    check_openclaw()
    check_config()

    host = "0.0.0.0"
    port = 8000
    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--host" and i + 2 < len(sys.argv):
            host = sys.argv[i + 2]
        if arg == "--port" and i + 2 < len(sys.argv):
            port = int(sys.argv[i + 2])

    start_server(host, port)


if __name__ == "__main__":
    main()
