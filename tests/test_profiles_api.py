"""Tests for agent profiles API routes."""

import pytest


@pytest.fixture
def api(api_client, tmp_path):
    """API client with profiles path overridden to tmp_path."""
    client, wm = api_client
    wm._PROFILES_PATH = tmp_path / "agent_profiles.json"
    yield client, wm


class TestListProfiles:
    def test_list_all_profiles(self, api):
        client, wm = api
        resp = client.get("/api/profiles/")
        assert resp.status_code == 200
        data = resp.json()
        # Should contain preset profiles seeded from DEFAULT_AGENT_PROFILES
        assert isinstance(data, dict)

    def test_list_role_profiles(self, api):
        client, wm = api
        resp = client.get("/api/profiles/cto")
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "cto"
        assert isinstance(data["profiles"], list)


class TestCreateProfile:
    def test_create_profile(self, api):
        client, wm = api
        resp = client.post("/api/profiles/engineer", json={
            "name": "Custom Engineer",
            "additional_prompt": "Focus on clean code",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Custom Engineer"
        assert data["additional_prompt"] == "Focus on clean code"
        assert data["is_preset"] is False

    def test_create_profile_empty_name(self, api):
        client, wm = api
        resp = client.post("/api/profiles/engineer", json={
            "name": "  ",
            "additional_prompt": "",
        })
        assert resp.status_code == 400

    def test_create_profile_clone(self, api):
        client, wm = api
        # Create a source profile
        resp1 = client.post("/api/profiles/engineer", json={
            "name": "Source",
            "additional_prompt": "base prompt",
        })
        source_id = resp1.json()["id"]

        # Clone it
        resp2 = client.post("/api/profiles/engineer", json={
            "name": "Cloned",
            "clone_from": source_id,
        })
        assert resp2.status_code == 200
        cloned = resp2.json()
        assert cloned["name"] == "Cloned"
        assert cloned["additional_prompt"] == "base prompt"
        assert cloned["created_from"] == source_id


class TestUpdateProfile:
    def test_update_profile(self, api):
        client, wm = api
        # Create
        resp = client.post("/api/profiles/engineer", json={
            "name": "Edit Me",
            "additional_prompt": "old",
        })
        pid = resp.json()["id"]

        # Update
        resp2 = client.put(f"/api/profiles/engineer/{pid}", json={
            "additional_prompt": "new prompt",
        })
        assert resp2.status_code == 200
        assert resp2.json()["additional_prompt"] == "new prompt"

    def test_update_preset_rejected(self, api):
        client, wm = api
        # Get presets
        resp = client.get("/api/profiles/cto")
        profiles = resp.json()["profiles"]
        preset = next((p for p in profiles if p.get("is_preset")), None)
        if preset:
            resp2 = client.put(f"/api/profiles/cto/{preset['id']}", json={
                "name": "Hacked",
            })
            assert resp2.status_code == 404

    def test_update_no_fields(self, api):
        client, wm = api
        resp = client.post("/api/profiles/engineer", json={
            "name": "X", "additional_prompt": "",
        })
        pid = resp.json()["id"]
        resp2 = client.put(f"/api/profiles/engineer/{pid}", json={})
        assert resp2.status_code == 400


class TestDeleteProfile:
    def test_delete_profile(self, api):
        client, wm = api
        resp = client.post("/api/profiles/engineer", json={
            "name": "Delete Me",
            "additional_prompt": "",
        })
        pid = resp.json()["id"]
        resp2 = client.delete(f"/api/profiles/engineer/{pid}")
        assert resp2.status_code == 200
        assert resp2.json()["deleted"] is True

    def test_delete_preset_rejected(self, api):
        client, wm = api
        resp = client.get("/api/profiles/cto")
        profiles = resp.json()["profiles"]
        preset = next((p for p in profiles if p.get("is_preset")), None)
        if preset:
            resp2 = client.delete(f"/api/profiles/cto/{preset['id']}")
            assert resp2.status_code == 404

    def test_delete_nonexistent(self, api):
        client, wm = api
        resp = client.delete("/api/profiles/engineer/no-such-id")
        assert resp.status_code == 404
