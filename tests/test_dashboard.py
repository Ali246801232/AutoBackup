"""Test src/dashboard/app.py and src/dashboard/runner.py"""

import pytest
from unittest.mock import MagicMock, patch
from dashboard import app, runner


@pytest.fixture
def client():
    app.app.config["TESTING"] = True
    with app.app.test_client() as client:
        yield client


@pytest.fixture(autouse=True)
def mock_runner_dependencies():
    with (
        patch("dashboard.runner.webview"),
        patch("dashboard.runner.pystray"),
        patch("dashboard.runner.Image.open"),
    ):
        yield

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
def reset_app_state():
    app.BACKUPS = {}
    app.BACKUP_CONFIGS_DIR = None

    app.NOTIFIER = app.Notify()
    app.DRIVE_BROWSER = app.DriveHandler()

    try:
        app.cleanup_events_queue()
    except:
        pass
    app.EVENTS_QUEUE = None
    app.GLOBAL_STOP_WATCHING_EVENT = None
    app.BACKUP_WATCHERS = {}
    app.SCHEDULER_WATCHERS = {}
    app.STOP_BACKUP_WATCHER_EVENTS = {}
    app.STOP_SCHEDULER_WATCHER_EVENTS = {}


@pytest.fixture(autouse=True)
def reset_runner_state():
    try:
        runner.cleanup_backups()
        runner.cleanup_webview()
    except:
        pass
    runner.WINDOW = None
    runner.TRAY_ICON = None
    runner.WINDOW_VISIBLE = False
    runner.QUITTING = False
    runner.FIRST_HIDE = True

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
