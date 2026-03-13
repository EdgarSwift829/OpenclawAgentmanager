"""Memory Tools - save_summary, load_project_memory, update_project_memory."""

from pathlib import Path


class MemoryTools:
    """Tools for managing project-level persistent memory."""

    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.memory_file = self.project_path / "project_memory.md"

    def load_project_memory(self) -> str:
        """Load the project memory file."""
        if self.memory_file.exists():
            return self.memory_file.read_text(encoding="utf-8")
        return ""

    def update_project_memory(self, section: str, content: str) -> str:
        """Update a section in the project memory."""
        memory = self.load_project_memory()
        header = f"## {section}"
        if header in memory:
            lines = memory.split("\n")
            new_lines = []
            in_section = False
            for line in lines:
                if line.strip() == header:
                    new_lines.append(line)
                    new_lines.append(content)
                    in_section = True
                elif line.startswith("## ") and in_section:
                    in_section = False
                    new_lines.append(line)
                elif not in_section:
                    new_lines.append(line)
            memory = "\n".join(new_lines)
        else:
            memory += f"\n{header}\n{content}\n"
        self.memory_file.write_text(memory, encoding="utf-8")
        return f"Updated section: {section}"

    def save_summary(self, iteration: int, summary: str) -> str:
        """Save an iteration summary to the memory file."""
        return self.update_project_memory(f"Iteration {iteration} Summary", summary)
