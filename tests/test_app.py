"""Test src/dashboard/app.py"""

import pytest
from unittest.mock import MagicMock, patch
from AutoBackup.dashboard import app


@pytest.fixture
def client():
    app.app.config["TESTING"] = True
    with app.app.test_client() as client:
        yield client


@pytest.fixture(autouse=True)
def mock_create_file_dialog():
    window = MagicMock()
    window.create_file_dialog.return_value = "/selected/path"
    with patch.object(app.webview, "create_window", return_value=window):
        yield window.create_file_dialog

@pytest.fixture(autouse=True)
def mock_notifypy():
    with patch("AutoBackup.dashboard.app.Notify"):
        yield

@pytest.fixture(autouse=True)
def mock_DriveHandler():
    with patch("AutoBackup.dashboard.app.DriveHandler") as DriveHandler:
        drive_folders = [
            {"id": "drive-id-1", "title": "drive-title-1"},
            {"id": "drive-id-2", "title": "drive-title-2"}
        ]
        DriveHandler.get_child_folders.return_value = drive_folders
        DriveHandler.current_folder = {"id": "current-drive-id", "title": "current-drive-title"}
        yield DriveHandler

@pytest.fixture(autouse=True)
def mock_Backup(backup_dict):
    with patch("AutoBackup.dashboard.app.Backup") as Backup:
        backup = Backup.return_value
        backup.config_name = "test_config"
        backup.wait_for_backup.return_value = {
            "backup_folder": "path/to/folder",
            "drive_backup_folder_id": None
        }
        backup.status = {
            "backup_running": False,
            "backup_error": False,
            "backup_error_message": None,
            "scheduler_running": False,
            "scheduler_error": False,
            "scheduler_error_message": None,
            "backup_progress": {}
        }
        backup.to_dict.return_value = backup_dict
        backup.scheduler_running = False
        backup.backup_running = False
        Backup.from_dict.return_value = backup
        Backup.from_json.return_value = backup
        yield backup

@pytest.fixture(autouse=True)
def mock_startup():
    with (
        patch("AutoBackup.dashboard.app.is_in_startup") as is_in_startup,
        patch("AutoBackup.dashboard.app.add_to_startup") as add_to_startup,
        patch("AutoBackup.dashboard.app.remove_from_startup") as remove_from_startup
    ):
        is_in_startup.return_value = True
        yield


@pytest.fixture
def backup_dict(tmp_path):
    tmp_source = tmp_path / "source"
    tmp_source.mkdir()
    tmp_destination = tmp_path / "destination"
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

@pytest.fixture(autouse=True)
def reset_state():
    try:
        app.cleanup_events_queue()
    except:
        pass
    app.BACKUPS = {}
    app.BACKUP_CONFIGS_DIR = None
    app.NOTIFIER = app.Notify()
    app.DRIVE_BROWSER = app.DriveHandler()
    app.EVENTS_QUEUE = None
    app.GLOBAL_STOP_WATCHING_EVENT = None
    app.BACKUP_WATCHERS = {}
    app.SCHEDULER_WATCHERS = {}
    app.STOP_BACKUP_WATCHER_EVENTS = {}
    app.STOP_SCHEDULER_WATCHER_EVENTS = {}


@pytest.fixture
def set_backups_config_dir(tmp_path):
    configs_dir = tmp_path / "backup_configs"
    configs_dir.mkdir()
    app.BACKUP_CONFIGS_DIR = configs_dir
    return configs_dir

@pytest.fixture
def set_backups(client, set_backups_config_dir, backup_dict):
    resp = client.post("/api/backups/new", json=backup_dict)
    assert resp.status_code == 201
    return app.BACKUPS[backup_dict["config_name"]]


class TestEventQueue:
    def test_setup_events_queue(self):
        app.setup_events_queue()
        assert app.EVENTS_QUEUE is not None
        assert app.GLOBAL_STOP_WATCHING_EVENT is not None

    def test_cleanup_events_queue(self):
        app.setup_events_queue()
        app.cleanup_events_queue()
        assert app.GLOBAL_STOP_WATCHING_EVENT.is_set()

    def test_add_to_events_queue(self):
        app.setup_events_queue()
        app.add_to_events_queue("success", "test-title", "test-message")
        items = app.drain_events_queue()
        assert items == [{"type": "success", "title": "test-title", "message": "test-message"}]

    def test_drain_events_queue(self):
        app.setup_events_queue()
        app.add_to_events_queue("info", "title-1", "message-1")
        app.add_to_events_queue("error", "title-2", "message-2")
        items = app.drain_events_queue()
        assert len(items) == 2
        assert items[0] == {"type": "info", "title": "title-1", "message": "message-1"}
        assert items[1] == {"type": "error", "title": "title-2", "message": "message-2"}

    def test_start_backup_watcher(self, mock_Backup):
        app.setup_events_queue()
        backup = mock_Backup
        app.start_backup_watcher(backup)
        backup.wait_for_backup.assert_called_with(timeout=app.WATCHER_TIMEOUT)
        items = app.drain_events_queue()
        assert len(items) == 1
        assert items[0]["type"] == "success"
        assert items[0]["title"] == backup.config_name

    def test_stop_backup_watcher(self, mock_Backup):
        app.setup_events_queue()
        backup = mock_Backup
        backup.wait_for_backup.side_effect = TimeoutError()
        app.start_backup_watcher(backup)
        app.stop_backup_watcher(backup)
        assert backup.config_name in app.STOP_BACKUP_WATCHER_EVENTS

    def test_start_scheduler_watcher(self, mock_Backup):
        app.setup_events_queue()
        backup = mock_Backup
        app.start_scheduler_watcher(backup)
        backup.wait_for_scheduler.assert_called_with(timeout=app.WATCHER_TIMEOUT)

    def test_stop_scheduler_watcher(self, mock_Backup):
        app.setup_events_queue()
        backup = mock_Backup
        backup.wait_for_scheduler.side_effect = TimeoutError()
        app.start_scheduler_watcher(backup)
        app.stop_scheduler_watcher(backup)
        assert backup.config_name in app.STOP_SCHEDULER_WATCHER_EVENTS


class TestBackups:
    def test_get_backups(self):
        app.BACKUPS = {"test": MagicMock()}
        result = app.get_backups()
        assert result == app.BACKUPS

    def test_get_backup_configs_dir(self):
        app.BACKUP_CONFIGS_DIR = "test"
        result = app.get_backup_configs_dir()
        assert result == "test"

    def test_set_backup_configs_dir(self, tmp_path):
        configs_dir = tmp_path / "test"
        result = app.set_backup_configs_dir(configs_dir)
        assert app.BACKUP_CONFIGS_DIR == configs_dir.resolve()
        assert result == configs_dir.resolve()
        assert configs_dir.exists()

    def test_load_backups(self, set_backups_config_dir, backup_dict):
        config_name = backup_dict["config_name"]
        (app.BACKUP_CONFIGS_DIR / f"{config_name}.json").write_text(
            "{\"config_name\": \"test_config\", \"sources\": [], \"destination\": \"/tmp\"}"
        )
        app.load_backups()
        assert "test_config" in app.BACKUPS

    def test_save_backups(self, set_backups, set_backups_config_dir):
        backup = set_backups
        backup.to_json = MagicMock()
        app.save_backups()
        backup.to_json.assert_called_once()


class TestPages:
    def test_page_index(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_page_edit_backup(self, client, set_backups):
        resp = client.get(f"/edit_backup/{set_backups.config_name}")
        assert resp.status_code == 200

    def test_page_new_backup(self, client):
        resp = client.get("/new_backup")
        assert resp.status_code == 200


class TestBackupsApi:
    def test_api_backups(self, client, set_backups):
        resp = client.get("/api/backups")
        assert resp.status_code == 200
        data = resp.get_json()
        assert set_backups.config_name in data

    def test_api_start_backup(self, client, set_backups):
        app.setup_events_queue()
        resp = client.post(f"/api/backups/{set_backups.config_name}/start_backup")
        assert resp.status_code == 202

    def test_api_start_backup_missing_backup(self, client):
        resp = client.post("/api/backups/nonexistent/start_backup")
        assert resp.status_code == 404

    def test_api_start_backup_error(self, client, set_backups):
        app.setup_events_queue()
        set_backups.start_backup.side_effect = Exception("error")
        resp = client.post(f"/api/backups/{set_backups.config_name}/start_backup")
        assert resp.status_code == 500

    def test_api_cancel_backup(self, client, set_backups):
        resp = client.post(f"/api/backups/{set_backups.config_name}/cancel_backup")
        assert resp.status_code == 200
        set_backups.cancel_backup.assert_called_once()

    def test_api_cancel_backup_missing_backup(self, client):
        resp = client.post("/api/backups/nonexistent/cancel_backup")
        assert resp.status_code == 404

    def test_api_cancel_backup_error(self, client, set_backups):
        set_backups.cancel_backup.side_effect = Exception("error")
        resp = client.post(f"/api/backups/{set_backups.config_name}/cancel_backup")
        assert resp.status_code == 500

    def test_api_start_scheduler(self, client, set_backups):
        app.setup_events_queue()
        resp = client.post(f"/api/backups/{set_backups.config_name}/start_scheduler")
        assert resp.status_code == 202
        set_backups.start_scheduler.assert_called_once()

    def test_api_start_scheduler_missing_backup(self, client):
        resp = client.post("/api/backups/nonexistent/start_scheduler")
        assert resp.status_code == 404

    def test_api_start_scheduler_error(self, client, set_backups):
        app.setup_events_queue()
        set_backups.start_scheduler.side_effect = Exception("error")
        resp = client.post(f"/api/backups/{set_backups.config_name}/start_scheduler")
        assert resp.status_code == 500

    def test_api_stop_scheduler(self, client, set_backups):
        resp = client.post(f"/api/backups/{set_backups.config_name}/stop_scheduler")
        assert resp.status_code == 200
        set_backups.stop_scheduler.assert_called_once()

    def test_api_stop_scheduler_missing_backup(self, client):
        resp = client.post("/api/backups/nonexistent/stop_scheduler")
        assert resp.status_code == 404

    def test_api_stop_scheduler_error(self, client, set_backups):
        set_backups.stop_scheduler.side_effect = Exception("error")
        resp = client.post(f"/api/backups/{set_backups.config_name}/stop_scheduler")
        assert resp.status_code == 500

    def test_api_delete_backup(self, client, set_backups, set_backups_config_dir):
        resp = client.post(f"/api/backups/{set_backups.config_name}/delete")
        assert resp.status_code == 200
        assert set_backups.config_name not in app.BACKUPS

    def test_api_delete_backup_missing_backup(self, client):
        resp = client.post("/api/backups/nonexistent/delete")
        assert resp.status_code == 404

    def test_api_delete_backup_error(self, client, set_backups):
        app.setup_events_queue()
        backup = set_backups
        backup.scheduler_running = True
        backup.stop_scheduler.side_effect = Exception("error")
        resp = client.post(f"/api/backups/{set_backups.config_name}/delete")
        assert resp.status_code == 500

    def test_api_new_backup(self, client, backup_dict, set_backups_config_dir):
        resp = client.post("/api/backups/new", json=backup_dict)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["config_name"] == backup_dict["config_name"]

    def test_api_new_backup_no_request_body(self, client):
        resp = client.post("/api/backups/new", json={})
        assert resp.status_code == 400

    def test_api_new_backup_verify_details_error(self, client, backup_dict, set_backups_config_dir):
        app.Backup.from_dict.return_value.verify_details.side_effect = ValueError("invalid")
        resp = client.post("/api/backups/new", json=backup_dict)
        assert resp.status_code == 400

    def test_api_new_backup_error(self, client, backup_dict, set_backups_config_dir):
        app.Backup.from_dict.side_effect = Exception("error")
        resp = client.post("/api/backups/new", json=backup_dict)
        assert resp.status_code == 500

    def test_api_edit_backup(self, client, set_backups):
        resp = client.post(f"/api/backups/{set_backups.config_name}/edit", json={"config_name": "renamed"})
        assert resp.status_code == 200
        set_backups.update_from_dict.assert_called_once()

    def test_api_edit_backup_missing_backup(self, client):
        resp = client.post("/api/backups/nonexistent/edit", json={"config_name": "test"})
        assert resp.status_code == 404

    def test_api_edit_backup_no_request_body(self, client, set_backups):
        resp = client.post(f"/api/backups/{set_backups.config_name}/edit", json={})
        assert resp.status_code == 400

    def test_api_edit_backup_verify_details_error(self, client, set_backups):
        set_backups.verify_details.side_effect = ValueError("invalid")
        resp = client.post(f"/api/backups/{set_backups.config_name}/edit", json={"config_name": set_backups.config_name})
        assert resp.status_code == 400

    def test_api_edit_backup_error(self, client, set_backups):
        set_backups.to_json.side_effect = Exception("error")
        resp = client.post(f"/api/backups/{set_backups.config_name}/edit", json={"config_name": "renamed"})
        assert resp.status_code == 500

    def test_api_events_queue(self, client):
        app.setup_events_queue()
        app.add_to_events_queue("info", "test", "message")
        resp = client.get("/api/backups/events_queue")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 1
        assert data[0] == {"type": "info", "title": "test", "message": "message"}


class TestStartupApi:
    def test_api_startup_status(self, client, set_backups_config_dir):
        resp = client.get("/api/startup/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["registered"] is True

    def test_api_startup_add(self, client, set_backups_config_dir):
        app.is_in_startup.return_value = False
        resp = client.post("/api/startup/add")
        assert resp.status_code == 200

    def test_api_startup_add_already_in_startup(self, client, set_backups_config_dir):
        app.is_in_startup.return_value = True
        resp = client.post("/api/startup/add")
        assert resp.status_code == 409

    def test_api_startup_remove(self, client, set_backups_config_dir):
        app.is_in_startup.return_value = True
        resp = client.post("/api/startup/remove")
        assert resp.status_code == 200

    def test_api_startup_remove_not_in_startup(self, client, set_backups_config_dir):
        app.is_in_startup.return_value = False
        resp = client.post("/api/startup/remove")
        assert resp.status_code == 404


class TestDriveBrowserApi:
    def test_api_drive_auth(self, client):
        browser = app.DRIVE_BROWSER
        browser.current_folder = {"id": "root-id", "title": "My Drive"}
        resp = client.post("/api/drive/auth")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["folder_id"] == "root-id"
        assert data["folder_name"] == "My Drive"

    def test_api_drive_auth_error(self, client):
        browser = app.DRIVE_BROWSER
        browser.authenticate = MagicMock(side_effect=Exception("auth error"))
        resp = client.post("/api/drive/auth")
        assert resp.status_code == 500

    def test_api_drive_browse(self, client):
        browser = app.DRIVE_BROWSER
        browser.current_folder = {"id": "folder-id", "title": "Folder Title"}
        browser.get_child_folders = MagicMock(return_value=[
            {"id": "child-1", "title": "Child 1"}
        ])
        resp = client.post("/api/drive/browse", json={"folder_id": "some-id"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["folder_id"] == "folder-id"
        assert len(data["children"]) == 1
        assert data["children"][0] == {"id": "child-1", "name": "Child 1"}

    def test_api_drive_browse_error(self, client):
        browser = app.DRIVE_BROWSER
        browser.get_child_folders = MagicMock(side_effect=Exception("error"))
        resp = client.post("/api/drive/browse", json={"folder_id": "some-id"})
        assert resp.status_code == 500

    def test_api_drive_up(self, client):
        browser = app.DRIVE_BROWSER
        browser.current_folder = {"id": "parent-id", "title": "Parent Folder"}
        browser.get_child_folders = MagicMock(return_value=[
            {"id": "folder-1", "title": "Folder 1"}
        ])
        resp = client.post("/api/drive/up")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["folder_id"] == "parent-id"
        assert len(data["children"]) == 1

    def test_api_drive_up_error(self, client):
        browser = app.DRIVE_BROWSER
        browser.get_child_folders = MagicMock(side_effect=Exception("error"))
        resp = client.post("/api/drive/up")
        assert resp.status_code == 500


class TestUtilsApi:
    def test_api_file_dialog_for_file(self, client, mock_create_file_dialog):
        resp = client.post("/api/file_dialog", json={"type": "file"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["path"] == mock_create_file_dialog.return_value

    def test_api_file_dialog_for_folder(self, client, mock_create_file_dialog):
        resp = client.post("/api/file_dialog", json={"type": "folder"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["path"] == mock_create_file_dialog.return_value

    def test_api_file_dialog_for_file_with_initial_path(self, client, tmp_path, mock_create_file_dialog):
        file_path = tmp_path / "existing.txt"
        file_path.write_text("test")
        resp = client.post("/api/file_dialog", json={"type": "file", "initial_path": str(file_path)})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["path"] == mock_create_file_dialog.return_value

    def test_api_file_dialog_for_folder_with_initial_path(self, client, tmp_path, mock_create_file_dialog):
        resp = client.post("/api/file_dialog", json={"type": "folder", "initial_path": str(tmp_path)})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["path"] == mock_create_file_dialog.return_value

    def test_api_notify(self, client):
        resp = client.post("/api/notify", json={"title": "Test", "message": "Hello"})
        assert resp.status_code == 200