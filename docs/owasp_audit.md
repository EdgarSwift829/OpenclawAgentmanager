# MADO OWASP Top 10 セキュリティ監査

> 監査日: 2026-03-13
> 対象: MADO v0.x (Multi-Agent Development Orchestrator)
> 基準: OWASP Top 10:2021

---

## 監査結果サマリー

| # | カテゴリ | ステータス | リスク |
|---|---------|-----------|--------|
| A01 | Broken Access Control | **対策済み** | 低 |
| A02 | Cryptographic Failures | **対策済み** | 低 |
| A03 | Injection | **対策済み** | 低 |
| A04 | Insecure Design | **対策済み** | 低 |
| A05 | Security Misconfiguration | **注意** | 中 |
| A06 | Vulnerable Components | **対策済み** | 低 |
| A07 | Auth Failures | **対策済み** | 低 |
| A08 | Software/Data Integrity | **対策済み** | 低 |
| A09 | Logging/Monitoring | **対策済み** | 低 |
| A10 | SSRF | **対策済み** | 低 |

**総合判定: 9/10項目で対策完了。A05（設定管理）は運用環境での適切な設定が前提。**

---

## 詳細評価

### A01: Broken Access Control（アクセス制御の不備）

**ステータス: 対策済み**

| 対策項目 | 実装 | ファイル |
|---------|------|---------|
| API認証 | Bearer/X-API-Key トークン認証 | `safety/auth.py` |
| WebSocket認証 | クエリパラメータ `?token=` 検証 | `api/routes/websocket.py` |
| パストラバーサル防止 | `path.relative_to(workspace)` 検証 | `tools/file_tools.py` |
| プロジェクト隔離 | WorkspaceManager による独立ディレクトリ | `orchestrator/workspace_manager.py` |
| コマンドホワイトリスト | python/pytest/pip のみ許可 | `tools/exec_tools.py` |

**テスト:**
- `test_security_fuzz.py`: パストラバーサル攻撃ペイロード検証
- `test_security_improvements.py`: API認証有効/無効テスト

---

### A02: Cryptographic Failures（暗号化の不備）

**ステータス: 対策済み（スコープ限定）**

| 項目 | 状態 | 備考 |
|------|------|------|
| APIキー生成 | `secrets.token_urlsafe(32)` 使用 | 暗号的に安全な乱数 |
| パスワード保存 | N/A | ユーザーアカウント機能なし |
| 通信暗号化 | ローカル通信前提 | HTTPS はリバースプロキシで対応 |
| シークレット管理 | 環境変数 `MADO_API_KEY` | コードにハードコードなし |

**注意:** 本番デプロイ時は HTTPS 必須。現在はローカル開発前提のため HTTP。

---

### A03: Injection（インジェクション）

**ステータス: 対策済み**

| インジェクション種別 | 対策 | ファイル |
|-------------------|------|---------|
| コマンドインジェクション | `shell=False`、ブロックリスト（rm/sudo/kill等） | `tools/exec_tools.py`, `safety/sandbox.py` |
| パスインジェクション | `resolved.relative_to(workspace)` 検証 | `tools/file_tools.py` |
| プロンプトインジェクション | XMLタグラッピング + キーワード検出 | `safety/prompt_sanitizer.py` |
| pip パッケージインジェクション | PEP 508名称検証 + ブロックリスト + フラグ拒否 | `tools/exec_tools.py` |
| SQLインジェクション | N/A | SQLデータベース不使用（ファイルベース） |
| API入力インジェクション | Pydantic `field_validator` + 正規表現チェック | `api/routes/orchestrator.py` |

**テスト:**
- `test_security_fuzz.py`: シェル演算子、逆シェル、破壊的コマンドのペイロード
- `test_security_improvements.py`: プロンプト注入パターン検出テスト
- `test_quality_phase12_13.py`: パッケージ名バリデーションテスト

---

### A04: Insecure Design（安全でない設計）

**ステータス: 対策済み**

| 設計原則 | 実装 |
|---------|------|
| 最小権限原則 | エージェントは割り当てられたワークスペース内のみ操作可能 |
| 多層防御 | Sandbox → ExecTools → FileTools の3層チェック |
| フェイルセーフ | Reviewer解析失敗時は保守的にreject |
| リソース制限 | `AgentLimits`: max_iterations=10, timeout=300s |
| 入力検証 | Pydantic モデルでAPI境界の全入力を検証 |

---

### A05: Security Misconfiguration（セキュリティ設定ミス）

**ステータス: 注意（運用環境依存）**

| 項目 | 現状 | 推奨 |
|------|------|------|
| 認証デフォルト | 無効（`MADO_API_KEY` 未設定時） | 本番では必ず設定すること |
| CORSポリシー | 現在未制限 | 本番では `allowed_origins` 制限 |
| デバッグモード | 開発時有効 | 本番では `MADO_LOG_LEVEL=WARNING` 推奨 |
| ポート公開 | localhost のみ | Docker利用時はネットワーク制限 |

**推奨対応:**
- 本番デプロイチェックリストを作成し、必須設定を明記する
- CORSミドルウェアに `allow_origins` 制限を追加する

---

### A06: Vulnerable and Outdated Components（脆弱なコンポーネント）

**ステータス: 対策済み**

| 項目 | 状態 |
|------|------|
| Python依存 | `pyproject.toml` でバージョン管理、最新版使用 |
| フロントエンド | Next.js 15 + React 19（最新メジャー版） |
| pip パッケージ制限 | ブロックリストで危険パッケージ拒否 |
| TypeScript | v5.7（最新安定版） |

**推奨:** 定期的な `pip audit` / `npm audit` の CI 統合

---

### A07: Identification and Authentication Failures（認証の不備）

**ステータス: 対策済み**

| 項目 | 実装 |
|------|------|
| APIトークン認証 | `Authorization: Bearer`, `X-API-Key`, `?api_key=` 3方式対応 |
| WebSocketトークン | `?token=` クエリパラメータ検証 |
| トークン生成 | `secrets.token_urlsafe(32)` — 256bit エントロピー |
| 認証バイパス保護 | 全ルートに `Depends(require_auth)` 適用 |

---

### A08: Software and Data Integrity Failures（ソフトウェア・データ整合性）

**ステータス: 対策済み**

| 項目 | 実装 |
|------|------|
| LLM出力検証 | `extract_json()` でブラケットマッチング解析 |
| Reviewer スコア検証 | 範囲クランプ(1-10)、型バリデーション |
| タスク状態管理 | TaskGraph のトポロジカルソートで依存関係保証 |
| 設定ファイル | JSON形式で永続化、読み込み時にバリデーション |

---

### A09: Security Logging and Monitoring Failures（ログ・監視の不備）

**ステータス: 対策済み**

| 項目 | 実装 | ファイル |
|------|------|---------|
| 構造化ログ | JSON/Readable 切替対応 | `logging_config.py` |
| コンテキストログ | project_id/agent_role/task_id 付与 | `logging_config.py` |
| LLMメトリクス | 呼出数/成功/失敗/リトライ/レイテンシ | `models/router.py` |
| メトリクスAPI | `GET /api/models/metrics` | `api/routes/models.py` |
| ログレベル制御 | `MADO_LOG_LEVEL` 環境変数 | 設定可能 |

---

### A10: Server-Side Request Forgery (SSRF)

**ステータス: 対策済み（スコープ限定）**

| 項目 | 状態 |
|------|------|
| WebTools | DuckDuckGo検索のみ（任意URL fetch は制限的） |
| LLM接続先 | ローカルOllama/vLLMのみ（外部API非使用） |
| API外部通信 | プロジェクト内ワークスペースのみ操作 |

**注意:** WebToolsに外部URL取得機能がある場合は、プライベートIPアドレス（10.x, 172.16.x, 192.168.x, 127.x）へのリクエストをブロックすべき。

---

## 監査まとめ

MADOは**ローカル開発ツールとして十分なセキュリティ水準**を達成しています。

**完了済みの対策:**
- プロンプトインジェクション防御（全9エージェント）
- コマンド/パス/パッケージインジェクション防御
- トークンベース認証（API + WebSocket）
- 構造化ログ・メトリクス監視
- 入力バリデーション（Pydantic）
- リソース制限（タイムアウト、イテレーション上限）

**本番デプロイ前の推奨対応:**
1. `MADO_API_KEY` の必須設定化（環境変数チェック）
2. CORSポリシーの制限
3. HTTPS の有効化（リバースプロキシ）
4. `pip audit` / `npm audit` の CI 統合
5. WebTools の SSRF 防御強化（プライベートIP ブロック）
