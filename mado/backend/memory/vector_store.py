"""Vector Store - Code indexing and semantic search using FAISS + sentence-transformers.

Provides two search modes:
  1. Semantic search via FAISS + sentence-transformers (if available)
  2. Fallback TF-IDF keyword search (always available, no extra deps)
"""

import logging
import math
import re
from collections import Counter
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Default embedding model for sentence-transformers
DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"


class VectorStore:
    """Index workspace code and perform vector-based semantic search."""

    def __init__(self, workspace_path: str, embedding_model: str = DEFAULT_EMBEDDING_MODEL):
        self.workspace = Path(workspace_path)
        self.embedding_model_name = embedding_model
        self.index = None
        self.documents: list[dict] = []
        self._encoder = None
        self._use_semantic = False
        self._tfidf_docs: list[dict] = []
        self._idf: dict[str, float] = {}

    def _load_encoder(self) -> bool:
        """Attempt to load the sentence-transformers encoder."""
        if self._encoder is not None:
            return self._use_semantic
        try:
            from sentence_transformers import SentenceTransformer
            self._encoder = SentenceTransformer(self.embedding_model_name)
            self._use_semantic = True
            logger.info("Loaded embedding model: %s", self.embedding_model_name)
            return True
        except ImportError:
            logger.warning(
                "sentence-transformers not installed. "
                "Falling back to TF-IDF keyword search. "
                "Install with: pip install sentence-transformers"
            )
            self._use_semantic = False
            return False
        except Exception as e:
            logger.warning("Failed to load embedding model: %s. Falling back to TF-IDF.", e)
            self._use_semantic = False
            return False

    def scan_and_index(self, extensions: Optional[list[str]] = None) -> int:
        """Scan workspace files, chunk code, generate embeddings, store index.

        Returns the number of chunks indexed.
        """
        extensions = extensions or [".py", ".js", ".ts", ".tsx", ".yaml", ".json", ".md"]
        chunks: list[dict] = []

        for filepath in self.workspace.rglob("*"):
            if not filepath.is_file():
                continue
            if filepath.suffix not in extensions:
                continue
            # Skip hidden dirs, node_modules, __pycache__
            rel = filepath.relative_to(self.workspace)
            parts = rel.parts
            if any(p.startswith(".") or p in ("node_modules", "__pycache__") for p in parts):
                continue
            try:
                content = filepath.read_text(encoding="utf-8", errors="replace")
                file_chunks = self._chunk_code(content, str(rel))
                chunks.extend(file_chunks)
            except (PermissionError, OSError):
                continue

        self.documents = chunks
        if chunks:
            self._build_index(chunks)
        logger.info("Indexed %d chunks from %s", len(chunks), self.workspace)
        return len(chunks)

    def _chunk_code(self, content: str, filename: str,
                    chunk_size: int = 60, overlap: int = 10) -> list[dict]:
        """Split code into overlapping line-based chunks for better context."""
        lines = content.splitlines()
        if not lines:
            return []

        chunks = []
        step = max(chunk_size - overlap, 1)
        for i in range(0, len(lines), step):
            chunk_lines = lines[i:i + chunk_size]
            if not chunk_lines:
                break
            text = "\n".join(chunk_lines)
            chunks.append({
                "file": filename,
                "start_line": i + 1,
                "end_line": i + len(chunk_lines),
                "content": text,
            })
        return chunks

    def _build_index(self, chunks: list[dict]) -> None:
        """Build FAISS index from chunks using sentence-transformers embeddings."""
        if not self._load_encoder():
            self._build_tfidf_index(chunks)
            return

        try:
            import faiss
            import numpy as np

            texts = [c["content"] for c in chunks]
            embeddings = self._encoder.encode(texts, show_progress_bar=False, batch_size=32)
            embeddings = np.array(embeddings, dtype="float32")

            # Normalize for cosine similarity via inner product
            faiss.normalize_L2(embeddings)

            dimension = embeddings.shape[1]
            self.index = faiss.IndexFlatIP(dimension)
            self.index.add(embeddings)

            logger.info("Built FAISS index: %d vectors, dim=%d", len(chunks), dimension)
        except ImportError:
            logger.warning("faiss-cpu not installed. Using TF-IDF fallback.")
            self._build_tfidf_index(chunks)
        except Exception as e:
            logger.warning("Failed to build FAISS index: %s. Using TF-IDF fallback.", e)
            self._build_tfidf_index(chunks)

    def _build_tfidf_index(self, chunks: list[dict]) -> None:
        """Build a simple TF-IDF index for keyword-based search fallback."""
        self._tfidf_docs = []
        for chunk in chunks:
            tokens = self._tokenize(chunk["content"])
            tf = Counter(tokens)
            total = len(tokens) or 1
            self._tfidf_docs.append({
                "tf": {t: c / total for t, c in tf.items()},
                "tokens": set(tokens),
            })

        # Compute IDF
        n = len(chunks) or 1
        all_tokens: set[str] = set()
        for doc in self._tfidf_docs:
            all_tokens.update(doc["tokens"])
        self._idf = {}
        for token in all_tokens:
            df = sum(1 for doc in self._tfidf_docs if token in doc["tokens"])
            self._idf[token] = math.log(n / (df + 1)) + 1

        logger.info("Built TF-IDF index: %d documents, %d unique tokens",
                     len(chunks), len(all_tokens))

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Simple tokenizer: lowercase, split on non-alphanumeric, filter short tokens."""
        tokens = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*', text.lower())
        return [t for t in tokens if len(t) > 1]

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Search for relevant code chunks.

        Uses semantic search (FAISS) if available, otherwise falls back to TF-IDF,
        then to simple text matching.
        """
        if not self.documents:
            return []

        # Semantic search path
        if self.index is not None and self._use_semantic and self._encoder is not None:
            return self._search_semantic(query, top_k)

        # TF-IDF fallback
        if self._tfidf_docs:
            return self._search_tfidf(query, top_k)

        # Simple text search as last resort
        return self._search_text(query, top_k)

    def _search_semantic(self, query: str, top_k: int) -> list[dict]:
        """Perform semantic search using FAISS."""
        try:
            import faiss
            import numpy as np

            query_embedding = self._encoder.encode([query], show_progress_bar=False)
            query_embedding = np.array(query_embedding, dtype="float32")
            faiss.normalize_L2(query_embedding)

            k = min(top_k, len(self.documents))
            scores, indices = self.index.search(query_embedding, k)

            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx < 0 or idx >= len(self.documents):
                    continue
                doc = dict(self.documents[idx])
                doc["score"] = float(score)
                results.append(doc)
            return results
        except Exception as e:
            logger.warning("Semantic search failed: %s. Falling back to text search.", e)
            return self._search_text(query, top_k)

    def _search_tfidf(self, query: str, top_k: int) -> list[dict]:
        """Perform TF-IDF based search."""
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return self._search_text(query, top_k)

        scores: list[tuple[float, int]] = []
        for i, doc in enumerate(self._tfidf_docs):
            score = 0.0
            for token in query_tokens:
                if token in doc["tf"]:
                    score += doc["tf"][token] * self._idf.get(token, 1.0)
            if score > 0:
                scores.append((score, i))

        scores.sort(reverse=True)
        results = []
        for score, idx in scores[:top_k]:
            doc = dict(self.documents[idx])
            doc["score"] = score
            results.append(doc)
        return results

    def _search_text(self, query: str, top_k: int) -> list[dict]:
        """Simple text-matching search as last resort."""
        query_lower = query.lower()
        results = []
        for doc in self.documents:
            if query_lower in doc["content"].lower():
                results.append(dict(doc))
                if len(results) >= top_k:
                    break
        return results
