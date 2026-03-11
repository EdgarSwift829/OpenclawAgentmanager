"""MADO Environment Checker - Verify and install all dependencies."""

import subprocess
import sys
import shutil
from pathlib import Path

MADO_ROOT = Path(__file__).resolve().parent
BACKEND_DIR = MADO_ROOT / "backend"
FRONTEND_DIR = MADO_ROOT / "frontend"
REQUIREMENTS_TXT = BACKEND_DIR / "requirements.txt"

# ANSI colors (works on Windows 10+ terminal)
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"


def ok(msg: str) -> None:
    print(f"  {GREEN}[OK]{RESET} {msg}")


def warn(msg: str) -> None:
    print(f"  {YELLOW}[!!]{RESET} {msg}")


def fail(msg: str) -> None:
    print(f"  {RED}[NG]{RESET} {msg}")


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


# ── pip packages check & install ────────────────────────────────
def check_pip_packages() -> bool:
    print("\n── Backend pip packages ──")
    if not REQUIREMENTS_TXT.exists():
        fail(f"{REQUIREMENTS_TXT} が見つかりません")
        return False

    # Parse required packages from requirements.txt
    required: list[str] = []
    for line in REQUIREMENTS_TXT.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Extract package name (before any version specifier)
        name = line.split(">=")[0].split("<=")[0].split("==")[0].split("[")[0].strip()
        required.append(name)

    # Check which are already installed
    result = run([sys.executable, "-m", "pip", "list", "--format=columns"])
    installed = set()
    for pip_line in result.stdout.splitlines()[2:]:  # skip header
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
        print(f"\n  → 不足パッケージをインストール中: {', '.join(missing)}")
        result = run(
            [sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS_TXT)],
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
    if not node_modules.exists():
        warn("node_modules が存在しません — npm install を実行します")
        result = run(["npm", "install"], cwd=str(FRONTEND_DIR))
        if result.returncode != 0:
            fail("npm install に失敗しました:")
            print(result.stderr)
            return False
        ok("npm install 完了")
    else:
        ok("node_modules 確認済み")

    return True


# ── Optional tools check ────────────────────────────────────────
def check_optional() -> None:
    print("\n── Optional ──")

    # Ollama
    if shutil.which("ollama"):
        result = run(["ollama", "--version"])
        ver = result.stdout.strip() or result.stderr.strip()
        ok(f"Ollama: {ver}")
    else:
        warn("Ollama が見つかりません（ローカルLLM未使用なら問題なし）")

    # Docker
    if shutil.which("docker"):
        result = run(["docker", "--version"])
        ok(result.stdout.strip())
    else:
        warn("Docker が見つかりません（Docker未使用なら問題なし）")


# ── Main ────────────────────────────────────────────────────────
def main() -> int:
    print("=" * 50)
    print("  MADO 環境チェック")
    print("=" * 50)

    results = []
    results.append(check_python())
    results.append(check_pip_packages())
    results.append(check_node())
    results.append(check_npm_packages())
    check_optional()

    print("\n" + "=" * 50)
    if all(results):
        print(f"  {GREEN}環境チェック完了 — すべてOKです{RESET}")
        print("=" * 50)
        return 0
    else:
        print(f"  {RED}一部の必須要件を満たしていません{RESET}")
        print("=" * 50)
        return 1


if __name__ == "__main__":
    sys.exit(main())
