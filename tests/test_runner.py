"""Test src/dashboard/runner.py"""

import pytest
from unittest.mock import MagicMock, patch
from AutoBackup.dashboard import runner


@pytest.fixture(autouse=True)
def mock_webview():
    with patch("AutoBackup.dashboard.runner.webview"):
        yield

@pytest.fixture(autouse=True)
def mock_pystray():
    with patch("AutoBackup.dashboard.runner.pystray"):
        yield

@pytest.fixture(autouse=True)
def mock_PIL_image():
    with patch("PIL.Image.open"):
        yield

@pytest.fixture(autouse=True)
def mock_app():
    with (
        patch("AutoBackup.dashboard.runner.app"),
        patch("AutoBackup.dashboard.runner.ICON_PATH"),
        patch("AutoBackup.dashboard.runner.NOTIFIER"),
        patch("AutoBackup.dashboard.runner.setup_backups"),
        patch("AutoBackup.dashboard.runner.cleanup_backups"),
        patch("AutoBackup.dashboard.runner.setup_events_queue"),
        patch("AutoBackup.dashboard.runner.cleanup_events_queue"),
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


@pytest.fixture
def set_webview_tray():
    runner.WINDOW = MagicMock()
    runner.TRAY_ICON = MagicMock()
    runner.WINDOW_VISIBLE = True
    runner.QUITTING = False
    runner.FIRST_HIDE = True


class TestSetupCleanup:
    def test_setup(self):
        with (
            patch.object(runner, 'setup_webview'),
            patch.object(runner, 'setup_backups'),
            patch.object(runner, 'setup_events_queue')
        ):
            runner.setup("test", True, True)
            runner.setup_backups.assert_called_once_with("test", True)
            runner.setup_webview.assert_called_once_with(True)
            runner.setup_events_queue.assert_called_once()

    def test_cleanup(self):
        with (
            patch.object(runner, 'cleanup_webview'),
            patch.object(runner, 'cleanup_backups'),
            patch.object(runner, 'cleanup_events_queue')
        ):
            runner.cleanup()
            runner.cleanup_events_queue.assert_called_once()
            runner.cleanup_backups.assert_called_once()
            runner.cleanup_webview.assert_called_once()



class TestHandleWebviewPystray:
    def test_toggle_window_visible_to_hidden(self, set_webview_tray):
        runner.WINDOW_VISIBLE = True
        runner.toggle_window(runner.TRAY_ICON, None)
        runner.WINDOW.hide.assert_called_once()
        assert runner.WINDOW_VISIBLE is False
        runner.TRAY_ICON.update_menu.assert_called_once()

    def test_toggle_window_hidden_to_visible(self, set_webview_tray):
        runner.WINDOW_VISIBLE = False
        runner.toggle_window(runner.TRAY_ICON, None)
        runner.WINDOW.show.assert_called_once()
        assert runner.WINDOW_VISIBLE is True

    def test_on_wndow_closing_quitting_false(self, set_webview_tray):
        result = runner.on_window_closing()
        assert result is False
        runner.WINDOW.hide.assert_called_once()
        assert runner.WINDOW_VISIBLE is False
        assert runner.FIRST_HIDE is False

    def test_on_wndow_closing_quitting_true(self, set_webview_tray):
        runner.QUITTING = True
        result = runner.on_window_closing()
        assert result is True

    def test_quit_application(self, set_webview_tray):
        tray = runner.TRAY_ICON
        window = runner.WINDOW
        runner.quit_application(runner.TRAY_ICON, None)
        assert runner.QUITTING is True
        assert runner.WINDOW is None
        assert runner.TRAY_ICON is None
        tray.stop.assert_called_once()
        window.destroy.assert_called_once()

    def test_setup_webview(self):
        runner.setup_webview(start_minimized=False)
        assert runner.WINDOW is not None
        assert runner.TRAY_ICON is not None
        runner.webview.create_window.assert_called_once()

    def test_cleanup_webview(self, set_webview_tray):
        tray = runner.TRAY_ICON
        window = runner.WINDOW
        runner.cleanup_webview()
        assert runner.QUITTING is True
        assert runner.WINDOW is None
        assert runner.TRAY_ICON is None
        tray.stop.assert_called_once()
        window.destroy.assert_called_once()
