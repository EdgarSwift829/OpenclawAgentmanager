# CLAUDE.md

## 応答言語ルール（最優先）

- すべての応答・説明・会話は日本語で書いてください。
- コードやコマンド、ファイル名、技術用語はそのまま英語でOKですが、文章部分は必ず日本語にしてください。
- ユーザーが英語で質問した場合でも、日本語で返答してください。

# Project Instructions

## 1. プロジェクトにおける注意点

＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝
ここに **このプロジェクト固有の内容** を記述する。

このセクションはワークスペース共通ルールではなく、
**このプロジェクト専用の仕様・前提・注意事項を書く場所**である。

記述例：

・このプロジェクトの目的\
・このプロジェクトの責務\
・関連する別プロジェクト（ある場合のみ）\
・変更してよい範囲\
・変更してはいけない範囲\
・起動方法\
・主要ディレクトリの意味\
・特別な依存関係

注意： この部分は **各プロジェクトごとに内容が変わる前提**。
共通ルールはここに書かない。
＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝＝

---

# Project Overview

This repository is part of the OpenClaw workspace.

Primary goals:

- Maintain a clean and stable local development workflow.
- Prefer small, reversible changes.
- Keep project boundaries clear between independent projects.
- Preserve compatibility with Windows paths, Docker usage, and local
  LLM workflows.

Current environment assumptions:

- Main storage root is on `E:AI Storage`
- Claude Code may be launched from PowerShell in each project
  directory
- Docker is available
- Ollama is installed and runs locally
- ByteRover is connected for project memory

---

# Workspace Structure

Expected top-level structure:

    E:AI Storage
    ├ projects
    │  ├ 〇〇〇〇〇〇
    │  ├ △△△△
    │  └ <future-projects>
    ├ runtime
    │  ├ data
    │  ├ logs
    │  └ workspace
    ├ config
    ├ docker
    ├ scripts
    └ archive

Notes:

- `〇〇〇〇〇〇` and `△△△△` are **placeholder names used as examples
  only**.
- Actual project names may differ.
- Each directory under `projects/` must be treated as **an independent
  project**.
- Projects should not implicitly depend on each other unless
  explicitly designed.

Rules:

- Treat each folder under `projects/` as an independent Claude Code
  project scope.
- Do not mix runtime outputs, logs, installers, and source code in the
  same directory unless explicitly required.
- Prefer placing reusable scripts under `scripts/`.
- Prefer placing environment-specific runtime artifacts under
  `runtime/`.

---

# How to Work in This Repository

When working in this project:

1.  First inspect the current directory structure.
2.  Identify whether the task belongs to:
    - application code
    - installer/setup logic
    - Docker/runtime configuration
    - scripts/automation
    - config/log/data handling
3.  Before making broad edits, summarize:
    - what is changing
    - why it is changing
    - which files will be affected
4.  Prefer incremental edits over large rewrites.
5.  When a change may affect startup, install flow, file paths, Docker
    behavior, or persistence, call that out explicitly.

---

# Coding Principles

- Prefer simple and explicit implementations.
- Preserve existing behavior unless the task explicitly asks for
  refactoring or redesign.
- Avoid introducing hidden coupling between independent projects.
- Keep path handling robust across Windows-oriented environments.
- Avoid hardcoding paths when a config value or environment variable
  is more appropriate.
- Prefer clear logging for install, startup, and runtime operations.
- Do not silently delete, migrate, or overwrite user data.

---

# File and Change Rules

- For existing files, prefer targeted edits.
- For new functionality, create new files only when it improves
  structure.
- Do not rename or move major folders unless explicitly requested.
- If a folder restructure is needed, propose the target structure
  first.
- When editing startup scripts or batch files, preserve ease of use
  for non-technical operation.

If changing configuration-sensitive files, explain impact clearly:

- `.env`
- `docker-compose.yml`
- `Dockerfile`
- `*.ini`
- startup scripts like `.bat`, `.vbs`, `.ps1`

---

# Docker Rules

When Docker-related files are involved:

- Prefer minimal changes.
- Do not change ports, volumes, or service names without explaining
  impact.
- Preserve persistent data locations whenever possible.
- If `docker compose up -d` is expected in workflow, keep
  configuration compatible with that assumption.
- Flag any change that requires rebuild, restart, or data migration.

---

# Local LLM / Ollama Rules

- Assume Ollama is locally available.
- Do not redesign the LLM integration path unless explicitly
  requested.
- If suggesting model or provider changes, separate them from core
  application logic.
- Prefer configuration-driven model/provider selection.
- Keep local/offline workflows viable.

---

# Installer / Setup Rules

For installer-related work:

- Prioritize reproducibility and safe reruns.
- Avoid destructive operations by default.
- Make install steps observable through logs.
- Prefer idempotent setup logic where possible.
- Distinguish clearly between:
  - install-time files
  - runtime files
  - user data
  - temporary work files

---

# Claude Code Behavior Preferences

When assisting in this project:

- Start by understanding the current structure before proposing
  changes.
- For non-trivial work, give a short implementation plan first.
- For risky changes, explicitly mention risk.
- When multiple options exist, recommend one and briefly explain why.
- Keep responses practical and implementation-oriented.
- Prefer copy-paste-ready commands when command-line action is needed.

---

# Output Format Preferences

When making code or file change suggestions:

- Be explicit about whether the action is:
  - replace existing file
  - edit existing file
  - create new file if absent
- Prefer wording like:
  - `Replace`
  - `Edit`
  - `Create if missing`
- Avoid ambiguous instructions.

---

# Project Startup Expectations

Typical workflow for a project under `E:AI Storage\projects\...`:

1.  Open PowerShell in the target project folder
2.  Run `claude`
3.  Use project-local context as the primary scope

If startup scripts are created, keep them simple and project-specific.
Example pattern:

- `start_project_claude.bat`

---

# What to Avoid

- Unrequested large-scale rewrites
- Silent path changes
- Mixing unrelated project concerns
- Destructive cleanup without confirmation
- Introducing unnecessary dependencies
- Overengineering simple local workflows

---

# Preferred Assistance Style for This Workspace

- Clear
- Direct
- Structured
- Conservative with risk
- Aware of Windows + Docker + local LLM realities

When unsure, inspect first, then propose the smallest correct change.
