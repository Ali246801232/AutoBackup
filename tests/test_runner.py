"""Test src/dashboard/runner.py"""

import pytest
from unittest.mock import MagicMock, patch
from dashboard import runner


@pytest.fixture(autouse=True)
def mock_webview():
    with patch("dashboard.runner.webview"):
        yield

def mock_pystray():
    with patch("dashboard.runner.pystray"):
        yield

@pytest.fixture(autouse=True)
def mock_app():
    with (
        patch("dashboard.runner.app"),
        patch("dashboard.runner.ICON_PATH"),
        patch("dashboard.runner.NOTIFIER"),
        patch("dashboard.runner.get_backups"),
        patch("dashboard.runner.get_backup_configs_dir"),
        patch("dashboard.runner.set_backup_configs_dir"),
        patch("dashboard.runner.load_backups"),
        patch("dashboard.runner.save_backups"),
        patch("dashboard.runner.setup_events_queue"),
        patch("dashboard.runner.cleanup_events_queue"),
    ):
        yield


@pytest.fixture(autouse=True)
def reset_state():
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


class TestSetupCleanup:
    def test_setup(self): raise NotImplementedError()
    def test_cleanup(self): raise NotImplementedError()

class TestHandleBackups:
    def test_setup_backups(self): raise NotImplementedError()
    def test_cleanup_backups(self): raise NotImplementedError()

class TestHandleWebviewPystray:
    def test_toggle_window_visible_to_hidden(self): raise NotImplementedError()
    def test_toggle_window_hidden_to_visible(self): raise NotImplementedError()
    def test_on_wndow_closing_quitting_false(self): raise NotImplementedError()
    def test_on_wndow_closing_quitting_true(self): raise NotImplementedError()
    def test_quit_application(self): raise NotImplementedError()
    def test_setup_webview(self): raise NotImplementedError()
    def test_cleanup_webview(self): raise NotImplementedError()
