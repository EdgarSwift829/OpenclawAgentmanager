#!/usr/bin/env python3
"""
Sample project seeder for MADO.

Creates a sample project with pre-filled goal, overview, roadmap,
policy, tasks, and agent assignments so you can immediately test
the UI and agent orchestration flow.

Usage:
    python scripts/seed_sample_project.py          # default sample
    python scripts/seed_sample_project.py --clean   # delete & recreate
    python scripts/seed_sample_project.py --run     # create + start run

Requires: backend running at http://127.0.0.1:8000
"""

import argparse
import json
import sys
import urllib.request
import urllib.error

API = "http://127.0.0.1:8000/api"

# ──────────────────────────────────────────────────
# Sample project data
# ──────────────────────────────────────────────────

SAMPLE_PROJECT_ID = "sample-todo-app"

SAMPLE_CONFIG = {
    "goal": (
        "Todoアプリ（React + FastAPI）を構築する。\n"
        "ユーザーはタスクの作成・編集・削除・完了切替ができる。\n"
        "フロントエンドはReact + TypeScript、バックエンドはFastAPI + SQLiteを使用。"
    ),
    "overview": (
        "シンプルなフルスタックTodoアプリ。\n"
        "- フロントエンド: React 18 + TypeScript + Vite\n"
        "- バックエンド: FastAPI + SQLite (aiosqlite)\n"
        "- REST API: CRUD操作 (/api/todos)\n"
        "- デプロイ: Docker Compose"
    ),
    "policy": (
        "- コードはTypeScriptで型安全に書く\n"
        "- APIは RESTful 設計に従う\n"
        "- エラーハンドリングを適切に行う\n"
        "- テストカバレッジ80%以上を目標\n"
        "- コミットメッセージは Conventional Commits 形式"
    ),
    "roadmap": (
        "Phase 1: バックエンドAPI実装 (CRUD + DB)\n"
        "Phase 2: フロントエンド実装 (React UI)\n"
        "Phase 3: フロント⇔バック結合\n"
        "Phase 4: テスト + コードレビュー\n"
        "Phase 5: Docker化 + ドキュメント"
    ),
    "description": "MADO動作テスト用サンプルプロジェクト",
    "deadline": "2026-03-31",
    "tasks": [
        {
            "id": "task-1",
            "title": "FastAPIバックエンドのCRUD API実装",
            "description": "GET/POST/PUT/DELETE /api/todos エンドポイントを実装",
            "status": "pending",
            "deadline": "2026-03-20",
            "priority": "high",
        },
        {
            "id": "task-2",
            "title": "SQLiteデータベーススキーマ設計",
            "description": "todosテーブル (id, title, completed, created_at, updated_at)",
            "status": "pending",
            "deadline": "2026-03-18",
            "priority": "high",
        },
        {
            "id": "task-3",
            "title": "Reactフロントエンド UI構築",
            "description": "TodoList / TodoItem / AddTodo コンポーネントの実装",
            "status": "pending",
            "deadline": "2026-03-25",
            "priority": "medium",
        },
        {
            "id": "task-4",
            "title": "API統合テスト",
            "description": "pytest + httpx でバックエンドAPIの結合テストを作成",
            "status": "pending",
            "deadline": "2026-03-28",
            "priority": "medium",
        },
        {
            "id": "task-5",
            "title": "Docker Compose構成",
            "description": "frontend + backend + db の docker-compose.yml を作成",
            "status": "pending",
            "deadline": "2026-03-30",
            "priority": "low",
        },
    ],
    "agents": ["cto", "manager", "engineer", "reviewer", "tester"],
}

# ──────────────────────────────────────────────────
# HTTP helpers
# ──────────────────────────────────────────────────

def api_call(method: str, path: str, body: dict | None = None) -> dict:
    url = f"{API}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode() if e.fp else ""
        return {"_error": e.code, "_detail": body_text}
    except urllib.error.URLError as e:
        print(f"[ERROR] Backend not reachable: {e.reason}")
        sys.exit(1)


def check_backend():
    result = api_call("GET", "/health")
    if result.get("status") != "ok":
        print("[ERROR] Backend health check failed")
        sys.exit(1)
    print("[OK] Backend is running")


def project_exists(pid: str) -> bool:
    result = api_call("GET", f"/projects/{pid}")
    return "_error" not in result


def delete_project(pid: str):
    result = api_call("DELETE", f"/projects/{pid}")
    if result.get("_error"):
        print(f"[WARN] Delete failed: {result.get('_detail', 'unknown')}")
    else:
        print(f"[OK] Deleted existing project: {pid}")


def create_project(pid: str):
    result = api_call("POST", "/projects/", {"project_id": pid, "goal": SAMPLE_CONFIG["goal"]})
    if result.get("_error"):
        detail = result.get("_detail", "")
        if "409" in str(result.get("_error", "")) or "already exists" in detail:
            print(f"[SKIP] Project already exists: {pid}")
            return True
        print(f"[ERROR] Create failed: {detail}")
        return False
    print(f"[OK] Created project: {pid}")
    return True


def configure_project(pid: str):
    updates = {k: v for k, v in SAMPLE_CONFIG.items() if k != "agents"}
    result = api_call("PUT", f"/projects/{pid}/config", updates)
    if result.get("_error"):
        print(f"[ERROR] Config update failed: {result.get('_detail', '')}")
        return False
    print(f"[OK] Configured project with goal, overview, roadmap, tasks")
    return True


def start_run(pid: str):
    result = api_call("POST", "/orchestrator/run", {
        "project_id": pid,
        "goal": SAMPLE_CONFIG["goal"],
        "max_iterations": 3,
    })
    if result.get("_error"):
        print(f"[ERROR] Start run failed: {result.get('_detail', '')}")
        return False
    print(f"[OK] Started orchestrator run for: {pid}")
    return True


# ──────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Seed a sample project for MADO testing")
    parser.add_argument("--clean", action="store_true", help="Delete existing project first")
    parser.add_argument("--run", action="store_true", help="Also start an orchestrator run")
    parser.add_argument("--id", default=SAMPLE_PROJECT_ID, help=f"Project ID (default: {SAMPLE_PROJECT_ID})")
    args = parser.parse_args()

    print("=" * 50)
    print("  MADO Sample Project Seeder")
    print("=" * 50)

    check_backend()

    pid = args.id

    if args.clean and project_exists(pid):
        delete_project(pid)

    if not project_exists(pid):
        if not create_project(pid):
            sys.exit(1)
    else:
        print(f"[SKIP] Project already exists: {pid}")

    if not configure_project(pid):
        sys.exit(1)

    print()
    print(f"  Project: {pid}")
    print(f"  Goal:    {SAMPLE_CONFIG['goal'][:50]}...")
    print(f"  Tasks:   {len(SAMPLE_CONFIG['tasks'])}")
    print(f"  Agents:  {', '.join(SAMPLE_CONFIG['agents'])}")
    print()

    if args.run:
        start_run(pid)

    print("=" * 50)
    print("  Done! Open http://127.0.0.1:3000 and select the project.")
    print("=" * 50)


if __name__ == "__main__":
    main()
