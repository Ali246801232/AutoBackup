"""Test src/dashboard/app.py."""

import json
import sys
from unittest.mock import MagicMock, patch

# Mock GUI-only dependencies before any module imports
for _mod in ("pystray", "PIL", "PIL.Image", "webview", "notifypy"):
    sys.modules.setdefault(_mod, MagicMock())

_startup = MagicMock()
_startup.is_in_startup.return_value = False
_startup.add_to_startup.return_value = None
_startup.remove_from_startup.return_value = None
sys.modules.setdefault("startup", _startup)

import pytest


@pytest.fixture(autouse=True)
def _reset_backups():
    import dashboard.app
    old = dashboard.app.BACKUPS, dashboard.app.BACKUP_CONFIGS_DIR
    dashboard.app.BACKUPS = {}
    dashboard.app.BACKUP_CONFIGS_DIR = None
    yield
    dashboard.app.BACKUPS, dashboard.app.BACKUP_CONFIGS_DIR = old


@pytest.fixture
def client():
    import dashboard.app
    dashboard.app.app.config["TESTING"] = True
    with dashboard.app.app.test_client() as c:
        yield c


@pytest.fixture
def setup_backups(tmp_path):
    import dashboard.app
    configs_dir = tmp_path / "configs"
    configs_dir.mkdir()
    dashboard.app.BACKUP_CONFIGS_DIR = configs_dir
    yield configs_dir


@pytest.fixture
def valid_backup_dict(tmp_path):
    tmp_source = tmp_path / "fixture_source"
    tmp_source.mkdir()
    tmp_destination = tmp_path / "fixture_destination"
    tmp_destination.mkdir()
    return {
        "config_name": "test_config",
        "sources": [str(tmp_source)],
        "destination": str(tmp_destination),
        "exclusions": [],
        "schedule": None,
        "drive_upload": False,
        "drive_folder_id": None,
        "last_scheduled_attempt": None,
    }


@pytest.fixture
def created_backup(client, setup_backups, valid_backup_dict):
    resp = client.post("/api/backups/new", json=valid_backup_dict)
    assert resp.status_code == 201
    return resp.get_json()


class TestCreateBackup:
    def test_create_success(self, client, setup_backups, valid_backup_dict):
        resp = client.post("/api/backups/new", json=valid_backup_dict)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["config_name"] == "test_config"
        assert "sources" in data

    def test_create_no_config_name(self, client, setup_backups):
        resp = client.post("/api/backups/new", json={"sources": ["/x"], "destination": "/y"})
        assert resp.status_code == 400
        assert "config name" in resp.get_json()["error"].lower()

    def test_create_no_sources(self, client, setup_backups):
        resp = client.post("/api/backups/new", json={"config_name": "x", "destination": "/y"})
        assert resp.status_code == 400
        assert "source" in resp.get_json()["error"].lower()

    def test_create_no_destination(self, client, setup_backups):
        resp = client.post("/api/backups/new", json={"config_name": "x", "sources": ["/y"]})
        assert resp.status_code == 400
        assert "destination" in resp.get_json()["error"].lower()

    def test_create_duplicate(self, client, setup_backups, created_backup, valid_backup_dict):
        resp = client.post("/api/backups/new", json=valid_backup_dict)
        assert resp.status_code == 409

    def test_create_verify_failure(self, client, setup_backups):
        resp = client.post("/api/backups/new", json={
            "config_name": "bad",
            "sources": ["/nonexistent_source"],
            "destination": "/nonexistent_dest",
        })
        assert resp.status_code == 400

    def test_create_saves_to_disk(self, client, setup_backups, valid_backup_dict):
        resp = client.post("/api/backups/new", json=valid_backup_dict)
        assert resp.status_code == 201
        config_file = setup_backups / "test_config.json"
        assert config_file.exists()
        data = json.loads(config_file.read_text())
        assert data["config_name"] == "test_config"


class TestListBackups:
    def test_empty(self, client, setup_backups):
        resp = client.get("/api/backups/")
        assert resp.status_code == 200
        assert resp.get_json() == {}

    def test_with_backups(self, client, setup_backups, created_backup):
        resp = client.get("/api/backups/")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "test_config" in data
        assert data["test_config"]["config_name"] == "test_config"
        assert "status" in data["test_config"]
        assert data["test_config"]["status"]["backup_running"] is False
        assert data["test_config"]["status"]["backup_error"] is False
        assert data["test_config"]["status"]["scheduler_running"] is False
        assert data["test_config"]["status"]["scheduler_error"] is False
        assert data["test_config"]["status"]["backup_progress"] is None


class TestUpdateBackup:
    def test_update_name(self, client, setup_backups, created_backup, valid_backup_dict):
        update = dict(valid_backup_dict)
        update["config_name"] = "renamed"
        resp = client.post("/api/backups/test_config/edit", json=update)
        assert resp.status_code == 200

        import dashboard.app
        assert "renamed" in dashboard.app.BACKUPS
        assert "test_config" not in dashboard.app.BACKUPS

    def test_update_name_conflict(self, client, setup_backups, created_backup, valid_backup_dict):
        d2 = dict(valid_backup_dict)
        d2["config_name"] = "other"
        client.post("/api/backups/new", json=d2)

        update = dict(valid_backup_dict)
        update["config_name"] = "other"
        resp = client.post("/api/backups/test_config/edit", json=update)
        assert resp.status_code == 409

    def test_update_invalid_data(self, client, setup_backups, created_backup):
        resp = client.post("/api/backups/test_config/edit", json={"config_name": "test_config", "sources": []})
        assert resp.status_code == 500

    def test_update_not_found(self, client, setup_backups):
        resp = client.post("/api/backups/nonexistent/edit", json={"config_name": "x"})
        assert resp.status_code == 404

    def test_update_rolls_back_on_failure(self, client, setup_backups, created_backup, valid_backup_dict):
        import dashboard.app
        update = dict(valid_backup_dict)
        update["config_name"] = "will_fail"
        update["destination"] = "/nonexistent/destination"
        resp = client.post("/api/backups/test_config/edit", json=update)
        assert resp.status_code == 500

        assert "test_config" in dashboard.app.BACKUPS
        assert "will_fail" not in dashboard.app.BACKUPS

    def test_update_preserves_data(self, client, setup_backups, created_backup, valid_backup_dict):
        import dashboard.app
        update = dict(valid_backup_dict)
        update["config_name"] = "renamed"
        resp = client.post("/api/backups/test_config/edit", json=update)
        assert resp.status_code == 200
        assert "renamed" in dashboard.app.BACKUPS
        assert dashboard.app.BACKUPS["renamed"].config_name == "renamed"


class TestDeleteBackup:
    def test_delete(self, client, setup_backups, created_backup):
        resp = client.post("/api/backups/test_config/delete")
        assert resp.status_code == 200

        import dashboard.app
        assert "test_config" not in dashboard.app.BACKUPS

    def test_delete_not_found(self, client, setup_backups):
        resp = client.post("/api/backups/nonexistent/delete")
        assert resp.status_code == 404

    def test_delete_removes_file(self, client, setup_backups, created_backup):
        config_file = setup_backups / "test_config.json"
        assert config_file.exists()
        resp = client.post("/api/backups/test_config/delete")
        assert resp.status_code == 200
        assert not config_file.exists()


class TestStartCancelBackup:
    def test_start_backup(self, client, setup_backups, created_backup):
        import dashboard.app
        with patch.object(dashboard.app.Backup, "start_backup") as mock_start:
            resp = client.post("/api/backups/test_config/start_backup")
            assert resp.status_code == 202
            mock_start.assert_called_once()

    def test_start_backup_not_found(self, client, setup_backups):
        resp = client.post("/api/backups/nonexistent/start_backup")
        assert resp.status_code == 404

    def test_cancel_backup(self, client, setup_backups, created_backup):
        import dashboard.app
        with patch.object(dashboard.app.Backup, "cancel_backup") as mock_cancel:
            resp = client.post("/api/backups/test_config/cancel_backup")
            assert resp.status_code == 200
            mock_cancel.assert_called_once()

    def test_cancel_not_found(self, client, setup_backups):
        resp = client.post("/api/backups/nonexistent/cancel_backup")
        assert resp.status_code == 404


class TestSchedulerAPI:
    def test_start_scheduler(self, client, setup_backups, created_backup):
        import dashboard.app
        with patch.object(dashboard.app.Backup, "start_scheduler") as mock_start:
            resp = client.post("/api/backups/test_config/start_scheduler")
            assert resp.status_code == 202
            mock_start.assert_called_once()

    def test_start_not_found(self, client, setup_backups):
        resp = client.post("/api/backups/nonexistent/start_scheduler")
        assert resp.status_code == 404

    def test_stop_scheduler(self, client, setup_backups, created_backup):
        import dashboard.app
        with patch.object(dashboard.app.Backup, "stop_scheduler") as mock_stop:
            resp = client.post("/api/backups/test_config/stop_scheduler")
            assert resp.status_code == 200
            mock_stop.assert_called_once()

    def test_stop_not_found(self, client, setup_backups):
        resp = client.post("/api/backups/nonexistent/stop_scheduler")
        assert resp.status_code == 404


class TestPages:
    def test_index_page(self, client):
        import dashboard.app
        with patch.object(dashboard.app, "render_template", return_value="<html>index</html>"):
            resp = client.get("/")
            assert resp.status_code == 200

    def test_edit_backup_page(self, client, setup_backups, created_backup):
        import dashboard.app
        with patch.object(dashboard.app, "render_template", return_value="<html>editor</html>"):
            resp = client.get("/edit_backup/test_config")
            assert resp.status_code == 200

    def test_new_backup_page(self, client):
        import dashboard.app
        with patch.object(dashboard.app, "render_template", return_value="<html>new</html>"):
            resp = client.get("/new_backup")
            assert resp.status_code == 200


class TestErrorHandling:
    def test_create_server_error(self, client, setup_backups):
        import dashboard.app
        with patch.object(dashboard.app.Backup, "from_dict", side_effect=Exception("unexpected")):
            resp = client.post("/api/backups/new", json={
                "config_name": "x", "sources": ["/a"], "destination": "/b",
            })
            assert resp.status_code == 500

    def test_start_backup_exception(self, client, setup_backups, created_backup):
        import dashboard.app
        with patch.object(dashboard.app.Backup, "start_backup", side_effect=Exception("fail")):
            resp = client.post("/api/backups/test_config/start_backup")
            assert resp.status_code == 500
            assert "fail" in resp.get_json()["error"]

    def test_cancel_backup_exception(self, client, setup_backups, created_backup):
        import dashboard.app
        with patch.object(dashboard.app.Backup, "cancel_backup", side_effect=Exception("fail")):
            resp = client.post("/api/backups/test_config/cancel_backup")
            assert resp.status_code == 500
            assert "fail" in resp.get_json()["error"]

    def test_start_scheduler_exception(self, client, setup_backups, created_backup):
        import dashboard.app
        with patch.object(dashboard.app.Backup, "start_scheduler", side_effect=Exception("fail")):
            resp = client.post("/api/backups/test_config/start_scheduler")
            assert resp.status_code == 500
            assert "fail" in resp.get_json()["error"]

    def test_stop_scheduler_exception(self, client, setup_backups, created_backup):
        import dashboard.app
        with patch.object(dashboard.app.Backup, "stop_scheduler", side_effect=Exception("fail")):
            resp = client.post("/api/backups/test_config/stop_scheduler")
            assert resp.status_code == 500
            assert "fail" in resp.get_json()["error"]

    def test_delete_exception(self, client, setup_backups, created_backup):
        import dashboard.app
        backup = dashboard.app.BACKUPS["test_config"]
        backup._manual_backup_ongoing = True
        with patch.object(dashboard.app.Backup, "cancel_backup", side_effect=Exception("fail")):
            resp = client.post("/api/backups/test_config/delete")
            assert resp.status_code == 500
            assert "fail" in resp.get_json()["error"]
        backup._manual_backup_ongoing = False


class TestDeleteBackupEdgeCases:
    def test_delete_stops_scheduler_first(self, client, setup_backups, created_backup):
        import dashboard.app
        backup = dashboard.app.BACKUPS["test_config"]
        backup.scheduler_running = True
        resp = client.post("/api/backups/test_config/delete")
        assert resp.status_code == 200
        assert "test_config" not in dashboard.app.BACKUPS

    def test_delete_cancels_backup_first(self, client, setup_backups, created_backup):
        import dashboard.app
        backup = dashboard.app.BACKUPS["test_config"]
        backup._manual_backup_ongoing = True
        resp = client.post("/api/backups/test_config/delete")
        assert resp.status_code == 200
        assert "test_config" not in dashboard.app.BACKUPS
        backup._manual_backup_ongoing = False


class TestPagesEdgeCases:
    def test_edit_nonexistent(self, client):
        resp = client.get("/edit_backup/nonexistent")
        assert resp.status_code == 404

    def test_edit_backup_page_uses_to_dict(self, client, setup_backups, created_backup):
        import dashboard.app
        with patch.object(dashboard.app, "render_template", return_value="<html>editor</html>") as mock_render:
            resp = client.get("/edit_backup/test_config")
            assert resp.status_code == 200
            _, kwargs = mock_render.call_args
            assert "config_data" in kwargs
            assert kwargs["config_data"]["config_name"] == "test_config"


class TestDriveAPI:
    def test_drive_auth_disabled(self, client):
        import dashboard.app
        with patch.object(dashboard.app.DRIVE_BROWSER, "authenticate") as mock_auth, \
             patch.object(dashboard.app.DRIVE_BROWSER, "go_to_root") as mock_root:
            dashboard.app.DRIVE_BROWSER.current_folder = {"id": "root_id", "title": "My Drive"}
            resp = client.post("/api/drive/auth")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["folder_id"] == "root_id"
            mock_auth.assert_called_once()
            mock_root.assert_called_once()

    def test_drive_auth_exception(self, client):
        import dashboard.app
        with patch.object(dashboard.app.DRIVE_BROWSER, "authenticate", side_effect=Exception("auth err")):
            resp = client.post("/api/drive/auth")
            assert resp.status_code == 500
            assert "auth err" in resp.get_json()["error"]

    def test_drive_browse(self, client):
        import dashboard.app
        handler = dashboard.app.DRIVE_BROWSER
        handler.current_folder = {"id": "fid", "title": "Folder"}
        with patch.object(handler, "open_folder") as mock_open, \
             patch.object(handler, "get_child_folders", return_value=[{"id": "c1", "title": "Child"}]) as mock_children:
            resp = client.post("/api/drive/browse", json={"folder_id": "fid"})
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["folder_id"] == "fid"
            assert data["folder_name"] == "Folder"
            assert len(data["children"]) == 1
            assert data["children"][0]["id"] == "c1"
            mock_open.assert_called_with("fid")

    def test_drive_browse_no_folder_id(self, client):
        import dashboard.app
        handler = dashboard.app.DRIVE_BROWSER
        handler.current_folder = {"id": "root", "title": "Root"}
        with patch.object(handler, "open_folder") as mock_open, \
             patch.object(handler, "get_child_folders", return_value=[]) as mock_children:
            resp = client.post("/api/drive/browse", json={})
            assert resp.status_code == 200
            mock_open.assert_not_called()
            mock_children.assert_called_once()

    def test_drive_browse_exception(self, client):
        import dashboard.app
        handler = dashboard.app.DRIVE_BROWSER
        with patch.object(handler, "open_folder", side_effect=Exception("browse err")):
            resp = client.post("/api/drive/browse", json={"folder_id": "x"})
            assert resp.status_code == 500
            assert "browse err" in resp.get_json()["error"]

    def test_drive_up(self, client):
        import dashboard.app
        handler = dashboard.app.DRIVE_BROWSER
        handler.current_folder = {"id": "parent_id", "title": "Parent"}
        with patch.object(handler, "go_up") as mock_up, \
             patch.object(handler, "get_child_folders", return_value=[]) as mock_children:
            resp = client.post("/api/drive/up")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["folder_id"] == "parent_id"
            mock_up.assert_called_once()
            mock_children.assert_called_once()

    def test_drive_up_exception(self, client):
        import dashboard.app
        handler = dashboard.app.DRIVE_BROWSER
        with patch.object(handler, "go_up", side_effect=Exception("up err")):
            resp = client.post("/api/drive/up")
            assert resp.status_code == 500
            assert "up err" in resp.get_json()["error"]


class TestFileDialog:
    def test_file_dialog_folder(self, client):
        import dashboard.app
        mock_window = MagicMock()
        mock_window.create_file_dialog.return_value = "/selected/path"
        with patch.object(dashboard.app.webview, "windows", [mock_window]):
            resp = client.post("/api/file_dialog", json={"type": "folder"})
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["path"] == "/selected/path"
            mock_window.create_file_dialog.assert_called_once()

    def test_file_dialog_file(self, client):
        import dashboard.app
        mock_window = MagicMock()
        mock_window.create_file_dialog.return_value = "/selected/file.txt"
        with patch.object(dashboard.app.webview, "windows", [mock_window]):
            resp = client.post("/api/file_dialog", json={"type": "file"})
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["path"] == "/selected/file.txt"

    def test_file_dialog_default_type(self, client):
        import dashboard.app
        mock_window = MagicMock()
        mock_window.create_file_dialog.return_value = "/selected/path"
        with patch.object(dashboard.app.webview, "windows", [mock_window]):
            resp = client.post("/api/file_dialog", json={})
            assert resp.status_code == 200
            assert resp.get_json()["path"] == "/selected/path"

    def test_file_dialog_cancelled(self, client):
        import dashboard.app
        mock_window = MagicMock()
        mock_window.create_file_dialog.return_value = None
        with patch.object(dashboard.app.webview, "windows", [mock_window]):
            resp = client.post("/api/file_dialog", json={"type": "folder"})
            assert resp.status_code == 200
            assert resp.get_json()["path"] is None

    def test_file_dialog_tuple_result(self, client):
        import dashboard.app
        mock_window = MagicMock()
        mock_window.create_file_dialog.return_value = ("/first/path", "/second/path")
        with patch.object(dashboard.app.webview, "windows", [mock_window]):
            resp = client.post("/api/file_dialog", json={"type": "file"})
            assert resp.status_code == 200
            assert resp.get_json()["path"] == "/first/path"

    def test_file_dialog_exception(self, client):
        import dashboard.app
        mock_window = MagicMock()
        mock_window.create_file_dialog.side_effect = Exception("dialog error")
        with patch.object(dashboard.app.webview, "windows", [mock_window]):
            resp = client.post("/api/file_dialog", json={"type": "folder"})
            assert resp.status_code == 500
            assert "dialog error" in resp.get_json()["error"]


class TestNotifyAPI:
    def test_notify_success(self, client):
        import dashboard.app
        with patch("dashboard.app.NOTIFIER") as mock_notifier:
            resp = client.post("/api/notify", json={"title": "Test", "message": "Hello"})
            assert resp.status_code == 200
            assert resp.get_json()["status"] == "notification sent"
            assert mock_notifier.title == "Test"
            assert mock_notifier.message == "Hello"
            mock_notifier.send.assert_called_once_with(block=False)

    def test_notify_default_title(self, client):
        import dashboard.app
        with patch("dashboard.app.Notify"):
            resp = client.post("/api/notify", json={"message": "Hello"})
            assert resp.status_code == 200
            assert resp.get_json()["status"] == "notification sent"

    def test_notify_exception(self, client):
        import dashboard.app
        mock_notifier = MagicMock()
        mock_notifier.send.side_effect = Exception("notify fail")
        with patch("dashboard.app.NOTIFIER", mock_notifier):
            resp = client.post("/api/notify", json={"title": "T", "message": "M"})
            assert resp.status_code == 500
            assert "notify fail" in resp.get_json()["error"]


class TestCreateBackupEdgeCases:
    def test_create_empty_json_body(self, client, setup_backups):
        resp = client.post("/api/backups/new", content_type="application/json", data="{}")
        assert resp.status_code == 400
        assert "request body" in resp.get_json()["error"].lower()

    def test_create_with_schedule(self, client, setup_backups, valid_backup_dict):
        data = dict(valid_backup_dict)
        data["schedule"] = {"count": 1, "unit": "hours"}
        resp = client.post("/api/backups/new", json=data)
        assert resp.status_code == 201
        assert resp.get_json()["schedule"] == {"count": 1, "unit": "hours"}

    def test_create_with_drive(self, client, setup_backups, valid_backup_dict):
        data = dict(valid_backup_dict)
        data["drive_upload"] = True
        data["drive_folder_id"] = "drive_123"
        resp = client.post("/api/backups/new", json=data)
        assert resp.status_code == 201
        assert resp.get_json()["drive_upload"] is True


class TestEditBackupEdgeCases:
    def test_edit_no_body(self, client, setup_backups, created_backup):
        resp = client.post("/api/backups/test_config/edit", content_type="application/json", data="{}")
        assert resp.status_code == 500

    def test_edit_removes_old_config_file(self, client, setup_backups, created_backup, valid_backup_dict):
        old_file = setup_backups / "test_config.json"
        assert old_file.exists()
        update = dict(valid_backup_dict)
        update["config_name"] = "renamed_again"
        resp = client.post("/api/backups/test_config/edit", json=update)
        assert resp.status_code == 200
        assert not old_file.exists()
        assert (setup_backups / "renamed_again.json").exists()

    def test_edit_preserves_config_on_rename_failure(self, client, setup_backups, created_backup, valid_backup_dict):
        import dashboard.app
        old_file = setup_backups / "test_config.json"
        backup = dashboard.app.BACKUPS["test_config"]
        with patch.object(backup, "to_json", side_effect=Exception("save fail")):
            update = dict(valid_backup_dict)
            update["config_name"] = "rename_fail"
            resp = client.post("/api/backups/test_config/edit", json=update)
            assert resp.status_code == 500
            assert "test_config" in dashboard.app.BACKUPS
            assert "rename_fail" not in dashboard.app.BACKUPS
