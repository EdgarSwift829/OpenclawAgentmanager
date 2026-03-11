"""Script to index workspace code for vector search."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mado.backend.memory.vector_store import VectorStore


def main():
    if len(sys.argv) < 2:
        print("Usage: python index_code.py <workspace_path>")
        sys.exit(1)

    workspace_path = sys.argv[1]
    store = VectorStore(workspace_path)
    count = store.scan_and_index()
    print(f"Indexed {count} code chunks from {workspace_path}")


if __name__ == "__main__":
    main()
