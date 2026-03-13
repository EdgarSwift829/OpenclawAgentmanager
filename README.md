# MADO - Multi-Agent Dev Orchestrator

ローカル LLM（Ollama / vLLM）を活用したマルチエージェント開発オーケストレーター。
複数の専門エージェントが協調してソフトウェア開発タスクを自律的に遂行します。

## アーキテクチャ

```
┌─────────────────────────────────────────────────┐
│                  FastAPI Server                  │
│               (REST + WebSocket)                 │
├─────────────────────────────────────────────────┤
│                  Orchestrator                    │
│   CTO → Manager → Agents → Reviewer (max 10回)  │
├──────────┬──────────┬──────────┬────────────────┤
│  Models  │  Memory  │  Safety  │     Tools      │
│ Manager  │  Vector  │ Sandbox  │  File / Web /  │
│ + Router │  Store   │ + Limits │  Exec / Memory │
└──────────┴──────────┴──────────┴────────────────┘
         ↓               ↓
    Ollama / vLLM    Project Workspace
```

## エージェント一覧

| ロール | 役割 | デフォルトモデル |
|--------|------|-----------------|
| **CTO** | 目標分析・全体方針決定 | qwen3.5-9b |
| **Manager** | タスク分解・進捗管理 | qwen3.5-9b |
| **Researcher** | 調査・情報収集 | qwen3.5-9b |
| **Engineer** | 実装・コーディング | qwen2.5-coder-7b |
| **Reviewer** | コードレビュー・承認判定 | qwen3.5-9b |
| **Tester** | テスト作成・実行 | qwen2.5-coder-7b |
| **Optimizer** | パフォーマンス最適化 | qwen2.5-coder-7b |
| **Documenter** | ドキュメント生成 | qwen3.5-9b |

モデル割当は `config/agents.yaml` で設定、ランタイムで API 経由の切替も可能。

## セットアップ

### 前提条件

- Python 3.10+
- [Ollama](https://ollama.ai/) （ローカル LLM 推論）
- モデルの事前ダウンロード:
  ```bash
  ollama pull qwen3.5:9b
  ollama pull qwen2.5-coder:7b
  ```

### インストール

```bash
pip install -r requirements.txt
```

### 起動

```bash
python run.py
# or
python run.py --host 0.0.0.0 --port 8000
```

サーバーが `http://localhost:8000` で起動します。

## API エンドポイント

| メソッド | パス | 説明 |
|----------|------|------|
| GET | `/api/health` | ヘルスチェック |
| GET | `/api/projects/` | プロジェクト一覧 |
| POST | `/api/projects/` | プロジェクト作成 |
| GET | `/api/projects/{id}` | プロジェクト詳細 |
| GET | `/api/projects/{id}/memory` | プロジェクトメモリ |
| GET | `/api/agents/{project_id}` | エージェント一覧 |
| GET | `/api/models/` | 利用可能モデル一覧 |
| GET | `/api/models/assignments` | ロール別モデル割当 |
| PUT | `/api/models/switch` | モデル切替 |
| POST | `/api/orchestrator/run` | オーケストレーション実行 |
| GET | `/api/orchestrator/runs` | 実行履歴 |
| GET | `/api/logs/{project_id}` | ログ取得 |
| GET | `/api/openclaw/status` | OpenClaw 連携状態 |
| WS | `/api/ws/{project_id}` | リアルタイム通知 |

### 使用例

```bash
# プロジェクト作成
curl -X POST http://localhost:8000/api/projects/ \
  -H "Content-Type: application/json" \
  -d '{"project_id": "my_app", "goal": "Build a REST API"}'

# オーケストレーション実行
curl -X POST http://localhost:8000/api/orchestrator/run \
  -H "Content-Type: application/json" \
  -d '{"project_id": "my_app", "goal": "Build a REST API"}'

# モデル切替
curl -X PUT http://localhost:8000/api/models/switch \
  -H "Content-Type: application/json" \
  -d '{"role": "engineer", "new_model": "deepseek-coder"}'
```

## ディレクトリ構成

```
mado/
├── backend/
│   ├── api/              # FastAPI ルーティング
│   │   ├── main.py       # アプリケーション定義
│   │   └── routes/       # 各エンドポイント
│   ├── agents/           # エージェント実装
│   │   ├── base_agent.py # 抽象基底クラス
│   │   ├── cto.py        # CTO エージェント
│   │   ├── engineer.py   # Engineer エージェント
│   │   └── ...
│   ├── orchestrator/     # オーケストレーション
│   │   ├── orchestrator.py     # メイン実行ループ
│   │   ├── agent_factory.py    # エージェント生成
│   │   └── workspace_manager.py # ワークスペース管理
│   ├── models/           # LLM モデル管理
│   │   ├── model_manager.py    # モデル設定・割当
│   │   └── router.py          # 推論ルーティング
│   ├── memory/           # メモリ・知識管理
│   │   ├── project_memory.py   # プロジェクトメモリ
│   │   └── vector_store.py     # コード検索インデックス
│   ├── tools/            # エージェント用ツール
│   │   ├── file_tools.py       # ファイル操作
│   │   ├── web_tools.py        # Web アクセス
│   │   ├── exec_tools.py       # コード実行
│   │   └── memory_tools.py     # メモリ操作
│   ├── safety/           # 安全機構
│   │   ├── sandbox.py          # コマンド実行制限
│   │   └── agent_limits.py     # 反復・リトライ制限
│   ├── integrations/     # 外部連携
│   │   └── openclaw.py         # OpenClaw 統合
│   ├── logging_system.py # 構造化ログ
│   └── token_optimizer.py # コンテキスト最適化
config/
├── models.yaml           # モデル定義
└── agents.yaml           # ロール別モデル割当
projects/                 # プロジェクトワークスペース
scripts/
└── index_code.py         # コードインデックス生成
```

## 安全機構

- **Sandbox**: 許可コマンドのみ実行（python, pytest, pip）。`rm`, `sudo` 等はブロック
- **Agent Limits**: 最大反復 10 回、リトライ 3 回、タイムアウト 300 秒
- **Workspace Isolation**: 各プロジェクトは隔離されたワークスペースで動作、パストラバーサルを防止
- **Token Optimizer**: LLM コンテキスト予算管理（デフォルト 16,000 トークン）

## 対応 LLM プロバイダ

| プロバイダ | エンドポイント | 備考 |
|-----------|---------------|------|
| Ollama | `localhost:11434` | ローカル推論（推奨） |
| vLLM | `localhost:8000` | 高スループット推論 |

`config/models.yaml` でモデルごとにプロバイダを設定。

## 今後の構想: 自然言語インターフェース連携

MADO の開発オーケストレーション機能を、日常的な PC 操作の自動化にも拡張する構想です。

### コンセプト

```
ユーザー (Telegram)
    │  「今日のメール整理して、重要なのだけ教えて」
    ▼
セキュリティアプリ (常駐)
    │  自然言語をそのままテキストファイルとして書き出し
    ▼
指示フォルダ (共有ディレクトリ)
    │  instructions/pending/20260313_143022.txt
    ▼
MADO (フォルダ監視)
    │  テキストを LLM で解釈 → タスク実行
    ▼
結果フォルダ → セキュリティアプリ → Telegram に返答
```

### 設計方針

- **指示ファイルはプレーンテキスト**: JSON や YAML ではなく、自然言語をそのまま書き出す。LLM が解釈するため、フォーマットを強制しない
- **ファイルベース連携**: プロセス間通信ではなくファイルの読み書きで連携する。シンプルで、デバッグしやすく、障害に強い
- **セキュリティアプリが仲介**: Telegram からの入力を受け取り、MADO への橋渡しと結果の返送を担う

### 想定フォルダ構造

```
runtime/
├── instructions/
│   ├── pending/       # 未処理の指示ファイル
│   ├── processing/    # 処理中
│   └── done/          # 完了済み
└── results/
    └── {対応する指示ID}/  # 実行結果
```

### 特徴

- **機械が苦手な人でも使える**: Telegram に話しかけるだけで PC 操作を自動化できる
- **ローカル完結**: Ollama + MADO でクラウド不要。プライバシーを保てる
- **段階的に拡張可能**: まずメール整理やファイル操作など小さなタスクから始め、徐々に対応範囲を広げる

> **ステータス**: 構想段階。セキュリティアプリ側の Telegram 連携と、MADO 側のフォルダ監視機能を順次実装予定。

## ライセンス

OpenClaw Project
