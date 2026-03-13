"""Shared test fixtures for MADO backend tests."""

import json
import pytest
from pathlib import Path

from mado.backend.orchestrator.workspace_manager import WorkspaceManager


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


@pytest.fixture
def app_client(tmp_path):
    """Create a FastAPI test client with isolated projects root."""
    from fastapi.testclient import TestClient

    # Patch the shared workspace manager before importing app
    import mado.backend.orchestrator.workspace_manager as wm_mod
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    original_instance = wm_mod._shared_instance
    wm_mod._shared_instance = WorkspaceManager(str(projects_root))

    from mado.backend.api.main import app
    client = TestClient(app)

    yield client, wm_mod._shared_instance

    # Restore
    wm_mod._shared_instance = original_instance
