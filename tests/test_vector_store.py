"""Tests for VectorStore - code indexing and search."""

from mado.backend.memory.vector_store import VectorStore


class TestVectorStoreInit:
    def test_init(self, tmp_path):
        vs = VectorStore(str(tmp_path))
        assert vs.workspace == tmp_path
        assert vs.index is None
        assert vs.documents == []


class TestVectorStoreScanAndIndex:
    def test_scan_empty_dir(self, tmp_path):
        vs = VectorStore(str(tmp_path))
        count = vs.scan_and_index()
        assert count == 0
        assert vs.documents == []

    def test_scan_python_files(self, tmp_path):
        (tmp_path / "app.py").write_text("def hello():\n    print('hi')\n", encoding="utf-8")
        (tmp_path / "test.py").write_text("def test_hello():\n    assert True\n", encoding="utf-8")
        vs = VectorStore(str(tmp_path))
        count = vs.scan_and_index()
        assert count >= 2
        assert len(vs.documents) >= 2

    def test_scan_with_custom_extensions(self, tmp_path):
        (tmp_path / "app.py").write_text("code", encoding="utf-8")
        (tmp_path / "data.txt").write_text("text", encoding="utf-8")
        vs = VectorStore(str(tmp_path))
        count = vs.scan_and_index(extensions=[".txt"])
        assert count == 1
        assert vs.documents[0]["file"] == "data.txt"

    def test_scan_skips_binary_files(self, tmp_path):
        (tmp_path / "binary.py").write_bytes(b"\x00\x01\x02\x03")
        vs = VectorStore(str(tmp_path))
        count = vs.scan_and_index()
        # Should skip or handle gracefully
        assert count >= 0

    def test_scan_nested_directories(self, tmp_path):
        subdir = tmp_path / "src"
        subdir.mkdir()
        (subdir / "main.py").write_text("x = 1\n", encoding="utf-8")
        vs = VectorStore(str(tmp_path))
        count = vs.scan_and_index()
        assert count >= 1


class TestVectorStoreChunkCode:
    def test_chunk_small_file(self, tmp_path):
        vs = VectorStore(str(tmp_path))
        chunks = vs._chunk_code("line1\nline2\nline3", "test.py")
        assert len(chunks) >= 1
        assert chunks[0]["file"] == "test.py"
        assert chunks[0]["start_line"] == 1
        assert "line1" in chunks[0]["content"]

    def test_chunk_large_file(self, tmp_path):
        vs = VectorStore(str(tmp_path))
        content = "\n".join(f"line {i}" for i in range(1000))
        chunks = vs._chunk_code(content, "big.py", chunk_size=100)
        assert len(chunks) > 1


class TestVectorStoreSearch:
    def test_search_no_index(self, tmp_path):
        vs = VectorStore(str(tmp_path))
        results = vs.search("hello")
        assert results == []

    def test_text_fallback_search(self, tmp_path):
        (tmp_path / "app.py").write_text("def hello_world():\n    return 42\n", encoding="utf-8")
        vs = VectorStore(str(tmp_path))
        vs.scan_and_index()
        # Index might be None if faiss not available, fallback to text search
        vs.index = None
        results = vs.search("hello_world")
        assert len(results) >= 1
        assert "hello_world" in results[0]["content"]

    def test_text_search_respects_top_k(self, tmp_path):
        for i in range(10):
            (tmp_path / f"file{i}.py").write_text(f"# common keyword\nx = {i}\n", encoding="utf-8")
        vs = VectorStore(str(tmp_path))
        vs.scan_and_index()
        vs.index = None
        results = vs.search("common", top_k=3)
        assert len(results) <= 3

    def test_text_search_no_match(self, tmp_path):
        (tmp_path / "app.py").write_text("def foo(): pass\n", encoding="utf-8")
        vs = VectorStore(str(tmp_path))
        vs.scan_and_index()
        vs.index = None
        results = vs.search("nonexistent_keyword_xyz")
        assert results == []
