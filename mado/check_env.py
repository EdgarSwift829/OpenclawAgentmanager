"""MADO Environment Checker - Auto-setup venv, install deps, verify tools."""

import subprocess
import sys
import os
import shutil
from pathlib import Path

MADO_ROOT = Path(__file__).resolve().parent
BACKEND_DIR = MADO_ROOT / "backend"
FRONTEND_DIR = MADO_ROOT / "frontend"
REQUIREMENTS_TXT = BACKEND_DIR / "requirements.txt"
VENV_DIR = MADO_ROOT / ".venv"

# Windows venv paths
VENV_PYTHON = VENV_DIR / "Scripts" / "python.exe"
VENV_PIP = VENV_DIR / "Scripts" / "pip.exe"
VENV_ACTIVATE = VENV_DIR / "Scripts" / "activate.bat"

# Linux/macOS fallback
if not sys.platform.startswith("win"):
    VENV_PYTHON = VENV_DIR / "bin" / "python"
    VENV_PIP = VENV_DIR / "bin" / "pip"
    VENV_ACTIVATE = VENV_DIR / "bin" / "activate"

# ANSI colors (Windows 10+ terminal)
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
RESET = "\033[0m"


def ok(msg: str) -> None:
    print(f"  {GREEN}[OK]{RESET} {msg}")


def warn(msg: str) -> None:
    print(f"  {YELLOW}[!!]{RESET} {msg}")


def fail(msg: str) -> None:
    print(f"  {RED}[NG]{RESET} {msg}")


def info(msg: str) -> None:
    print(f"  {CYAN}[..]{RESET} {msg}")


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)


# ── Python check ────────────────────────────────────────────────
def check_python() -> bool:
    print("\n── Python ──")
    ver = sys.version_info
    ok(f"Python {ver.major}.{ver.minor}.{ver.micro}")
    if ver < (3, 10):
        fail("Python 3.10+ が必要です")
        return False
    return True


# ── venv auto-creation ──────────────────────────────────────────
def ensure_venv() -> bool:
    """Create .venv if it doesn't exist, return True if venv is ready."""
    print("\n── Virtual Environment ──")

    if VENV_PYTHON.exists():
        ok(f".venv 確認済み ({VENV_DIR})")
        return True

    info(f".venv が見つかりません — 自動作成中...")
    result = run([sys.executable, "-m", "venv", str(VENV_DIR)])
    if result.returncode != 0:
        fail("venv の作成に失敗しました:")
        print(result.stderr)
        return False

    if not VENV_PYTHON.exists():
        fail("venv の作成後に python が見つかりません")
        return False

    ok(f".venv を作成しました ({VENV_DIR})")

    # Upgrade pip in venv
    info("pip をアップグレード中...")
    run([str(VENV_PYTHON), "-m", "pip", "install", "--upgrade", "pip"])
    ok("pip アップグレード完了")

    return True


# ── pip packages check & install (in venv) ──────────────────────
def check_pip_packages() -> bool:
    print("\n── Backend pip packages ──")
    if not REQUIREMENTS_TXT.exists():
        fail(f"{REQUIREMENTS_TXT} が見つかりません")
        return False

    python_exe = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable

    # Parse required packages
    required: list[str] = []
    for line in REQUIREMENTS_TXT.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name = line.split(">=")[0].split("<=")[0].split("==")[0].split("[")[0].strip()
        required.append(name)

    # Check which are installed in the target environment
    result = run([python_exe, "-m", "pip", "list", "--format=columns"])
    installed = set()
    for pip_line in result.stdout.splitlines()[2:]:
        parts = pip_line.split()
        if parts:
            installed.add(parts[0].lower().replace("-", "_"))

    missing = []
    for pkg in required:
        normalized = pkg.lower().replace("-", "_")
        if normalized in installed:
            ok(pkg)
        else:
            warn(f"{pkg} — 未インストール")
            missing.append(pkg)

    if missing:
        info(f"不足パッケージをインストール中: {', '.join(missing)}")
        result = run(
            [python_exe, "-m", "pip", "install", "-r", str(REQUIREMENTS_TXT)],
        )
        if result.returncode != 0:
            fail("pip install に失敗しました:")
            print(result.stderr)
            return False
        ok("全パッケージのインストール完了")
    else:
        ok("全パッケージ確認済み")

    return True


# ── Node.js check ───────────────────────────────────────────────
def check_node() -> bool:
    print("\n── Node.js ──")
    node = shutil.which("node")
    if not node:
        fail("Node.js が見つかりません。https://nodejs.org/ からインストールしてください")
        return False

    result = run(["node", "--version"])
    ver_str = result.stdout.strip().lstrip("v")
    ok(f"Node.js {ver_str}")

    major = int(ver_str.split(".")[0])
    if major < 18:
        fail("Node.js 18+ が必要です")
        return False
    return True


# ── npm packages check & install ────────────────────────────────
def check_npm_packages() -> bool:
    print("\n── Frontend npm packages ──")
    package_json = FRONTEND_DIR / "package.json"
    if not package_json.exists():
        fail(f"{package_json} が見つかりません")
        return False

    node_modules = FRONTEND_DIR / "node_modules"
    package_lock = FRONTEND_DIR / "package-lock.json"

    needs_install = False
    if not node_modules.exists():
        warn("node_modules が存在しません")
        needs_install = True
    elif package_lock.exists():
        # Check if package.json is newer than node_modules
        pj_mtime = package_json.stat().st_mtime
        nm_mtime = node_modules.stat().st_mtime
        if pj_mtime > nm_mtime:
            warn("package.json が更新されています — 再インストールが必要です")
            needs_install = True

    if needs_install:
        info("npm install を実行中...")
        result = run(["npm", "install"], cwd=str(FRONTEND_DIR))
        if result.returncode != 0:
            fail("npm install に失敗しました:")
            print(result.stderr)
            return False
        ok("npm install 完了")
    else:
        ok("node_modules 確認済み")

    return True


# ── LLM provider check ──────────────────────────────────────────
def check_llm_providers() -> bool:
    print("\n── LLM Providers ──")
    import urllib.request
    import json

    found_any = False

    # LM Studio (primary)
    try:
        req = urllib.request.Request("http://localhost:1234/v1/models")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = [m.get("id", "?") for m in data.get("data", [])]
            ok("LM Studio (localhost:1234) — 稼働中")
            if models:
                for m in models:
                    print(f"         モデル: {m}")
            else:
                warn("LM Studio にモデルがロードされていません")
            found_any = True
    except Exception:
        warn("LM Studio (localhost:1234) — 未起動またはアクセス不可")

    # Ollama (alternative)
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = [m.get("name", "?") for m in data.get("models", [])]
            ok("Ollama (localhost:11434) — 稼働中")
            if models:
                for m in models:
                    print(f"         モデル: {m}")
            found_any = True
    except Exception:
        warn("Ollama (localhost:11434) — 未起動またはアクセス不可")

    if not found_any:
        warn("LLM プロバイダーが検出されませんでした")
        warn("LM Studio または Ollama を起動してください")

    return True


# ── Optional tools check ────────────────────────────────────────
def check_optional() -> None:
    print("\n── Optional ──")

    if shutil.which("docker"):
        result = run(["docker", "--version"])
        ok(result.stdout.strip())
    else:
        warn("Docker が見つかりません（Docker未使用なら問題なし）")


# ── Write env info file (for bat to read) ───────────────────────
def write_env_info() -> None:
    """Write a small file that start_mado.bat can source for paths."""
    env_file = MADO_ROOT / ".env_paths"
    lines = [
        f"MADO_VENV_PYTHON={VENV_PYTHON}",
        f"MADO_VENV_ACTIVATE={VENV_ACTIVATE}",
        f"MADO_VENV_DIR={VENV_DIR}",
    ]
    env_file.write_text("\n".join(lines), encoding="utf-8")


# ── Main ────────────────────────────────────────────────────────
def main() -> int:
    print("=" * 50)
    print("  MADO 環境自動セットアップ")
    print("=" * 50)

    results = []
    results.append(check_python())
    results.append(ensure_venv())
    results.append(check_pip_packages())
    results.append(check_node())
    results.append(check_npm_packages())
    check_llm_providers()
    check_optional()

    print("\n" + "=" * 50)
    if all(results):
        write_env_info()
        print(f"  {GREEN}環境セットアップ完了 — すべてOKです{RESET}")
        print("=" * 50)
        return 0
    else:
        print(f"  {RED}一部の必須要件を満たしていません{RESET}")
        print("=" * 50)
        return 1


if __name__ == "__main__":
    sys.exit(main())
