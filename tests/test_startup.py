"""Test src/startup/registry.py, src/startup/startup.py, and src/startup/ensure.py"""

import json

import pytest
from unittest.mock import MagicMock, patch
from startup import registry, startup, ensure

PYTHON_EXECUTABLE = "python"


@pytest.fixture(autouse=True)
def ensure_paths(tmp_path):
    home = tmp_path / "home_dir"
    autostart_dir = home / ".config" / "autostart"
    launch_agent_dir = home / "Library" / "LaunchAgents"
    with (
        patch("startup.ensure.AUTOSTART_DIR", autostart_dir),
        patch("startup.ensure.AUTOSTART_FILE", autostart_dir / "AutoBackup.desktop"),
        patch("startup.ensure.LAUNCH_AGENT_DIR", launch_agent_dir),
        patch("startup.ensure.LAUNCH_AGENT_FILE", launch_agent_dir / "com.autobackup.startup.plist"),
        patch("startup.ensure.LAUNCH_AGENT_LOG", launch_agent_dir / "autobackup.log"),
    ):
        yield autostart_dir, launch_agent_dir

@pytest.fixture(autouse=True)
def startup_registry(tmp_path):
    yield {
        str(tmp_path / "backup_configs" / "test_config_1"): PYTHON_EXECUTABLE,
        str(tmp_path / "backup_configs" / "test_config_2"): PYTHON_EXECUTABLE,
    }

@pytest.fixture(autouse=True)
def startup_registry_path(tmp_path, startup_registry):
    registry_path = tmp_path / "home_dir" / "AutoBackup" / "startup.json"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(startup_registry, indent=4))
    with patch("startup.registry.STARTUP_REGISTRY", registry_path):
        yield registry_path


@pytest.fixture(autouse=True)
def mock_winreg():
    winreg = MagicMock()
    with patch.dict("sys.modules", {"winreg": winreg}):
        yield winreg

@pytest.fixture(autouse=True)
def mock_Popen():
    with patch("startup.startup.subprocess.Popen") as Popen:
        yield Popen


@pytest.fixture
def windows_system():
    with (
        patch("startup.ensure.system", "Windows"),
        patch("startup.startup.system", "Windows"),
    ):
        yield

@pytest.fixture
def linux_system():
    with (
        patch("startup.ensure.system", "Linux"),
        patch("startup.startup.system", "Linux"),
    ):
        yield

@pytest.fixture
def macos_system():
    with (
        patch("startup.ensure.system", "Darwin"),
        patch("startup.startup.system", "Darwin"),
    ):
        yield


class TestRegistry:
    def test_load_registry(self, startup_registry, startup_registry_path):
        result = registry.load_registry()
        assert result == startup_registry

    def test_save_registry(self, startup_registry, startup_registry_path):
        new_entry = str(startup_registry_path.parent / "new_config")
        startup_registry[new_entry] = PYTHON_EXECUTABLE
        registry.save_registry(startup_registry)
        saved = json.loads(startup_registry_path.read_text(encoding="utf-8"))
        assert saved == startup_registry

    def test_add_to_startup_new(self, startup_registry, startup_registry_path):
        new_dir = str(startup_registry_path.parent / "new_config")
        registry.add_to_startup(new_dir, PYTHON_EXECUTABLE)
        saved = json.loads(startup_registry_path.read_text(encoding="utf-8"))
        assert saved.get(new_dir) == PYTHON_EXECUTABLE

    def test_add_to_startup_already_exists(self, startup_registry, startup_registry_path):
        existing_dir = next(iter(startup_registry))
        new_exe = "python_new"
        registry.add_to_startup(existing_dir, new_exe)
        saved = json.loads(startup_registry_path.read_text(encoding="utf-8"))
        assert saved[existing_dir] == new_exe

    def test_remove_from_startup_exists(self, startup_registry, startup_registry_path):
        existing_dir = next(iter(startup_registry))
        registry.remove_from_startup(existing_dir)
        saved = json.loads(startup_registry_path.read_text(encoding="utf-8"))
        assert existing_dir not in saved

    def test_remove_from_startup_missing(self, startup_registry, startup_registry_path, tmp_path):
        missing_dir = str(tmp_path / "missing")
        registry.remove_from_startup(missing_dir)
        saved = json.loads(startup_registry_path.read_text(encoding="utf-8"))
        assert saved == startup_registry

    def test_is_in_startup_yes(self, startup_registry, startup_registry_path):
        existing_dir = next(iter(startup_registry))
        assert registry.is_in_startup(existing_dir) is True

    def test_is_in_startup_no(self, startup_registry, startup_registry_path, tmp_path):
        missing_dir = str(tmp_path / "missing")
        assert registry.is_in_startup(missing_dir) is False


class TestStartupScript:
    def test_build_commands(self):
        dummy = {
            "/path/to/configs/work": "python",
            "/path/to/configs/personal": "python3",
        }
        expected = [
            ["python", "-m", "AutoBackup", "--configs-dir", "/path/to/configs/work", "--start-minimized", "--start-schedulers"],
            ["python3", "-m", "AutoBackup", "--configs-dir", "/path/to/configs/personal", "--start-minimized", "--start-schedulers"],
        ]
        assert startup.build_commands(dummy) == expected

    def test_run_command_windows(self, windows_system, mock_Popen):
        import subprocess
        command = ["python", "-c", "pass"]
        with (  # patch in case tests run on non-Windows
            patch("startup.startup.subprocess.CREATE_NO_WINDOW", 0x08000000, create=True),
            patch("startup.startup.subprocess.DETACHED_PROCESS", 0x00000008, create=True),
        ):
            result = startup.run_command(command)
        mock_Popen.assert_called_once_with(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=False,
            creationflags=0x08000008,
        )
        assert result == mock_Popen.return_value

    def test_run_command_linux(self, linux_system, mock_Popen):
        import subprocess
        command = ["python", "-c", "pass"]
        result = startup.run_command(command)
        mock_Popen.assert_called_once_with(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=False,
            start_new_session=True,
            close_fds=True,
        )
        assert result == mock_Popen.return_value

    def test_run_command_macos(self, macos_system, mock_Popen):
        import subprocess
        command = ["python", "-c", "pass"]
        result = startup.run_command(command)
        mock_Popen.assert_called_once_with(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=False,
            start_new_session=True,
            close_fds=True,
        )
        assert result == mock_Popen.return_value

    def test_run_commands(self, mock_Popen):
        commands = [
            ["python", "-c", "pass"],
            ["python", "-V"],
        ]
        result = startup.run_commands(commands)
        assert result == [mock_Popen.return_value, mock_Popen.return_value]
        assert mock_Popen.call_count == len(commands)


class TestEnsureStartupEntry:
    def test_ensure_windows(self, windows_system, mock_winreg):
        ensure.ensure_startup_entry()
        key = mock_winreg.OpenKey.return_value
        mock_winreg.OpenKey.assert_called_once_with(
            mock_winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            mock_winreg.KEY_SET_VALUE,
        )
        mock_winreg.SetValueEx.assert_called_once_with(
            key,
            "AutoBackup",
            0,
            mock_winreg.REG_SZ,
            ensure.COMMAND_STRING,
        )
        mock_winreg.CloseKey.assert_called_once_with(key)

    def test_ensure_linux(self, linux_system):
        ensure.ensure_startup_entry()
        assert ensure.AUTOSTART_DIR.is_dir()
        content = ensure.AUTOSTART_FILE.read_text(encoding="utf-8")
        expected = (
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=AutoBackup\n"
           f"Exec={ensure.COMMAND_STRING}\n"
            "Terminal=false\n"
            "X-GNOME-Autostart-enabled=true\n"
        )
        assert content == expected

    def test_ensure_macos(self, macos_system):
        ensure.ensure_startup_entry()
        assert ensure.LAUNCH_AGENT_DIR.is_dir()
        content = ensure.LAUNCH_AGENT_FILE.read_text(encoding="utf-8")
        expected = (
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
            "<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">\n"
            "<plist version=\"1.0\">\n"
            "<dict>\n"
            "    <key>Label</key>\n"
           f"    <string>{ensure.PLIST_LABEL}</string>\n"
            "    <key>ProgramArguments</key>\n"
           f"{ensure.COMMAND_XML(indent=1)}\n"
            "    <key>RunAtLoad</key>\n"
            "    <true/>\n"
            "    <key>KeepAlive</key>\n"
            "    <false/>\n"
            "    <key>StandardOutPath</key>\n"
           f"    <string>{ensure.LAUNCH_AGENT_LOG}</string>\n"
            "    <key>StandardErrorPath</key>\n"
           f"    <string>{ensure.LAUNCH_AGENT_LOG}</string>\n"
            "</dict>\n"
            "</plist>"
        )
        assert content == expected


class TestRemoveStartupEntry:
    def test_remove_windows(self, windows_system, mock_winreg):
        ensure.ensure_startup_entry()

        ensure.remove_startup_entry()

        key = mock_winreg.OpenKey.return_value
        mock_winreg.DeleteValue.assert_called_once_with(key, "AutoBackup")
        mock_winreg.CloseKey.assert_any_call(key)

    def test_remove_linux(self, linux_system):
        ensure.ensure_startup_entry()
        assert ensure.AUTOSTART_FILE.is_file()
        ensure.remove_startup_entry()
        assert not ensure.AUTOSTART_FILE.exists()

    def test_remove_macos(self, macos_system):
        ensure.ensure_startup_entry()
        assert ensure.LAUNCH_AGENT_FILE.is_file()
        ensure.remove_startup_entry()
        assert not ensure.LAUNCH_AGENT_FILE.exists()
