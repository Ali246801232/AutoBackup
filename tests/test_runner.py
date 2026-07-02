import json
from unittest.mock import MagicMock, patch

import pytest

from backup import Backup


@pytest.fixture(autouse=True)
def _mock_gui_deps():
    with patch.dict("sys.modules", {
        "pystray": MagicMock(),
        "PIL": MagicMock(),
        "PIL.Image": MagicMock(),
        "webview": MagicMock(),
        "notifypy": MagicMock(),
    }):
        yield


@pytest.fixture
def mock_setup_webview():
    with (
        patch("dashboard.runner.webview") as mock_wv,
        patch("dashboard.runner.pystray") as mock_tray,
        patch("dashboard.runner.Image") as mock_img,
    ):
        mock_wv.create_window.return_value = MagicMock()
        mock_wv.create_window.return_value.events.closing = MagicMock()
        mock_tray.Icon.return_value = MagicMock()
        yield mock_wv, mock_tray, mock_img


class TestSetupBackups:
    def test_setup_backups_loads_and_starts_schedulers(self, tmp_path):
        from dashboard.runner import setup_backups
        import dashboard.app
        backup_instance = Backup("test_backup", [tmp_path/"source"], tmp_path/"destination")
        configs_dir = tmp_path / "configs"
        configs_dir.mkdir()
        backup_instance.to_json(configs_dir / "test_backup.json")
        setup_backups(configs_dir, start_schedulers=True)
        assert "test_backup" in dashboard.app.BACKUPS

    def test_setup_backups_creates_configs_dir(self, tmp_path):
        from dashboard.runner import setup_backups
        import dashboard.app
        configs_dir = tmp_path / "nonexistent"
        setup_backups(configs_dir)
        assert configs_dir.exists()

    def test_setup_backups_handles_scheduler_error(self, tmp_path):
        from dashboard.runner import setup_backups
        import dashboard.runner as runner
        backup_instance = Backup("test_backup", [tmp_path/"source"], tmp_path/"destination")
        configs_dir = tmp_path / "configs"
        configs_dir.mkdir()
        backup_instance.to_json(configs_dir / "test_backup.json")
        with patch.object(Backup, "start_scheduler", side_effect=Exception("sched err")):
            setup_backups(configs_dir, start_schedulers=True)


class TestCleanupBackups:
    def test_cleanup_stops_schedulers_and_saves(self, tmp_path):
        from dashboard.runner import cleanup_backups
        import dashboard.runner as runner
        configs_dir = tmp_path / "configs"
        configs_dir.mkdir()
        runner.BACKUP_CONFIGS_DIR = configs_dir
        backup = MagicMock()
        backup.config_name = "test_backup"
        backup.to_dict.return_value = {"config_name": "test_backup"}
        runner.BACKUPS = {"test_backup": backup}
        cleanup_backups()
        backup.stop_scheduler.assert_called_once()
        backup.cancel_backup.assert_called_once()

    def test_cleanup_no_backups(self):
        from dashboard.runner import cleanup_backups
        import dashboard.runner as runner
        runner.BACKUPS = {}
        cleanup_backups()

    def test_cleanup_no_configs_dir(self, tmp_path):
        from dashboard.runner import cleanup_backups
        import dashboard.runner as runner
        backup = MagicMock()
        backup.config_name = "test_backup"
        runner.BACKUP_CONFIGS_DIR = None
        runner.BACKUPS = {"test_backup": backup}
        cleanup_backups()
        backup.stop_scheduler.assert_called_once()

    def test_cleanup_handles_stop_error(self, tmp_path):
        from dashboard.runner import cleanup_backups
        import dashboard.runner as runner
        configs_dir = tmp_path / "configs"
        configs_dir.mkdir()
        runner.BACKUP_CONFIGS_DIR = configs_dir
        backup = MagicMock()
        backup.config_name = "test_backup"
        backup.stop_scheduler.side_effect = Exception("stop err")
        runner.BACKUPS = {"test_backup": backup}
        cleanup_backups()


class TestLoadBackupsRunner:
    def test_load_backups_skips_non_json_files(self, tmp_path):
        import dashboard.app
        configs_dir = tmp_path / "configs"
        configs_dir.mkdir()
        (configs_dir / "not_json.txt").write_text("{}")
        dashboard.app.BACKUP_CONFIGS_DIR = configs_dir
        from dashboard.app import load_backups
        load_backups()
        assert dashboard.app.BACKUPS == {}

    def test_load_backups_invalid_json(self, tmp_path):
        import dashboard.app
        configs_dir = tmp_path / "configs"
        configs_dir.mkdir()
        (configs_dir / "bad.json").write_text("not json")
        dashboard.app.BACKUP_CONFIGS_DIR = configs_dir
        from dashboard.app import load_backups
        with pytest.raises(json.JSONDecodeError):
            load_backups()

    def test_load_backups_nonexistent_dir(self, tmp_path):
        import dashboard.app
        dashboard.app.BACKUP_CONFIGS_DIR = tmp_path / "nonexistent"
        from dashboard.app import load_backups
        with pytest.raises(ValueError, match="No config files directory at"):
            load_backups()

    def test_load_backups_empty_dir(self, tmp_path):
        import dashboard.app
        configs_dir = tmp_path / "empty"
        configs_dir.mkdir()
        dashboard.app.BACKUP_CONFIGS_DIR = configs_dir
        from dashboard.app import load_backups
        load_backups()
        assert dashboard.app.BACKUPS == {}


class TestSaveBackupsRunner:
    def test_save_backups(self, tmp_path):
        import dashboard.app
        backup_instance = Backup("test_backup", [tmp_path/"source"], tmp_path/"destination")
        configs_dir = tmp_path / "configs"
        configs_dir.mkdir()
        dashboard.app.BACKUP_CONFIGS_DIR = configs_dir
        dashboard.app.BACKUPS = {"test_backup": backup_instance}
        from dashboard.app import save_backups
        save_backups()
        assert (configs_dir / "test_backup.json").exists()
        data = json.loads((configs_dir / "test_backup.json").read_text())
        assert data["config_name"] == "test_backup"

    def test_save_backups_nonexistent_dir(self, tmp_path):
        import dashboard.app
        backup_instance = Backup("test_backup", [tmp_path/"source"], tmp_path/"destination")
        dashboard.app.BACKUP_CONFIGS_DIR = tmp_path / "nonexistent"
        dashboard.app.BACKUPS = {"test_backup": backup_instance}
        from dashboard.app import save_backups
        with pytest.raises(ValueError, match="No config files directory at"):
            save_backups()


class TestWebviewFunctions:
    def test_toggle_window_show(self):
        from dashboard.runner import toggle_window, WINDOW, WINDOW_VISIBLE
        import dashboard.runner as runner
        window = MagicMock()
        icon = MagicMock()
        runner.WINDOW = window
        runner.WINDOW_VISIBLE = False
        toggle_window(icon, None)
        window.show.assert_called_once()
        assert runner.WINDOW_VISIBLE is True

    def test_toggle_window_hide(self):
        from dashboard.runner import toggle_window
        import dashboard.runner as runner
        window = MagicMock()
        icon = MagicMock()
        runner.WINDOW = window
        runner.WINDOW_VISIBLE = True
        toggle_window(icon, None)
        window.hide.assert_called_once()
        assert runner.WINDOW_VISIBLE is False

    def test_toggle_window_no_window(self):
        from dashboard.runner import toggle_window
        import dashboard.runner as runner
        runner.WINDOW = None
        icon = MagicMock()
        toggle_window(icon, None)

    def test_on_window_closing_hides(self):
        from dashboard.runner import on_window_closing
        import dashboard.runner as runner
        window = MagicMock()
        icon = MagicMock()
        runner.WINDOW = window
        runner.TRAY_ICON = icon
        runner.QUITTING = False
        runner.WINDOW_VISIBLE = True
        runner.FIRST_HIDE = True
        with patch("dashboard.runner.Notify") as mock_notify:
            result = on_window_closing()
        assert result is False
        window.hide.assert_called_once()
        assert runner.WINDOW_VISIBLE is False

    def test_on_window_closing_quitting(self):
        from dashboard.runner import on_window_closing
        import dashboard.runner as runner
        runner.QUITTING = True
        result = on_window_closing()
        assert result is True

    def test_quit_application(self):
        from dashboard.runner import quit_application
        with patch("dashboard.runner.cleanup_webview") as mock_cleanup:
            quit_application(None, None)
            mock_cleanup.assert_called_once()


class TestSetupCleanupWebview:
    def test_setup_webview(self, mock_setup_webview):
        from dashboard.runner import setup_webview
        import dashboard.runner as runner
        mock_wv, mock_tray, mock_img = mock_setup_webview
        setup_webview()
        mock_wv.create_window.assert_called_once()
        assert runner.WINDOW is not None
        mock_tray.Icon.assert_called_once()
        assert runner.TRAY_ICON is not None

    def test_cleanup_webview(self, mock_setup_webview):
        from dashboard.runner import cleanup_webview
        import dashboard.runner as runner
        mock_wv, mock_tray, mock_img = mock_setup_webview
        runner.TRAY_ICON = mock_tray.Icon.return_value
        runner.WINDOW = mock_wv.create_window.return_value
        cleanup_webview()
        assert runner.QUITTING is True
        mock_tray.Icon.return_value.stop.assert_called_once()
        mock_wv.create_window.return_value.destroy.assert_called_once()
        assert runner.TRAY_ICON is None
        assert runner.WINDOW is None

    def test_cleanup_webview_no_window(self, mock_setup_webview):
        from dashboard.runner import cleanup_webview
        import dashboard.runner as runner
        runner.TRAY_ICON = None
        runner.WINDOW = None
        cleanup_webview()
        assert runner.QUITTING is True

    def test_on_window_closing_first_hide_notification(self):
        from dashboard.runner import on_window_closing
        import dashboard.runner as runner
        window = MagicMock()
        runner.WINDOW = window
        runner.TRAY_ICON = MagicMock()
        runner.QUITTING = False
        runner.FIRST_HIDE = True
        with patch("dashboard.runner.NOTIFIER") as mock_notif:
            on_window_closing()
            mock_notif.send.assert_called_once()
            assert runner.FIRST_HIDE is False


class TestRunApp:
    def test_run_app_default_configs_dir(self, mock_setup_webview):
        with (
            patch("dashboard.runner.setup_backups") as mock_setup_b,
            patch("dashboard.runner.setup_webview") as mock_setup_w,
            patch("dashboard.runner.cleanup_backups") as mock_cleanup_b,
            patch("dashboard.runner.cleanup_webview") as mock_cleanup_w,
            patch("dashboard.runner.webview") as mock_wv,
        ):
            from dashboard.runner import run_app
            run_app()
            mock_setup_b.assert_called_once()
            mock_setup_w.assert_called_once()
            mock_cleanup_b.assert_called_once()
            mock_cleanup_w.assert_called_once()

    def test_run_app_custom_configs_dir(self, mock_setup_webview, tmp_path):
        with (
            patch("dashboard.runner.setup_backups") as mock_setup_b,
            patch("dashboard.runner.setup_webview") as mock_setup_w,
            patch("dashboard.runner.cleanup_backups") as mock_cleanup_b,
            patch("dashboard.runner.cleanup_webview") as mock_cleanup_w,
        ):
            from dashboard.runner import run_app
            custom_dir = tmp_path / "custom_configs"
            run_app(str(custom_dir))
            mock_setup_b.assert_called_once_with(str(custom_dir), False)
            mock_setup_w.assert_called_once_with(False)
            mock_cleanup_b.assert_called_once()
            mock_cleanup_w.assert_called_once()

    def test_run_app_handles_setup_exception(self, mock_setup_webview):
        with (
            patch("dashboard.runner.setup_backups", side_effect=Exception("setup fail")),
            patch("dashboard.runner.cleanup_backups") as mock_cleanup_b,
            patch("dashboard.runner.cleanup_webview") as mock_cleanup_w,
        ):
            from dashboard.runner import run_app
            run_app()
            mock_cleanup_b.assert_called_once()
            mock_cleanup_w.assert_called_once()
