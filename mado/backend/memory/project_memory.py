"""Project Memory - Persistent memory management per project."""

from pathlib import Path


class ProjectMemory:
    """Manages persistent project memory stored in project_memory.md."""

    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.memory_file = self.project_path / "project_memory.md"

    def load(self) -> str:
        if self.memory_file.exists():
            return self.memory_file.read_text(encoding="utf-8")
        return ""

    def save(self, content: str) -> None:
        self.memory_file.write_text(content, encoding="utf-8")

    def get_context(self) -> dict:
        """Parse memory into structured context for token optimization."""
        content = self.load()
        sections = {}
        current_section = None
        current_lines = []

        for line in content.splitlines():
            if line.startswith("## "):
                if current_section:
                    sections[current_section] = "\n".join(current_lines).strip()
                current_section = line[3:].strip()
                current_lines = []
            elif current_section:
                current_lines.append(line)

        if current_section:
            sections[current_section] = "\n".join(current_lines).strip()

        return sections
