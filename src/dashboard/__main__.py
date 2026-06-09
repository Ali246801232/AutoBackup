import pystray
from PIL import Image
from pathlib import Path
import webview

from .app import BACKUP_CONFIGS_DIR, BACKUPS, app
from .logger import logger
from backup import Backup

WINDOW = None
TRAY_ICON = None
WINDOW_VISIBLE = True
QUITTING = False


def load_backups(configs_dir: str | Path) -> dict[str, Backup]:
    """Return a dictionary of backups loaded from a directory of config JSONs."""
    backups = {}
    configs_dir = Path(configs_dir).resolve()
    if not (configs_dir.exists() and configs_dir.is_dir()):
        raise ValueError(f"No config files directory at {configs_dir.absolute()}")
    for config_file in configs_dir.iterdir():
        if not (config_file.is_file() and config_file.suffix == ".json"):
            continue
        backups[config_file.stem] = Backup.from_json(config_file)
    return backups


def save_backups(backups: dict[str, Backup], configs_dir: str | Path):
    """Save a dictionary of backups to a directory as config JSONs."""
    configs_dir = Path(configs_dir).resolve()
    if not (configs_dir.exists() and configs_dir.is_dir()):
        raise ValueError(f"No config files directory at {configs_dir.absolute()}")
    for config_name, backup in backups.items():
        config_file = configs_dir / f"{config_name}.json"
        backup.to_json(config_file)

def setup_backups():
    """Load all backups from config directory, and start their schedulers"""
    global BACKUP_CONFIGS_DIR, BACKUPS

    # Load backups
    logger.info("[DASHBOARD] Attempting to load backups")
    try:
        BACKUP_CONFIGS_DIR = (
            Path(__file__).resolve().parent.parent.parent / "backup_configs"
        )
        BACKUP_CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
        BACKUPS = load_backups(BACKUP_CONFIGS_DIR)
        logger.info(f"[DASHBOARD] Loaded {len(BACKUPS)} backups")
    except Exception as e:
        logger.error(f"[DASHBOARD] Error while loading backups: {e}")
        raise

    # Start schedulers
    logger.info("[DASHBOARD] Attempting to start schedulers")
    for config_name, backup in BACKUPS.items():
        try:
            backup.start_scheduler()
            logger.info(f"[DASHBOARD] Started scheduler for backup {config_name}")
        except Exception as e:
            logger.error(
                f"[DASHBOARD] Error while starting scheduler for backup {config_name}: {e}"
            )

def cleanup_backups():
    """Stop all schedulers, cancel all backups, and save all backup configs"""
    global BACKUP_CONFIGS_DIR, BACKUPS

    logger.info("[DASHBOARD] Attempting to clean up backups")
    if BACKUPS is not None:
        # Stop all schedulers and cancel all backups
        for config_name, backup in BACKUPS.items():
            try:
                backup.stop_scheduler()
                backup.cancel_backup()
                logger.info(f"[DASHBOARD] Stopped backup {config_name}")
            except backup:
                pass
            except Exception as e:
                logger.error(
                    f"[DASHBOARD] Error while stopping backup {config_name} during cleanup: {e}"
                )

        # Save all backups
        if BACKUP_CONFIGS_DIR is not None:
            try:
                save_backups(BACKUPS, BACKUP_CONFIGS_DIR)
                logger.info(f"[DASHBOARD] Saved backups to {BACKUP_CONFIGS_DIR}")
            except Exception as e:
                logger.error(
                    f"[DASHBOARD] Error while saving backups during cleanup: {e}"
                )


def toggle_window(icon, item):
    """Callback for the show/hide option on the tray menu."""
    global WINDOW, WINDOW_VISIBLE
    if WINDOW:
        if WINDOW_VISIBLE:
            WINDOW.hide()
            WINDOW_VISIBLE = False
        else:
            WINDOW.show()
            WINDOW_VISIBLE = True
        icon.update_menu()

def on_window_closing():
    """Hide window instead of close it, unless Quit option was used."""
    global WINDOW, WINDOW_VISIBLE, TRAY_ICON, QUITTING
    if QUITTING:
        return True
    if WINDOW:
        WINDOW.hide()
        WINDOW_VISIBLE = False
        if TRAY_ICON:
            TRAY_ICON.update_menu()
    return False

def quit_application(icon, item):
    """Callback for the quit option on the tray menu."""
    global WINDOW, TRAY_ICON, QUITTING
    QUITTING = True
    if TRAY_ICON:
        TRAY_ICON.stop()
    if WINDOW:
        WINDOW.destroy()

def setup_webview():
    """Create the webview window and start the tray icon."""
    global WINDOW, TRAY_ICON, app

    WINDOW = webview.create_window("AutoBackup", app, width=1280, height=720, hidden=False)
    WINDOW.events.closing += on_window_closing

    menu = pystray.Menu(
        pystray.MenuItem(
            text=lambda item: "Hide Window" if WINDOW_VISIBLE else "Show Window",
            action=toggle_window,
            default=True
        ),
        pystray.MenuItem(
            text="Quit",
            action=quit_application
        ),
    )

    TRAY_ICON = pystray.Icon(
        "AutoBackupTray",
        Image.new("RGB", (64, 64), color="blue"),
        "AutoBackup",
        menu
    )

def cleanup_webview():
    """Close the webview window and the tray icon."""
    global WINDOW, TRAY_ICON
    if TRAY_ICON:
        TRAY_ICON.stop()
    if WINDOW:
        WINDOW.destroy()


def main():
    try:
        setup_backups()
        setup_webview()
        TRAY_ICON.run_detached()
        webview.start()
    finally:
        cleanup_backups()
        cleanup_webview()

if __name__ == "__main__":
    main()