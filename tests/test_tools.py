"""Tests for FileTools and ExecTools."""

import pytest
from mado.backend.tools.file_tools import FileTools
from mado.backend.tools.exec_tools import ExecTools


class TestFileToolsRead:
    def test_read_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello world", encoding="utf-8")
        ft = FileTools(str(tmp_path))
        assert ft.read_file("test.txt") == "hello world"

    def test_read_nonexistent(self, tmp_path):
        ft = FileTools(str(tmp_path))
        with pytest.raises(FileNotFoundError):
            ft.read_file("nope.txt")

    def test_read_path_traversal(self, tmp_path):
        ft = FileTools(str(tmp_path))
        with pytest.raises(PermissionError, match="outside workspace"):
            ft.read_file("../../etc/passwd")


class TestFileToolsWrite:
    def test_write_file(self, tmp_path):
        ft = FileTools(str(tmp_path))
        result = ft.write_file("out.txt", "content")
        assert "Written" in result
        assert (tmp_path / "out.txt").read_text(encoding="utf-8") == "content"

    def test_write_creates_subdirs(self, tmp_path):
        ft = FileTools(str(tmp_path))
        ft.write_file("sub/dir/file.txt", "nested")
        assert (tmp_path / "sub" / "dir" / "file.txt").exists()

    def test_write_path_traversal(self, tmp_path):
        ft = FileTools(str(tmp_path))
        with pytest.raises(PermissionError, match="outside workspace"):
            ft.write_file("../../evil.txt", "bad")


class TestFileToolsListDir:
    def test_list_dir(self, tmp_path):
        (tmp_path / "a.py").write_text("", encoding="utf-8")
        (tmp_path / "b.py").write_text("", encoding="utf-8")
        ft = FileTools(str(tmp_path))
        items = ft.list_dir(".")
        assert "a.py" in items
        assert "b.py" in items

    def test_list_dir_not_a_dir(self, tmp_path):
        (tmp_path / "file.txt").write_text("", encoding="utf-8")
        ft = FileTools(str(tmp_path))
        with pytest.raises(ValueError, match="Not a directory"):
            ft.list_dir("file.txt")


class TestFileToolsSearchCode:
    def test_search_code_finds(self, tmp_path):
        (tmp_path / "app.py").write_text("def hello():\n    return 'world'", encoding="utf-8")
        ft = FileTools(str(tmp_path))
        results = ft.search_code("hello")
        assert len(results) == 1
        assert results[0]["line"] == 1
        assert "hello" in results[0]["content"]

    def test_search_code_case_insensitive(self, tmp_path):
        (tmp_path / "app.py").write_text("TODO: fix this", encoding="utf-8")
        ft = FileTools(str(tmp_path))
        results = ft.search_code("todo")
        assert len(results) == 1

    def test_search_code_no_match(self, tmp_path):
        (tmp_path / "app.py").write_text("nothing here", encoding="utf-8")
        ft = FileTools(str(tmp_path))
        results = ft.search_code("xyznotfound")
        assert results == []

    def test_search_code_respects_extensions(self, tmp_path):
        (tmp_path / "app.py").write_text("match", encoding="utf-8")
        (tmp_path / "data.csv").write_text("match", encoding="utf-8")
        ft = FileTools(str(tmp_path))
        results = ft.search_code("match", extensions=[".py"])
        assert len(results) == 1
        assert results[0]["file"] == "app.py"


class TestExecToolsCheckCommand:
    def test_allowed_commands(self, tmp_path):
        et = ExecTools(str(tmp_path))
        # Should not raise
        et._check_command("python script.py")
        et._check_command("pytest tests/")
        et._check_command("pip install x")

    def test_blocked_commands(self, tmp_path):
        et = ExecTools(str(tmp_path))
        with pytest.raises(PermissionError, match="Blocked"):
            et._check_command("rm -rf /")
        with pytest.raises(PermissionError, match="Blocked"):
            et._check_command("sudo anything")

    def test_unknown_command_rejected(self, tmp_path):
        et = ExecTools(str(tmp_path))
        with pytest.raises(PermissionError, match="not allowed"):
            et._check_command("curl http://evil.com")


class TestExecToolsRunPython:
    def test_run_python_success(self, tmp_path):
        script = tmp_path / "hello.py"
        script.write_text("print('works')", encoding="utf-8")
        et = ExecTools(str(tmp_path))
        result = et.run_python("hello.py")
        assert result["returncode"] == 0
        assert "works" in result["stdout"]

    def test_run_python_path_traversal(self, tmp_path):
        et = ExecTools(str(tmp_path))
        with pytest.raises(PermissionError, match="outside workspace"):
            et.run_python("../../etc/passwd")

    def test_run_python_error(self, tmp_path):
        script = tmp_path / "fail.py"
        script.write_text("raise ValueError('oops')", encoding="utf-8")
        et = ExecTools(str(tmp_path))
        result = et.run_python("fail.py")
        assert result["returncode"] != 0
        assert "oops" in result["stderr"]


class TestExecToolsWorkspaceValidation:
    def test_validate_path_inside(self, tmp_path):
        et = ExecTools(str(tmp_path))
        et._validate_path_in_workspace(tmp_path / "sub" / "file.py")

    def test_validate_path_outside(self, tmp_path):
        et = ExecTools(str(tmp_path))
        with pytest.raises(PermissionError):
            et._validate_path_in_workspace(tmp_path.parent / "outside.py")
