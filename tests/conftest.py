"""Shared test fixtures for MADO backend tests."""

from unittest.mock import MagicMock, patch

import pytest

from mado.backend.orchestrator.workspace_manager import WorkspaceManager

# ============================================================
# Workspace / Project fixtures
# ============================================================


@pytest.fixture
def tmp_projects(tmp_path):
    """Create a temporary projects root with WorkspaceManager."""
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    wm = WorkspaceManager(str(projects_root))
    return wm


@pytest.fixture
def sample_project(tmp_projects):
    """Create a sample project and return (workspace_manager, project_id)."""
    wm = tmp_projects
    wm.create_workspace("test-project")
    return wm, "test-project"


# ============================================================
# API client fixtures (shared across API test files)
# ============================================================


@pytest.fixture
def app_client(tmp_path):
    """Create a FastAPI test client with isolated projects root."""
    from fastapi.testclient import TestClient

    import mado.backend.orchestrator.workspace_manager as wm_mod
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    original_instance = wm_mod._shared_instance
    wm_mod._shared_instance = WorkspaceManager(str(projects_root))

    from mado.backend.api.main import app
    client = TestClient(app)

    yield client, wm_mod._shared_instance

    wm_mod._shared_instance = original_instance


@pytest.fixture
def api_client(tmp_path):
    """Isolated API test client with patched workspace manager.

    Returns (TestClient, WorkspaceManager). Patches both the shared
    instance and the projects route module-level reference.
    """
    from fastapi.testclient import TestClient

    import mado.backend.orchestrator.workspace_manager as wm_mod

    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    original = wm_mod._shared_instance
    wm = WorkspaceManager(str(projects_root))
    wm_mod._shared_instance = wm

    # Patch module-level reference in projects route
    import mado.backend.api.routes.projects as proj_mod
    proj_mod.workspace_manager = wm

    from mado.backend.api.main import app
    client = TestClient(app)
    yield client, wm

    wm_mod._shared_instance = original


@pytest.fixture
def orchestrator_api_client(tmp_path):
    """Isolated API test client for orchestrator route tests.

    Patches workspace manager, orchestrator state, and _execute_run.
    Returns (TestClient, WorkspaceManager).
    """
    from fastapi.testclient import TestClient

    import mado.backend.api.routes.orchestrator as orch_mod
    import mado.backend.orchestrator.workspace_manager as wm_mod

    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    original_wm = wm_mod._shared_instance
    wm = WorkspaceManager(str(projects_root))
    wm_mod._shared_instance = wm

    original_orch_wm = orch_mod._workspace_manager
    orch_mod._workspace_manager = wm

    original_runs = orch_mod._runs.copy()
    original_orchestrators = orch_mod._orchestrators.copy()
    orch_mod._runs.clear()
    orch_mod._orchestrators.clear()

    from mado.backend.api.main import app

    with patch("mado.backend.api.routes.orchestrator._execute_run", return_value=None):
        client = TestClient(app)
        yield client, wm

    wm_mod._shared_instance = original_wm
    orch_mod._workspace_manager = original_orch_wm
    orch_mod._runs.clear()
    orch_mod._runs.update(original_runs)
    orch_mod._orchestrators.clear()
    orch_mod._orchestrators.update(original_orchestrators)


# ============================================================
# Mock agent helpers
# ============================================================


@pytest.fixture
def mock_agent_factory():
    """Factory fixture for creating mock agents with configurable behavior."""

    def _create(role, delay=0, fail=False, result=None):
        agent = MagicMock()
        agent.role = role

        def execute(task):
            if delay:
                import time
                time.sleep(delay)
            if fail:
                raise RuntimeError(f"{role} failed")
            return result or {"role": role, "result": f"{role} done", "summary": f"{role} completed"}

        agent.execute = execute
        return agent

    return _create
