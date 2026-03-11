"""ModelManager - Register, update, switch, and route models dynamically."""

import yaml
from pathlib import Path
from typing import Optional

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
            with open(models_path) as f:
                data = yaml.safe_load(f) or {}
                self.models = data.get("models", {})

        if agents_path.exists():
            with open(agents_path) as f:
                self.agent_assignments = yaml.safe_load(f) or {}

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

    def register_model(self, name: str, config: dict) -> None:
        """Register a new model."""
        self.models[name] = config

    def list_models(self) -> dict:
        return self.models
