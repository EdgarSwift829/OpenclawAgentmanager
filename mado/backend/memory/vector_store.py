"""Vector Store - Code indexing and semantic search using FAISS/Chroma."""

from pathlib import Path


class VectorStore:
    """Index workspace code and perform vector-based semantic search."""

    def __init__(self, workspace_path: str):
        self.workspace = Path(workspace_path)
        self.index = None
        self.documents: list = []
        self.embeddings = None

    def scan_and_index(self, extensions: list = None) -> int:
        """Scan workspace files, chunk code, generate embeddings, store index."""
        extensions = extensions or [".py", ".js", ".ts", ".yaml", ".json"]
        chunks = []
        for filepath in self.workspace.rglob("*"):
            if filepath.is_file() and filepath.suffix in extensions:
                try:
                    content = filepath.read_text(encoding="utf-8")
                    file_chunks = self._chunk_code(content, str(filepath.relative_to(self.workspace)))
                    chunks.extend(file_chunks)
                except (UnicodeDecodeError, PermissionError):
                    continue

        self.documents = chunks
        self._build_index(chunks)
        return len(chunks)

    def _chunk_code(self, content: str, filename: str, chunk_size: int = 500) -> list:
        """Split code into chunks."""
        lines = content.splitlines()
        chunks = []
        for i in range(0, len(lines), chunk_size // 2):
            chunk_lines = lines[i:i + chunk_size]
            chunks.append({
                "file": filename,
                "start_line": i + 1,
                "content": "\n".join(chunk_lines),
            })
        return chunks

    def _build_index(self, chunks: list) -> None:
        """Build FAISS index from chunks. Requires faiss-cpu and an embedding model."""
        try:
            import faiss
            import numpy as np
            # Placeholder: use actual embeddings from local model
            dimension = 384
            self.index = faiss.IndexFlatL2(dimension)
            # TODO: Generate real embeddings via local model
        except ImportError:
            self.index = None

    def search(self, query: str, top_k: int = 5) -> list:
        """Search for relevant code chunks."""
        if self.index is None:
            # Fallback to simple text search
            results = []
            for doc in self.documents:
                if query.lower() in doc["content"].lower():
                    results.append(doc)
                    if len(results) >= top_k:
                        break
            return results
        # TODO: Vector search with FAISS
        return []
