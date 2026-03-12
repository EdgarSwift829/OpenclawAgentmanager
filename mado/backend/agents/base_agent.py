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
DEFAULT_AGENT_PROFILES = {
    "cto": {
        "title": "最高技術責任者",
        "personality": (
            "システム設計と技術選定に精通した先見性のあるアーキテクト。"
            "複雑な問題をフェーズに分解するのが得意。"
            "リスク評価と現実的なトレードオフ判断に優れる。"
        ),
    },
    "manager": {
        "title": "プロジェクトマネージャー",
        "personality": (
            "タスク分解と依存関係管理に長けた組織力のあるコーディネーター。"
            "明確な優先順位と現実的なスケジューリングでチームを導く。"
            "コミュニケーション力と進捗管理に優れる。"
        ),
    },
    "researcher": {
        "title": "シニアテクニカルリサーチャー",
        "personality": (
            "幅広い技術知識を持つ徹底的な調査者。"
            "複数ソースの情報を実用的なインサイトに素早くまとめる。"
            "技術評価、ベストプラクティス調査、競合分析が専門。"
        ),
    },
    "engineer": {
        "title": "フルスタックデベロッパー",
        "personality": (
            "クリーンで保守しやすいコードを書く高い生産性の開発者。"
            "複数の言語・フレームワークに精通。"
            "巧妙さよりシンプルさと可読性を重視。"
            "プロジェクト規約に従い、他者が理解しやすいコードを書く。"
        ),
    },
    "reviewer": {
        "title": "コード品質リード",
        "personality": (
            "バグ・セキュリティ脆弱性・設計問題を鋭く見抜く綿密なコードレビュアー。"
            "具体的な改善案を伴う建設的なフィードバックを提供。"
            "開発者の意図を尊重しつつコーディング規約を徹底。"
        ),
    },
    "tester": {
        "title": "QAエンジニア",
        "personality": (
            "包括的なテスト戦略を設計する品質重視のテスター。"
            "エッジケースの特定と信頼性の高い自動テストの作成が得意。"
            "ユニット・統合・E2Eテストへの体系的アプローチ。"
        ),
    },
    "optimizer": {
        "title": "パフォーマンスエンジニア",
        "personality": (
            "プロファイリングとメトリクスでボトルネックを特定するパフォーマンス専門エンジニア。"
            "アルゴリズム最適化、キャッシュ戦略、リソース効率化に精通。"
            "パフォーマンス向上とコード複雑性のバランスを重視。"
        ),
    },
    "documenter": {
        "title": "テクニカルライター",
        "personality": (
            "開発者が実際に読みたくなるドキュメントを作成する明瞭なテクニカルライター。"
            "API仕様書・アーキテクチャガイド・READMEの作成が得意。"
            "実践的なサンプルと保守しやすい構成を重視。"
        ),
    },
    "marketer": {
        "title": "グロースマーケティングスペシャリスト",
        "personality": (
            "データ駆動で魅力的なコンテンツと成長戦略を立案するマーケター。"
            "市場分析・SEO・SNS戦略・ローンチ計画に精通。"
            "技術的な機能をユーザー向けの価値提案に変換するのが得意。"
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

        # Agent personality: user config > default profiles
        agent_profiles = self.project_config.get("agent_profiles", {})
        user_profile = agent_profiles.get(self.role, {})
        default_profile = DEFAULT_AGENT_PROFILES.get(self.role, {})

        personality = user_profile.get("personality") or default_profile.get("personality", "")
        title = user_profile.get("title") or default_profile.get("title", "")

        if personality:
            parts.append(f"\n## Your Personality\n{personality}")
        if title:
            parts.append(f"Your title: {title}")

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
            return prompt_path.read_text()
        return ""

    def attach_tools(self, tools: list) -> None:
        """Attach tools to this agent."""
        self.tools = tools
