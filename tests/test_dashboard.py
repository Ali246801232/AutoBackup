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
    with patch("dashboard.app.notify.Notify"):
        yield

@pytest.fixture(autouse=True)
def mock_DriveHandler():
    with patch("dashboard.app.backup.DriveHandler") as DriveHandler:
        drive_folders = [
            {"id": "drive-id-1", "title": "drive-title-1"},
            {"id": "drive-id-2", "title": "drive-title-2"}
        ]
        DriveHandler.get_child_folders.return_value = drive_folders
        DriveHandler.current_folder = {"id": "current-drive-id", "title": "current-drive-title"}
        yield DriveHandler

@pytest.fixture(autouse=True)
def mock_startup():
    with (
        patch("dashboard.app.startup.is_in_startup") as is_in_startup,
        patch("dashboard.app.startup.add_to_startup") as add_to_startup,
        patch("dashboard.app.startup.remove_from_startup") as remove_from_startup
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
def _reset_state():
    previous = app.BACKUPS, app.BACKUP_CONFIGS_DIR
    app.BACKUPS = {}
    app.BACKUP_CONFIGS_DIR = None
    yield
    app.BACKUPS, app.BACKUP_CONFIGS_DIR = previous

@pytest.fixture
def set_backups_config_dir(tmp_path):
    configs_dir = tmp_path / "configs"
    configs_dir.mkdir()
    app.BACKUP_CONFIGS_DIR = configs_dir
    return configs_dir

@pytest.fixture
def set_backups(client, set_backups_config_dir, valid_backup_dict):
    resp = client.post("/api/backups/new", json=valid_backup_dict)
    assert resp.status_code == 201
    return resp.get_json()
