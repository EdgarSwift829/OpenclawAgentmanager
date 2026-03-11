"""File Tools - read_file, write_file, list_dir, search_code (restricted to workspace)."""

import os
from pathlib import Path


class FileTools:
    """File operations restricted to a project workspace."""

    def __init__(self, workspace_path: str):
        self.workspace = Path(workspace_path).resolve()

    def _validate(self, path: str) -> Path:
        target = (self.workspace / path).resolve()
        if not str(target).startswith(str(self.workspace)):
            raise PermissionError(f"Access denied: {path} is outside workspace")
        return target

    def read_file(self, path: str) -> str:
        target = self._validate(path)
        return target.read_text(encoding="utf-8")

    def write_file(self, path: str, content: str) -> str:
        target = self._validate(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Written: {target}"

    def list_dir(self, path: str = ".") -> list:
        target = self._validate(path)
        if not target.is_dir():
            raise ValueError(f"Not a directory: {path}")
        return [str(p.relative_to(self.workspace)) for p in target.iterdir()]

    def search_code(self, query: str, extensions: list = None) -> list:
        """Search for a string in workspace files."""
        extensions = extensions or [".py", ".js", ".ts", ".yaml", ".json", ".md"]
        results = []
        for filepath in self.workspace.rglob("*"):
            if filepath.is_file() and filepath.suffix in extensions:
                try:
                    content = filepath.read_text(encoding="utf-8")
                    for i, line in enumerate(content.splitlines(), 1):
                        if query.lower() in line.lower():
                            results.append({
                                "file": str(filepath.relative_to(self.workspace)),
                                "line": i,
                                "content": line.strip(),
                            })
                except (UnicodeDecodeError, PermissionError):
                    continue
        return results
