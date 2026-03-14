"""ModelManager - Register, update, switch, and route models dynamically."""

from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parents[3] / "config"


class ModelManager:
    """Central model management: register, update, switch, route inference, validate availability."""

    def __init__(self, config_dir: str = None):
        self.config_dir = Path(config_dir) if config_dir else CONFIG_DIR
        self.models: dict = {}
        self.agent_assignments: dict = {}
        self.reload_models()

    def reload_models(self) -> None:
        """Load models and agent assignments from YAML configs."""
        models_path = self.config_dir / "models.yaml"
        agents_path = self.config_dir / "agents.yaml"

        if models_path.exists():
            with open(models_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                self.models = data.get("models", {})

        if agents_path.exists():
            with open(agents_path, encoding="utf-8") as f:
                self.agent_assignments = yaml.safe_load(f) or {}

        # 自動追加: assignments が空なら全ロールにデフォルトモデルを割り当て
        if not self.agent_assignments:
            self._populate_default_roles()

    def get_model(self, role: str) -> dict:
        """Get model config for a given agent role."""
        model_name = self.agent_assignments.get(role, "qwen3.5-9b")
        model_config = self.models.get(model_name, {})
        return {"name": model_name, **model_config}

    def update_model(self, role: str, new_model: str) -> None:
        """Switch the model for a given role at runtime. No restart required."""
        if new_model not in self.models:
            raise ValueError(f"Model not registered: {new_model}")
        self.agent_assignments[role] = new_model
        self._save_assignments()

    def register_model(self, name: str, config: dict) -> None:
        """Register a new model."""
        self.models[name] = config

    def list_models(self) -> dict:
        return self.models

    def save_assignments(self) -> None:
        """Public method to persist current assignments to agents.yaml."""
        self._save_assignments()

    def add_role(self, role: str, model: str) -> None:
        """Add a new role with the specified model."""
        if role in self.agent_assignments:
            raise ValueError(f"Role already exists: {role}")
        if model not in self.models:
            raise ValueError(f"Model not registered: {model}")
        self.agent_assignments[role] = model
        self._save_assignments()

    def remove_role(self, role: str) -> None:
        """Remove a role."""
        if role not in self.agent_assignments:
            raise ValueError(f"Role not found: {role}")
        del self.agent_assignments[role]
        self._save_assignments()

    def _populate_default_roles(self) -> None:
        """Populate all known roles with default models when assignments are empty."""
        from mado.backend.orchestrator.agent_factory import AGENT_CLASSES
        high_tier = "qwen3.5-9b"
        standard_tier = "qwen2.5-coder-7b"
        planning_roles = {"cto", "manager", "researcher", "marketer"}
        for role in AGENT_CLASSES:
            self.agent_assignments[role] = high_tier if role in planning_roles else standard_tier
        self._save_assignments()

    def _save_assignments(self) -> None:
        """Persist agent_assignments to agents.yaml."""
        import logging
        logger = logging.getLogger(__name__)
        try:
            agents_path = self.config_dir / "agents.yaml"
            agents_path.parent.mkdir(parents=True, exist_ok=True)
            agents_path.write_text(
                yaml.dump(dict(self.agent_assignments), allow_unicode=True, default_flow_style=False),
                encoding="utf-8",
            )
            logger.info("Saved agent assignments to %s", agents_path)
        except Exception as e:
            logger.error("Failed to save agent assignments: %s", e)
