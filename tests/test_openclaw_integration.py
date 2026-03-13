"""Tests for OpenClaw integration module and API routes.

Covers: OpenClawIntegration (is_installed, get_version, install, ensure_installed,
start_gateway, send_message, list_sessions) and openclaw API routes.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mado.backend.integrations.openclaw import OpenClawIntegration


class TestOpenClawIsInstalled:
    def test_installed_via_direct_command(self):
        oc = OpenClawIntegration()
        mock_result = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=mock_result):
            assert oc.is_installed() is True

    def test_installed_via_shutil_which(self):
        oc = OpenClawIntegration()
        with patch("subprocess.run", side_effect=FileNotFoundError):
            with patch("shutil.which", return_value="/usr/bin/openclaw"):
                assert oc.is_installed() is True

    def test_installed_via_npm_list(self):
        oc = OpenClawIntegration()
        npm_result = MagicMock(returncode=0, stdout="openclaw@1.0.0")
        with patch("subprocess.run", side_effect=[FileNotFoundError, npm_result]):
            with patch("shutil.which", return_value=None):
                assert oc.is_installed() is True

    def test_not_installed(self):
        oc = OpenClawIntegration()
        with patch("subprocess.run", side_effect=FileNotFoundError):
            with patch("shutil.which", return_value=None):
                assert oc.is_installed() is False


class TestOpenClawGetVersion:
    def test_version_from_direct_command(self):
        oc = OpenClawIntegration()
        mock_result = MagicMock(returncode=0, stdout="1.2.3\n")
        with patch("subprocess.run", return_value=mock_result):
            assert oc.get_version() == "1.2.3"

    def test_version_from_npm_list(self):
        oc = OpenClawIntegration()
        npm_result = MagicMock(returncode=0, stdout="├── openclaw@1.5.0\n")
        with patch("subprocess.run", side_effect=[FileNotFoundError, npm_result]):
            version = oc.get_version()
            assert version is not None
            assert "openclaw@1.5.0" in version

    def test_version_not_available(self):
        oc = OpenClawIntegration()
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert oc.get_version() is None


class TestOpenClawInstall:
    def test_install_success(self):
        oc = OpenClawIntegration()
        mock_result = MagicMock(returncode=0, stdout="installed", stderr="")
        with patch("shutil.which", return_value="/usr/bin/npm"):
            with patch("subprocess.run", return_value=mock_result):
                result = oc.install()
        assert result["success"] is True

    def test_install_npm_not_found(self):
        oc = OpenClawIntegration()
        with patch("shutil.which", return_value=None):
            result = oc.install()
        assert result["success"] is False
        assert result["error_code"] == "npm_not_found"

    def test_install_timeout(self):
        oc = OpenClawIntegration()
        import subprocess
        with patch("shutil.which", return_value="/usr/bin/npm"):
            with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("npm", 300)):
                result = oc.install()
        assert result["success"] is False
        assert result["error_code"] == "timeout"

    def test_install_generic_error(self):
        oc = OpenClawIntegration()
        with patch("shutil.which", return_value="/usr/bin/npm"):
            with patch("subprocess.run", side_effect=OSError("disk full")):
                result = oc.install()
        assert result["success"] is False
        assert result["error_code"] == "unknown"


class TestOpenClawEnsureInstalled:
    def test_already_installed(self):
        oc = OpenClawIntegration()
        with patch.object(oc, "is_installed", return_value=True):
            with patch.object(oc, "get_version", return_value="1.0.0"):
                result = oc.ensure_installed()
        assert result["status"] == "already_installed"
        assert result["version"] == "1.0.0"

    def test_install_success(self):
        oc = OpenClawIntegration()
        with patch.object(oc, "is_installed", side_effect=[False, True]):
            with patch.object(oc, "install", return_value={"success": True}):
                with patch.object(oc, "get_version", return_value="1.0.0"):
                    result = oc.ensure_installed()
        assert result["status"] == "installed"

    def test_install_failed(self):
        oc = OpenClawIntegration()
        with patch.object(oc, "is_installed", return_value=False):
            with patch.object(oc, "install", return_value={"success": False, "error": "npm error", "error_code": "install_error"}):
                result = oc.ensure_installed()
        assert result["status"] == "install_failed"


class TestOpenClawStartGateway:
    def test_start_success(self):
        oc = OpenClawIntegration()
        mock_proc = MagicMock(pid=12345)
        with patch("subprocess.Popen", return_value=mock_proc):
            result = oc.start_gateway()
        assert result["status"] == "started"
        assert result["pid"] == 12345

    def test_start_error(self):
        oc = OpenClawIntegration()
        with patch("subprocess.Popen", side_effect=FileNotFoundError("no openclaw")):
            result = oc.start_gateway()
        assert result["status"] == "error"


class TestOpenClawSendMessage:
    @pytest.mark.asyncio
    async def test_send_message_success(self):
        oc = OpenClawIntegration()
        mock_ws = AsyncMock()
        mock_ws.recv = AsyncMock(return_value='{"result": "ok"}')
        mock_ws.__aenter__ = AsyncMock(return_value=mock_ws)
        mock_ws.__aexit__ = AsyncMock(return_value=False)
        with patch("websockets.connect", return_value=mock_ws):
            result = await oc.send_message("session1", "hello")
        assert result["result"] == "ok"

    @pytest.mark.asyncio
    async def test_send_message_connection_error(self):
        oc = OpenClawIntegration()
        with patch("websockets.connect", side_effect=ConnectionRefusedError("refused")):
            result = await oc.send_message("session1", "hello")
        assert "error" in result


class TestOpenClawListSessions:
    @pytest.mark.asyncio
    async def test_list_sessions_error(self):
        oc = OpenClawIntegration()
        with patch("websockets.connect", side_effect=ConnectionRefusedError("refused")):
            result = await oc.list_sessions()
        assert "error" in result


class TestOpenClawAPIRoutes:
    def test_openclaw_status(self, api_client):
        client, wm = api_client
        with patch("mado.backend.api.routes.openclaw.openclaw") as mock_oc:
            mock_oc.is_installed.return_value = True
            mock_oc.get_version.return_value = "1.0.0"
            resp = client.get("/api/openclaw/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["installed"] is True
        assert data["version"] == "1.0.0"

    def test_openclaw_status_not_installed(self, api_client):
        client, wm = api_client
        with patch("mado.backend.api.routes.openclaw.openclaw") as mock_oc:
            mock_oc.is_installed.return_value = False
            resp = client.get("/api/openclaw/status")
        assert resp.status_code == 200
        assert resp.json()["installed"] is False

    def test_openclaw_status_error(self, api_client):
        client, wm = api_client
        with patch("mado.backend.api.routes.openclaw.openclaw") as mock_oc:
            mock_oc.is_installed.side_effect = OSError("fail")
            resp = client.get("/api/openclaw/status")
        assert resp.status_code == 200
        assert resp.json()["installed"] is False

    def test_openclaw_install(self, api_client):
        client, wm = api_client
        with patch("mado.backend.api.routes.openclaw.openclaw") as mock_oc:
            mock_oc.ensure_installed.return_value = {"status": "already_installed", "version": "1.0.0"}
            resp = client.post("/api/openclaw/install")
        assert resp.status_code == 200

    def test_openclaw_gateway_start(self, api_client):
        client, wm = api_client
        with patch("mado.backend.api.routes.openclaw.openclaw") as mock_oc:
            mock_oc.start_gateway.return_value = {"status": "started", "pid": 999}
            resp = client.post("/api/openclaw/gateway/start")
        assert resp.status_code == 200
