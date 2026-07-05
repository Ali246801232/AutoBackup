"""Test src/dashboard/app.py"""

import pytest
from unittest.mock import MagicMock, patch
from dashboard import app


@pytest.fixture
def client():
    app.app.config["TESTING"] = True
    with app.app.test_client() as client:
        yield client


@pytest.fixture(autouse=True)
def mock_webview():
    window = MagicMock()
    window.create_file_dialog.return_value = "/selected/path"
    with patch.object(app.webview, "windows", [window]):
        yield

@pytest.fixture(autouse=True)
def mock_notifypy():
    with patch("dashboard.app.Notify"):
        yield

@pytest.fixture(autouse=True)
def mock_DriveHandler():
    with patch("dashboard.app.DriveHandler") as DriveHandler:
        drive_folders = [
            {"id": "drive-id-1", "title": "drive-title-1"},
            {"id": "drive-id-2", "title": "drive-title-2"}
        ]
        DriveHandler.get_child_folders.return_value = drive_folders
        DriveHandler.current_folder = {"id": "current-drive-id", "title": "current-drive-title"}
        yield DriveHandler

@pytest.fixture(autouse=True)
def mock_Backup(backup_dict):
    with patch("dashboard.app.Backup") as Backup:
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
        patch("dashboard.app.is_in_startup") as is_in_startup,
        patch("dashboard.app.add_to_startup") as add_to_startup,
        patch("dashboard.app.remove_from_startup") as remove_from_startup
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
    configs_dir = tmp_path / "configs"
    configs_dir.mkdir()
    app.BACKUP_CONFIGS_DIR = configs_dir
    return configs_dir

@pytest.fixture
def set_backups(client, set_backups_config_dir, backup_dict):
    resp = client.post("/api/backups/new", json=backup_dict)
    assert resp.status_code == 201
    return resp.get_json()


class TestEventQueue:
    def test_setup_events_queue(self): raise NotImplementedError()
    def test_cleanup_events_queue(self): raise NotImplementedError()
    def test_add_to_events_queue(self): raise NotImplementedError()
    def test_drain_events_queue(self): raise NotImplementedError()

    def test_start_backup_watcher(self): raise NotImplementedError()
    def test_stop_backup_watcher(self): raise NotImplementedError()
    def test_start_scheduler_watcher(self): raise NotImplementedError()
    def test_stop_scheduler_watcher(self): raise NotImplementedError()


class TestBackups:
    def test_get_backups(self): raise NotImplementedError()
    def test_get_backup_configs_dir(self): raise NotImplementedError()
    def set_backup_configs_dir(self): raise NotImplementedError()
    def load_backups(self): raise NotImplementedError()
    def save_backups(self): raise NotImplementedError()


class TestPages:
    def test_page_index(self): raise NotImplementedError()
    def test_page_edit_backup(self): raise NotImplementedError()
    def test_page_new_backup(self): raise NotImplementedError()


class TestBackupsApi:
    def test_api_backups(self): raise NotImplementedError()

    def test_api_start_backup(self): raise NotImplementedError()
    def test_api_start_backup_missing_backup(self): raise NotImplementedError()
    def test_api_start_backup_error(self): raise NotImplementedError()

    def test_api_cancel_backup(self): raise NotImplementedError()
    def test_api_cancel_backup_missing_backup(self): raise NotImplementedError()
    def test_api_cancel_backup_error(self): raise NotImplementedError()

    def test_api_start_scheduler(self): raise NotImplementedError()
    def test_api_start_scheduler_missing_backup(self): raise NotImplementedError()
    def test_api_start_scheduler_error(self): raise NotImplementedError()

    def test_api_stop_scheduler(self): raise NotImplementedError()
    def test_api_stop_scheduler_missing_backup(self): raise NotImplementedError()
    def test_api_stop_scheduler_error(self): raise NotImplementedError()


    def test_api_delete_backup(self): raise NotImplementedError()
    def test_api_delete_backup_missing_backup(self): raise NotImplementedError()
    def test_api_delete_backup_error(self): raise NotImplementedError()

    def test_api_new_backup(self): raise NotImplementedError()
    def test_api_new_backup_no_request_body(self): raise NotImplementedError()
    def test_api_new_backup_verify_details_error(self): raise NotImplementedError()
    def test_api_new_backup_error(self): raise NotImplementedError()

    def test_api_edit_backup(self): raise NotImplementedError()
    def test_api_edit_backup_same_config_name(self): raise NotImplementedError()
    def test_api_edit_backup_missing_backup(self): raise NotImplementedError()
    def test_api_edit_backup_no_request_body(self): raise NotImplementedError()
    def test_api_edit_backup_verify_details_error(self): raise NotImplementedError()
    def test_api_edit_backup_error(self): raise NotImplementedError()

    def test_api_events_queue(self): raise NotImplementedError()


class TestStartupApi:
    def test_api_startup_status(self): raise NotImplementedError()
    def test_api_startup_add(self): raise NotImplementedError()
    def test_api_startup_add_already_in_startup(self): raise NotImplementedError()
    def test_api_startup_remove(self): raise NotImplementedError()
    def test_api_startup_remove_not_in_startup(self): raise NotImplementedError()


class TestDriveBrowserApi:
    def api_drive_auth(self): raise NotImplementedError()
    def api_drive_auth_error(self): raise NotImplementedError()
    def api_drive_browse(self): raise NotImplementedError()
    def api_drive_browse_error(self): raise NotImplementedError()
    def api_drive_up(self): raise NotImplementedError()
    def api_drive_up_error(self): raise NotImplementedError()


class TestUtilsApi:
    def test_api_file_dialog_for_file(self): raise NotImplementedError()
    def test_api_file_dialog_for_folder(self): raise NotImplementedError()
    def test_api_file_dialog_for_file_with_initial_path(self): raise NotImplementedError()
    def test_api_file_dialog_for_folder_with_initial_path(self): raise NotImplementedError()

    def test_api_notify(self): raise NotImplementedError()