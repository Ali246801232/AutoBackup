import sys
import platform
from pathlib import Path

system = platform.system()

STARTUP_SCRIPT = (Path(__file__).resolve().parent / "startup.py").resolve()
COMMAND = [sys.executable, STARTUP_SCRIPT]


def ensure_startup_entry():
    if system == "Windows":
        _ensure_startup_windows()
    elif system == "Darwin":
        _ensure_startup_macos()
    elif system == "Linux":
        _ensure_startup_linux()
    else:
        raise NotImplementedError(f"Unsupported OS: {system}")

def remove_startup_entry():
    if system == "Windows":
        _remove_startup_windows()
    elif system == "Darwin":
        _remove_startup_macos()
    elif system == "Linux":
        _remove_startup_linux()
    else:
        raise NotImplementedError(f"Unsupported OS: {system}")


REGISTRY_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
REGISTRY_VALUE_NAME = "AutoBackup"

def _ensure_startup_windows():
    import winreg
    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, REGISTRY_KEY,
        0, winreg.KEY_SET_VALUE,
    )
    winreg.SetValueEx(
        key, REGISTRY_VALUE_NAME, 0, winreg.REG_SZ,
        f"\"{COMMAND[0]}\" \"{COMMAND[1]}\""
    )
    winreg.CloseKey(key)

def _remove_startup_windows():
    import winreg
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, REGISTRY_KEY,
            0, winreg.KEY_SET_VALUE,
        )
        winreg.DeleteValue(key, REGISTRY_VALUE_NAME)
        winreg.CloseKey(key)
    except FileNotFoundError:
        pass



AUTOSTART_DIR = Path.home() / ".config" / "autostart"
AUTOSTART_FILE = AUTOSTART_DIR / "AutoBackup.desktop"

def _ensure_startup_linux():
    AUTOSTART_DIR.mkdir(parents=True, exist_ok=True)
    desktop_content = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=AutoBackup\n"
        f"Exec=\"{COMMAND[0]}\" \"{COMMAND[1]}\"\n"
        "Terminal=false\n"
        "X-GNOME-Autostart-enabled=true\n"
    )
    AUTOSTART_FILE.write_text(desktop_content, encoding="utf-8")

def _remove_startup_linux():
    AUTOSTART_FILE.unlink(missing_ok=True)


PLIST_LABEL = "com.autobackup.startup"
LAUNCH_AGENT_DIR = Path.home() / "Library" / "LaunchAgents"
LAUNCH_AGENT_FILE = LAUNCH_AGENT_DIR / f"{PLIST_LABEL}.plist"
LAUNCH_AGENT_LOG = LAUNCH_AGENT_DIR / "autobackup.log"

def _ensure_startup_macos():
    LAUNCH_AGENT_DIR.mkdir(parents=True, exist_ok=True)
    plist_content = (
         "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
         "<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">\n"
         "<plist version=\"1.0\">\n"
         "<dict>\n"
         "    <key>Label</key>\n"
        f"    <string>{PLIST_LABEL}</string>\n"
         "    <key>ProgramArguments</key>\n"
         "    <array>\n"
        f"        <string>{COMMAND[0]}</string>\n"
        f"        <string>{COMMAND[1]}</string>\n"
         "    </array>\n"
         "    <key>RunAtLoad</key>\n"
         "    <true/>\n"
         "    <key>KeepAlive</key>\n"
         "    <false/>\n"
         "    <key>StandardOutPath</key>\n"
        f"    <string>{LAUNCH_AGENT_LOG}</string>\n"
         "    <key>StandardErrorPath</key>\n"
        f"    <string>{LAUNCH_AGENT_LOG}</string>\n"
         "</dict>\n"
         "</plist>"
    )
    LAUNCH_AGENT_FILE.write_text(plist_content, encoding="utf-8")

def _remove_startup_macos():
    LAUNCH_AGENT_FILE.unlink(missing_ok=True)
