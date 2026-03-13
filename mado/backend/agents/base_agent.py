"""BaseAgent - Abstract base class for all agents.

Enhanced with:
- Tool dispatch (file, exec, web, memory)
- Message bus integration for inter-agent communication
- Project rules (must/forbidden) injection into system prompts
- Iteration context awareness (previous results feed into next iteration)
- JSON extraction from LLM responses
- Structured output format
"""

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Default agent profiles - used when user hasn't configured custom profiles
# Each personality serves as a professional preset that defines the agent's
# expertise, approach, and behavioral guidelines. Users can override per-project.
DEFAULT_AGENT_PROFILES = {
    "cto": {
        "title": "最高技術責任者",
        "personality": (
            "あなたは10年以上の経験を持つ最高技術責任者（CTO）です。\n"
            "【専門領域】システムアーキテクチャ設計、技術スタック選定、スケーラビリティ戦略、セキュリティ設計\n"
            "【行動指針】\n"
            "- 要件を分析し、最適な技術スタックとアーキテクチャを提案する\n"
            "- 複雑な問題を実行可能なフェーズに分解し、依存関係を明確にする\n"
            "- リスク（技術的負債、スケーラビリティ、セキュリティ）を事前に評価する\n"
            "- チーム構成を提案し、各ロールに適切なタスクを配分する\n"
            "【スタイル】先見性のある判断、現実的なトレードオフ、簡潔で根拠のある意思決定"
        ),
    },
    "manager": {
        "title": "プロジェクトマネージャー",
        "personality": (
            "あなたは複数プロジェクトを成功に導いてきたプロジェクトマネージャーです。\n"
            "【専門領域】タスク分解、依存関係管理、スケジューリング、リソース配分、進捗管理\n"
            "【行動指針】\n"
            "- CTOの計画を具体的なタスクに分解し、優先度と依存関係を設定する\n"
            "- 各タスクに最適なエージェント（ロール）をアサインする\n"
            "- 並列実行可能なタスクを特定し、効率的なDAGを構築する\n"
            "- ブロッカーを早期発見し、代替案を提示する\n"
            "【スタイル】組織的、明確な優先順位、現実的な見積もり、チーム全体の生産性最大化"
        ),
    },
    "researcher": {
        "title": "シニアテクニカルリサーチャー",
        "personality": (
            "あなたは技術調査と分析のプロフェッショナルです。\n"
            "【専門領域】技術評価、ベストプラクティス調査、競合分析、PoC設計、技術トレンド分析\n"
            "【行動指針】\n"
            "- 複数の選択肢を比較し、メリット・デメリットを客観的に整理する\n"
            "- 公式ドキュメント・実績・コミュニティ評価に基づいて推薦する\n"
            "- 「なぜその技術か」を具体的な数値や事例で裏付ける\n"
            "- 未知の技術リスクを明示し、検証方法を提案する\n"
            "【スタイル】徹底的な調査、実用的なインサイト、バイアスのない比較、簡潔な結論"
        ),
    },
    "engineer": {
        "title": "シニアフルスタックエンジニア",
        "personality": (
            "あなたは生産性が高く品質を重視するシニアエンジニアです。\n"
            "【専門領域】フロントエンド/バックエンド開発、DB設計、API設計、テスト駆動開発\n"
            "【行動指針】\n"
            "- 仕様に忠実に、動作する完全なコードを書く（スタブや省略は避ける）\n"
            "- シンプルさと可読性を最優先にする（巧妙なコードより明快なコード）\n"
            "- エラーハンドリング、バリデーション、エッジケースを考慮する\n"
            "- プロジェクトの既存パターンとコーディング規約に従う\n"
            "- 変更理由と影響範囲をコメントで明記する\n"
            "【スタイル】実装ファースト、動くコード、段階的改善、YAGNI原則"
        ),
    },
    "reviewer": {
        "title": "シニアコードレビュアー",
        "personality": (
            "あなたは厳格だが建設的なコードレビューの専門家です。\n"
            "【専門領域】コード品質、セキュリティ監査、設計パターン、パフォーマンス分析\n"
            "【行動指針】\n"
            "- バグ、セキュリティ脆弱性、ロジックエラーを見逃さない\n"
            "- 問題を指摘する際は必ず具体的な修正案を提示する\n"
            "- 重要度でレビュー指摘を分類する（MUST FIX / SHOULD FIX / NICE TO HAVE）\n"
            "- 良い実装には積極的にポジティブフィードバックを与える\n"
            "- 開発者の意図を理解した上で、より良い代替案を提案する\n"
            "【スタイル】綿密、建設的、具体的、スコアリング（10点満点）で品質を評価"
        ),
    },
    "tester": {
        "title": "QAエンジニア",
        "personality": (
            "あなたは「壊れるまでテストする」を信条とするQAのプロフェッショナルです。\n"
            "【専門領域】テスト設計、自動テスト、E2Eテスト、負荷テスト、回帰テスト\n"
            "【行動指針】\n"
            "- 正常系だけでなく、境界値・異常系・競合状態を網羅するテストを設計する\n"
            "- テストピラミッド（Unit > Integration > E2E）に基づくバランスの良い構成\n"
            "- 再現可能で独立したテストケースを作成する\n"
            "- テストカバレッジと実行速度のバランスを保つ\n"
            "- バグ発見時は再現手順・期待値・実測値を明確に報告する\n"
            "【スタイル】体系的、エッジケースへの執着、自動化優先、CI/CD統合"
        ),
    },
    "optimizer": {
        "title": "パフォーマンスエンジニア",
        "personality": (
            "あなたは「計測なくして最適化なし」を信条とするパフォーマンス専門家です。\n"
            "【専門領域】プロファイリング、ボトルネック分析、アルゴリズム最適化、キャッシュ戦略\n"
            "【行動指針】\n"
            "- まず計測し、データに基づいてボトルネックを特定する\n"
            "- N+1クエリ、不要な再計算、メモリリーク、過度なI/Oを検出する\n"
            "- 最適化前後のベンチマーク数値を必ず提示する\n"
            "- 可読性を犠牲にしすぎない最適化を選ぶ\n"
            "- バンドルサイズ、レスポンスタイム、メモリ使用量を常に意識する\n"
            "【スタイル】データ駆動、計測→分析→改善のサイクル、実証的アプローチ"
        ),
    },
    "documenter": {
        "title": "テクニカルライター",
        "personality": (
            "あなたは「読まれないドキュメントは存在しないのと同じ」を信条とするテクニカルライターです。\n"
            "【専門領域】API仕様書、アーキテクチャドキュメント、README、チュートリアル、変更履歴\n"
            "【行動指針】\n"
            "- 対象読者（開発者/エンドユーザー/運用者）に合わせた粒度で書く\n"
            "- セットアップ手順はコピペで動くレベルの具体性を保つ\n"
            "- コード例は実際に動作するスニペットを使う\n"
            "- 図・表・構成図を積極的に活用して視覚的にわかりやすくする\n"
            "- 変更があったら即座にドキュメントも更新する\n"
            "【スタイル】明瞭、実践的、構造化、開発者が実際に読みたくなる文書"
        ),
    },
    "marketer": {
        "title": "グロースマーケティングスペシャリスト",
        "personality": (
            "あなたはデータ駆動で成長戦略を立案するマーケティングのプロフェッショナルです。\n"
            "【専門領域】市場分析、SEO/SEM、コンテンツマーケティング、SNS戦略、ローンチ計画\n"
            "【行動指針】\n"
            "- 技術的な機能をユーザーが理解できる価値提案に変換する\n"
            "- ターゲットユーザーのペルソナを明確にし、刺さるメッセージを設計する\n"
            "- 競合との差別化ポイントを数値やデータで裏付ける\n"
            "- ローンチ前・中・後のフェーズ別施策を計画する\n"
            "【スタイル】データ駆動、ユーザー視点、魅力的なストーリーテリング、効果測定重視"
        ),
    },
}


class BaseAgent(ABC):
    """Base class that all agents inherit from."""

    def __init__(self, role: str, model: dict, workspace_path: str):
        self.role = role
        self.model = model
        self.workspace_path = workspace_path
        self.tools: list = []
        self.iteration_count = 0
        self.max_retries = 3
        # Inter-agent collaboration
        self.message_bus = None
        self.project_config: dict = {}
        self.iteration_context: list = []  # summaries from previous iterations
        self.shared_context: dict = {}  # shared data from other agents in this iteration

    # ── Tool dispatch ──────────────────────────────────────────────

    def get_tool(self, tool_class_name: str):
        """Get an attached tool by class name (e.g. 'FileTools', 'ExecTools')."""
        for tool in self.tools:
            if type(tool).__name__ == tool_class_name:
                return tool
        return None

    @property
    def file_tools(self):
        return self.get_tool("FileTools")

    @property
    def exec_tools(self):
        return self.get_tool("ExecTools")

    @property
    def web_tools(self):
        return self.get_tool("WebTools")

    @property
    def memory_tools(self):
        return self.get_tool("MemoryTools")

    def read_file(self, path: str) -> str:
        """Read a file from workspace. Returns content or error string."""
        ft = self.file_tools
        if not ft:
            return "[Error] FileTools not available"
        try:
            return ft.read_file(path)
        except Exception as e:
            return f"[Error reading {path}]: {e}"

    def write_file(self, path: str, content: str) -> str:
        """Write a file to workspace. Returns confirmation or error."""
        ft = self.file_tools
        if not ft:
            return "[Error] FileTools not available"
        try:
            return ft.write_file(path, content)
        except Exception as e:
            return f"[Error writing {path}]: {e}"

    def list_files(self, path: str = ".") -> list:
        """List files in workspace directory."""
        ft = self.file_tools
        if not ft:
            return []
        try:
            return ft.list_dir(path)
        except Exception as e:
            logger.warning(f"list_files failed: {e}")
            return []

    def search_code(self, query: str) -> list:
        """Search code in workspace."""
        ft = self.file_tools
        if not ft:
            return []
        try:
            return ft.search_code(query)
        except Exception as e:
            logger.warning(f"search_code failed: {e}")
            return []

    def run_command(self, script_path: str, timeout: int = 60) -> dict:
        """Run a Python script in workspace."""
        et = self.exec_tools
        if not et:
            return {"error": "ExecTools not available"}
        try:
            return et.run_python(script_path, timeout)
        except Exception as e:
            return {"error": str(e)}

    def run_tests(self, test_path: str = ".", timeout: int = 120) -> dict:
        """Run tests in workspace."""
        et = self.exec_tools
        if not et:
            return {"error": "ExecTools not available"}
        try:
            return et.run_tests(test_path, timeout)
        except Exception as e:
            return {"error": str(e)}

    def search_web(self, query: str, max_results: int = 5) -> list:
        """Search the web via SearXNG."""
        wt = self.web_tools
        if not wt:
            return [{"error": "WebTools not available"}]
        try:
            return wt.search_web(query, max_results)
        except Exception as e:
            return [{"error": str(e)}]

    def load_project_memory(self) -> str:
        """Load project memory."""
        mt = self.memory_tools
        if not mt:
            return ""
        try:
            return mt.load_project_memory()
        except Exception:
            return ""

    def save_memory(self, section: str, content: str) -> str:
        """Save to project memory."""
        mt = self.memory_tools
        if not mt:
            return "[Error] MemoryTools not available"
        try:
            return mt.update_project_memory(section, content)
        except Exception as e:
            return f"[Error]: {e}"

    # ── Project rules & context ────────────────────────────────────

    def build_system_prompt(self, extra_instructions: str = "") -> str:
        """Build a complete system prompt including role, rules, and context."""
        parts = []

        # Role identity
        template = self.load_prompt_template()
        if template:
            parts.append(template)
        else:
            parts.append(f"You are a {self.role} agent in a multi-agent development team.")

        # Agent identity: preset (immutable) is always included
        default_profile = DEFAULT_AGENT_PROFILES.get(self.role, {})
        preset_personality = default_profile.get("personality", "")
        preset_title = default_profile.get("title", "")

        if preset_personality:
            parts.append(f"\n## Your Personality (Preset)\n{preset_personality}")
        if preset_title:
            parts.append(f"Your title: {preset_title}")

        # Additional prompt from selected profile (user-customizable layer)
        agent_profiles = self.project_config.get("agent_profiles", {})
        user_profile = agent_profiles.get(self.role, {})
        additional = user_profile.get("additional_prompt", "")
        if additional:
            parts.append(f"\n## Additional Context\n{additional}")

        # Project rules (MUST / FORBIDDEN)
        rules_must = self.project_config.get("rules_must", "")
        rules_forbidden = self.project_config.get("rules_forbidden", "")
        if rules_must or rules_forbidden:
            parts.append("\n## Project Rules (CRITICAL - You MUST follow these)")
            if rules_must:
                parts.append(f"### MUST follow:\n{rules_must}")
            if rules_forbidden:
                parts.append(f"### FORBIDDEN (NEVER do these):\n{rules_forbidden}")

        # Project goal & overview
        goal = self.project_config.get("goal", "")
        if goal:
            parts.append(f"\n## Project Goal\n{goal}")

        overview = self.project_config.get("overview", "")
        if overview:
            parts.append(f"\n## Project Overview\n{overview}")

        # Extra instructions (role-specific)
        if extra_instructions:
            parts.append(f"\n## Additional Instructions\n{extra_instructions}")

        # Output format
        parts.append(
            "\n## Output Format\n"
            "Always respond with valid JSON. Wrap your response in ```json ... ``` blocks.\n"
            "If you cannot produce JSON, prefix your response with 'PLAIN:' and write free text."
        )

        return "\n".join(parts)

    def build_iteration_context(self) -> str:
        """Build context string from previous iterations."""
        if not self.iteration_context:
            return ""
        parts = ["## Previous Iteration Results"]
        for ctx in self.iteration_context[-3:]:  # Last 3 iterations max
            it_num = ctx.get("iteration", "?")
            summary = ctx.get("summary", "")
            parts.append(f"### Iteration {it_num}\n{summary}")
        return "\n".join(parts)

    def build_shared_context(self) -> str:
        """Build context from other agents' outputs in this iteration."""
        if not self.shared_context:
            return ""
        parts = ["## Other Agents' Outputs (this iteration)"]
        for agent_role, output in self.shared_context.items():
            if agent_role != self.role:
                # Truncate long outputs
                text = str(output)[:2000]
                parts.append(f"### {agent_role}\n{text}")
        return "\n".join(parts)

    # ── LLM interaction ────────────────────────────────────────────

    @abstractmethod
    def execute(self, task: dict) -> dict:
        """Execute a given task and return results."""
        pass

    def call_llm(self, prompt: str, system_prompt: Optional[str] = None,
                  project_memory: str = "", retrieved_files: list = None) -> str:
        """Send prompt to the assigned LLM model with token-optimized context."""
        from mado.backend.models.router import route_inference
        from mado.backend.token_optimizer import TokenOptimizer

        optimizer = TokenOptimizer()

        # Auto-load project memory if not provided
        if not project_memory:
            project_memory = self.load_project_memory()

        # Build full system prompt with rules and context
        if system_prompt is None:
            system_prompt = self.build_system_prompt()

        optimized_prompt = optimizer.build_context(
            system_prompt=system_prompt,
            task=prompt,
            project_memory=project_memory,
            retrieved_files=retrieved_files or [],
            iteration_summaries=self.iteration_context,
        )
        return route_inference(
            model=self.model,
            prompt=optimized_prompt,
            system_prompt=None,
        )

    def call_llm_json(self, prompt: str, system_prompt: Optional[str] = None,
                       fallback: Any = None) -> Any:
        """Call LLM and parse JSON from response. Returns fallback on parse failure."""
        response = self.call_llm(prompt, system_prompt)
        parsed = self.extract_json(response)
        if parsed is not None:
            return parsed
        logger.warning(f"[{self.role}] Failed to parse JSON from LLM response, using fallback")
        return fallback if fallback is not None else response

    # ── JSON parsing helpers ───────────────────────────────────────

    @staticmethod
    def extract_json(text: str) -> Any:
        """Extract JSON from LLM response. Handles ```json blocks and raw JSON."""
        if not text:
            return None

        # Try ```json ... ``` blocks first
        json_blocks = re.findall(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
        for block in json_blocks:
            try:
                return json.loads(block.strip())
            except json.JSONDecodeError:
                continue

        # Try raw JSON (object or array)
        for pattern in [r'\{.*\}', r'\[.*\]']:
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                try:
                    return json.loads(match)
                except json.JSONDecodeError:
                    continue

        return None

    @staticmethod
    def extract_list_from_text(text: str, valid_items: list = None) -> list:
        """Extract a list of items from free text (e.g. role names)."""
        if not text:
            return []
        # Try JSON first
        parsed = BaseAgent.extract_json(text)
        if isinstance(parsed, list):
            if valid_items:
                return [item for item in parsed if item in valid_items]
            return parsed

        # Fall back to finding known items in text
        if valid_items:
            found = []
            text_lower = text.lower()
            for item in valid_items:
                if item.lower() in text_lower:
                    found.append(item)
            return found
        return []

    # ── Standard result format ─────────────────────────────────────

    def make_result(self, result: Any, files_modified: list = None,
                    summary: str = "", error: bool = False) -> dict:
        """Create a standardized result dict."""
        return {
            "role": self.role,
            "result": result,
            "summary": summary or str(result)[:200],
            "files_modified": files_modified or [],
            "error": error,
        }

    # ── Prompt template ────────────────────────────────────────────

    def load_prompt_template(self) -> str:
        """Load the prompt template for this agent role."""
        from pathlib import Path
        prompt_path = Path(__file__).resolve().parents[3] / "prompts" / f"{self.role}.txt"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        return ""

    def attach_tools(self, tools: list) -> None:
        """Attach tools to this agent."""
        self.tools = tools
