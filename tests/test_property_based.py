"""Property-based tests using hypothesis.

Tests invariants that should hold for ANY input:
- FileTools path validation always blocks escapes
- Sandbox command validation blocks dangerous commands
- extract_json never raises (returns None on invalid input)
- extract_list_from_text always returns a list
- TaskGraph validation detects all cycles
- _validate_safe_id blocks all path traversal attempts
"""

import string
import tempfile

from hypothesis import given, settings
from hypothesis import strategies as st

from mado.backend.agents.base_agent import BaseAgent
from mado.backend.orchestrator.task_graph import TaskGraph
from mado.backend.safety.sandbox import Sandbox
from mado.backend.tools.file_tools import FileTools

# ============================================================
# FileTools: Path Traversal Property Tests
# ============================================================

class TestFileToolsProperties:
    """Property: FileTools._validate NEVER allows access outside workspace."""

    @given(st.text(min_size=1, max_size=200))
    @settings(max_examples=200)
    def test_validate_never_escapes_workspace(self, path_input):
        """For any string input, _validate either returns a path inside
        workspace or raises an exception."""
        with tempfile.TemporaryDirectory() as td:
            ft = FileTools(td)
            try:
                resolved = ft._validate(path_input)
                assert str(resolved).startswith(str(ft.workspace)), \
                    f"Path {resolved} escaped workspace {ft.workspace}"
            except (PermissionError, ValueError, OSError):
                pass

    @given(st.sampled_from(["../", "../../", "../../../"]).flatmap(
        lambda prefix: st.just(prefix + "etc/passwd")
    ))
    def test_dotdot_always_blocked(self, path_input):
        """Any path with ../ prefix leading to /etc/passwd must be blocked."""
        with tempfile.TemporaryDirectory() as td:
            ft = FileTools(td)
            try:
                resolved = ft._validate(path_input)
                assert str(resolved).startswith(str(ft.workspace))
            except (PermissionError, ValueError, OSError):
                pass

    @given(st.text(alphabet=string.ascii_letters + string.digits + "_-.", min_size=1, max_size=50))
    @settings(max_examples=100)
    def test_safe_filenames_always_accepted(self, safe_name):
        """Safe filenames (alphanumeric + _-.) should always be accepted."""
        with tempfile.TemporaryDirectory() as td:
            ft = FileTools(td)
            resolved = ft._validate(safe_name)
            assert str(resolved).startswith(str(ft.workspace))


# ============================================================
# Sandbox: Command Validation Property Tests
# ============================================================

class TestSandboxProperties:
    """Property: Sandbox never allows blocked commands, regardless of wrapping."""

    @given(st.sampled_from([
        "rm", "sudo", "chmod", "chown", "kill", "shutdown",
        "reboot", "dd", "mkfs",
    ]).flatmap(lambda cmd: st.tuples(
        st.just(cmd),
        st.text(min_size=0, max_size=50),
    )))
    @settings(max_examples=100)
    def test_blocked_commands_always_rejected(self, cmd_pair):
        """Blocked base commands should always be rejected."""
        cmd, args = cmd_pair
        full_cmd = f"{cmd} {args}".strip()
        with tempfile.TemporaryDirectory() as td:
            sb = Sandbox(td)
            result = sb.validate_command(full_cmd)
            assert result is False, f"Blocked command '{full_cmd}' was allowed"

    @given(st.sampled_from(["python", "pip", "pytest"]))
    def test_allowed_commands_accepted(self, cmd):
        """Known allowed commands should be accepted."""
        with tempfile.TemporaryDirectory() as td:
            sb = Sandbox(td)
            result = sb.validate_command(cmd)
            assert result is True, f"Allowed command '{cmd}' was rejected"


# ============================================================
# JSON Extraction Property Tests
# ============================================================

class TestExtractJsonProperties:
    """Property: extract_json NEVER raises, always returns valid JSON or None."""

    @given(st.text(min_size=0, max_size=500))
    @settings(max_examples=200)
    def test_never_raises(self, text_input):
        """extract_json should never raise an exception."""
        result = BaseAgent.extract_json(text_input)
        assert result is None or isinstance(result, (dict, list, str, int, float, bool))

    @given(st.dictionaries(
        keys=st.text(min_size=1, max_size=20, alphabet=string.ascii_letters),
        values=st.one_of(st.text(max_size=50), st.integers(), st.booleans()),
        min_size=1, max_size=5,
    ))
    def test_roundtrip_json_block(self, data):
        """Valid JSON wrapped in ```json block should always be parsed correctly."""
        import json
        text = f"```json\n{json.dumps(data)}\n```"
        result = BaseAgent.extract_json(text)
        assert result == data

    @given(st.lists(
        st.text(min_size=1, max_size=20, alphabet=string.ascii_letters),
        min_size=1, max_size=10,
    ))
    def test_roundtrip_json_list(self, items):
        """Valid JSON list should always be parsed correctly."""
        import json
        text = f"```json\n{json.dumps(items)}\n```"
        result = BaseAgent.extract_json(text)
        assert result == items


class TestExtractListProperties:
    """Property: extract_list_from_text always returns a list."""

    @given(st.text(min_size=0, max_size=200))
    @settings(max_examples=100)
    def test_always_returns_list(self, text_input):
        """extract_list_from_text should always return a list."""
        result = BaseAgent.extract_list_from_text(text_input)
        assert isinstance(result, list)

    @given(st.text(min_size=0, max_size=200))
    @settings(max_examples=100)
    def test_with_valid_items_filter(self, text_input):
        """With valid_items filter, result should only contain valid items."""
        valid = ["engineer", "tester", "reviewer"]
        result = BaseAgent.extract_list_from_text(text_input, valid_items=valid)
        assert isinstance(result, list)
        for item in result:
            assert item in valid


# ============================================================
# TaskGraph Property Tests
# ============================================================

class TestTaskGraphProperties:
    """Property: TaskGraph validation correctly detects all cycles."""

    @given(st.lists(
        st.fixed_dictionaries({
            "task_id": st.text(min_size=1, max_size=10, alphabet=string.ascii_lowercase),
            "assigned_to": st.sampled_from(["engineer", "tester", "researcher"]),
        }),
        min_size=1, max_size=10,
    ))
    @settings(max_examples=50)
    def test_independent_tasks_no_errors(self, task_defs):
        """Tasks with no dependencies should never produce validation errors."""
        seen = set()
        tasks = []
        for t in task_defs:
            tid = t["task_id"]
            if tid in seen:
                continue
            seen.add(tid)
            tasks.append({**t, "depends_on": []})

        if not tasks:
            return

        graph = TaskGraph()
        graph.add_tasks(tasks)
        errors = graph.validate()
        assert errors == [], f"Independent tasks should have no errors: {errors}"

    @given(st.integers(min_value=2, max_value=5))
    def test_cycle_always_detected(self, n):
        """A cycle of n tasks should always be detected."""
        tasks = []
        for i in range(n):
            tasks.append({
                "task_id": f"t{i}",
                "assigned_to": "engineer",
                "depends_on": [f"t{(i + 1) % n}"],
            })
        graph = TaskGraph()
        graph.add_tasks(tasks)
        errors = graph.validate()
        assert len(errors) > 0, f"Cycle of size {n} was not detected"


# ============================================================
# Project ID Validation Property Tests
# ============================================================

class TestValidateSafeIdProperties:
    """Property: _validate_safe_id blocks all path traversal attempts."""

    @given(st.text(min_size=1, max_size=50, alphabet=string.ascii_letters + string.digits + "-_"))
    def test_safe_ids_accepted(self, safe_id):
        """Safe IDs (alphanumeric + hyphen/underscore) should be accepted."""
        from mado.backend.api.routes.projects import _validate_safe_id
        result = _validate_safe_id(safe_id)
        assert result == safe_id

    @given(st.sampled_from(["../", "..\\", "/", "\\"]).flatmap(
        lambda prefix: st.just(prefix).map(lambda p: p + "test")
    ))
    def test_traversal_always_blocked(self, bad_id):
        """IDs with path traversal characters should always be blocked."""
        from fastapi import HTTPException

        from mado.backend.api.routes.projects import _validate_safe_id
        try:
            _validate_safe_id(bad_id)
            assert False, f"Path traversal ID '{bad_id}' was not blocked"
        except HTTPException as e:
            assert e.status_code == 400
