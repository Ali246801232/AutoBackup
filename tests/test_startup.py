"""Test src/startup/registry.py, src/startup/startup.py, and src/startup/ensure.py"""

import json
from unittest.mock import MagicMock, patch

import pytest
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

@pytest.fixture
def startup_registry(tmp_path):
    registry_path = tmp_path / "home_dir" / "AutoBackup" / "startup.json"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    dummy_registry = {
        str(tmp_path / "backup_configs" / "test_config_1"): PYTHON_EXECUTABLE,
        str(tmp_path / "backup_configs" / "test_config_2"): PYTHON_EXECUTABLE,
    }
    registry_path.write_text(json.dumps(dummy_registry, indent=4))
    with patch("startup.registry.STARTUP_REGISTRY", registry_path):
        yield registry_path, dummy_registry


@pytest.fixture(autouse=True)
def mock_winreg():
    mock = MagicMock()
    with patch.dict("sys.modules", {"winreg": mock}):
        yield mock

@pytest.fixture(autouse=True)
def mock_popen():
    with patch("startup.startup.subprocess.Popen") as mock:
        yield mock


@pytest.fixture
def windows_system():
    with patch("startup.ensure.system", "Windows"):
        yield

@pytest.fixture
def linux_system():
    with patch("startup.ensure.system", "Linux"):
        yield

@pytest.fixture
def macos_system():
    with patch("startup.ensure.system", "Darwin"):
        yield



class TestRegistry:
    def test_load_registry(self, startup_registry):
        _, dummy_registry = startup_registry
        result = registry.load_registry()
        assert result == dummy_registry

    def test_save_registry(self, startup_registry):
        registry_path, dummy_registry = startup_registry
        new_entry = str(registry_path.parent / "new_config")
        dummy_registry[new_entry] = PYTHON_EXECUTABLE
        registry.save_registry(dummy_registry)
        saved = json.loads(registry_path.read_text(encoding="utf-8"))
        assert saved == dummy_registry

    def test_add_to_startup_new(self, startup_registry):
        registry_path, _ = startup_registry
        new_dir = str(registry_path.parent / "new_config")
        registry.add_to_startup(new_dir, PYTHON_EXECUTABLE)
        saved = json.loads(registry_path.read_text(encoding="utf-8"))
        assert saved.get(new_dir) == PYTHON_EXECUTABLE

    def test_add_to_startup_already_exists(self, startup_registry):
        registry_path, dummy_registry = startup_registry
        existing_dir = next(iter(dummy_registry))
        new_exe = "python_new"
        registry.add_to_startup(existing_dir, new_exe)
        saved = json.loads(registry_path.read_text(encoding="utf-8"))
        assert saved[existing_dir] == new_exe

    def test_remove_from_startup_exists(self, startup_registry):
        registry_path, dummy_registry = startup_registry
        existing_dir = next(iter(dummy_registry))
        registry.remove_from_startup(existing_dir)
        saved = json.loads(registry_path.read_text(encoding="utf-8"))
        assert existing_dir not in saved

    def test_remove_from_startup_missing(self, startup_registry):
        registry_path, dummy_registry = startup_registry
        missing_dir = str(registry_path.parent / "nonexistent")
        registry.remove_from_startup(missing_dir)
        saved = json.loads(registry_path.read_text(encoding="utf-8"))
        assert saved == dummy_registry

    def test_is_in_startup_yes(self, startup_registry):
        _, dummy_registry = startup_registry
        existing_dir = next(iter(dummy_registry))
        assert registry.is_in_startup(existing_dir) is True

    def test_is_in_startup_no(self, startup_registry):
        registry_path, _ = startup_registry
        missing_dir = str(registry_path.parent / "nonexistent")
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

    def test_run_command_windows(self, mock_popen):
        import subprocess
        try:  # handle these tests being run on non-Windows
            expected_flags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
        except AttributeError:
            expected_flags = 0x08000000
        command = ["python", "-c", "pass"]
        with patch("startup.startup.platform.system", return_value="Windows"):
            result = startup.run_command(command)
        mock_popen.assert_called_once_with(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=False,
            creationflags=expected_flags,
        )
        assert result == mock_popen.return_value

    @pytest.mark.parametrize("system_name", ["Linux", "Darwin"])
    def test_run_command_linux_macos(self, mock_popen, system_name):
        import subprocess
        command = ["python", "-c", "pass"]
        with patch("startup.startup.platform.system", return_value=system_name):
            result = startup.run_command(command)
        mock_popen.assert_called_once_with(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=False,
            start_new_session=True,
            close_fds=True,
        )
        assert result == mock_popen.return_value

    def test_run_commands(self, mock_popen):
        commands = [
            ["python", "-c", "pass"],
            ["python", "-V"],
        ]
        result = startup.run_commands(commands)
        assert result == [mock_popen.return_value, mock_popen.return_value]
        assert mock_popen.call_count == len(commands)


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
            f'"{ensure.COMMAND[0]}" "{ensure.COMMAND[1]}"',
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
            f"Exec=\"{ensure.COMMAND[0]}\" \"{ensure.COMMAND[1]}\"\n"
            "Terminal=false\n"
            "X-GNOME-Autostart-enabled=true\n"
        )
        assert content == expected

    def test_ensure_macos(self, macos_system):
        ensure.ensure_startup_entry()
        assert ensure.LAUNCH_AGENT_DIR.is_dir()
        content = ensure.LAUNCH_AGENT_FILE.read_text(encoding="utf-8")
        expected = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
            '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
            '<plist version="1.0">\n'
            '<dict>\n'
            '    <key>Label</key>\n'
            '    <string>com.autobackup.startup</string>\n'
            '    <key>ProgramArguments</key>\n'
            '    <array>\n'
            f'        <string>{ensure.COMMAND[0]}</string>\n'
            f'        <string>{ensure.COMMAND[1]}</string>\n'
            '    </array>\n'
            '    <key>RunAtLoad</key>\n'
            '    <true/>\n'
            '    <key>KeepAlive</key>\n'
            '    <false/>\n'
            '    <key>StandardOutPath</key>\n'
            f'    <string>{ensure.LAUNCH_AGENT_LOG}</string>\n'
            '    <key>StandardErrorPath</key>\n'
            f'    <string>{ensure.LAUNCH_AGENT_LOG}</string>\n'
            '</dict>\n'
            '</plist>'
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
