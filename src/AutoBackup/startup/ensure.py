import sys
import platform
from pathlib import Path

from .logger import logger

system = platform.system()

COMMAND = [sys.executable, "-m", "AutoBackup.startup.startup"]
COMMAND_STRING = " ".join(f"\"{c}\"" for c in COMMAND)
def COMMAND_XML(indent: int = 0) -> str:
    base = " " * (indent * 4)
    inner = " " * ((indent + 1) * 4)
    lines = [f'{base}<array>']
    for c in COMMAND:
        lines.append(f'{inner}<string>{c}</string>')
    lines.append(f'{base}</array>')
    return '\n'.join(lines)


def ensure_startup_entry():
    if system == "Windows":
        _ensure_startup_windows()
    elif system == "Linux":
        _ensure_startup_linux()
    elif system == "Darwin":
        _ensure_startup_macos()
    else:
        raise NotImplementedError(f"Unsupported OS: {system}")
    logger.debug("Created/ensured startup entry")

def remove_startup_entry():
    if system == "Windows":
        _remove_startup_windows()
    elif system == "Linux":
        _remove_startup_linux()
    elif system == "Darwin":
        _remove_startup_macos()
    else:
        raise NotImplementedError(f"Unsupported OS: {system}")
    logger.debug("Removed startup entry")


REGISTRY_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
REGISTRY_VALUE_NAME = "AutoBackup"

def _ensure_startup_windows():
    import winreg
    with winreg.OpenKeyEx(
        winreg.HKEY_CURRENT_USER, REGISTRY_KEY,
        0, winreg.KEY_SET_VALUE,
    ) as key:
        winreg.SetValueEx(key, REGISTRY_VALUE_NAME, 0, winreg.REG_SZ, COMMAND_STRING)

def _remove_startup_windows():
    import winreg
    try:
        with winreg.OpenKeyEx(winreg.HKEY_CURRENT_USER, REGISTRY_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, REGISTRY_VALUE_NAME)
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
       f"Exec={COMMAND_STRING}\n"
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
       f"{COMMAND_XML(indent=1)}\n"
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
