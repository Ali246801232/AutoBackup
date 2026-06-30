import pystray
from PIL import Image
import webview
from pathlib import Path

from .app import BACKUP_CONFIGS_DIR, BACKUPS, set_backup_configs_dir, set_backups, app
from .logger import logger
from backup import Backup

DEFAULT_CONFIGS_DIR = Path.home() / "AutoBackup" / "backup_configs"

WINDOW = None
TRAY_ICON = None
WINDOW_VISIBLE = True
QUITTING = False
FIRST_HIDE = True

STATIC_DIR = Path(__file__).resolve().parent / "static"
ICON_PATH = str(STATIC_DIR / "img" / "logo.png")


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
        BACKUPS = set_backups(load_backups(BACKUP_CONFIGS_DIR))
        logger.info(f"[DASHBOARD] Loaded {len(BACKUPS)} backups from {BACKUP_CONFIGS_DIR}")
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
            except Exception as e:
                logger.error(
                    f"[DASHBOARD] Error while stopping backup {config_name} during cleanup: {e}"
                )

        # Save all backups
        if BACKUP_CONFIGS_DIR is not None:
            try:
                save_backups(BACKUPS, BACKUP_CONFIGS_DIR)
                logger.info(f"[DASHBOARD] Saved {len(BACKUPS)} backups to {BACKUP_CONFIGS_DIR}")
            except Exception as e:
                logger.error(f"[DASHBOARD] Error while saving backups during cleanup: {e}")


def toggle_window(icon, item):
    """Callback for the show/hide option on the tray menu."""
    global WINDOW, WINDOW_VISIBLE
    if WINDOW:
        if WINDOW_VISIBLE:
            WINDOW.hide()
            WINDOW_VISIBLE = False
            logger.info("[DASHBOARD] Webview window hidden")
        else:
            WINDOW.show()
            WINDOW_VISIBLE = True
            logger.info("[DASHBOARD] Webview window shown")
        icon.update_menu()

def on_window_closing():
    """Hide window instead of close it, unless Quit option was used."""
    global WINDOW, WINDOW_VISIBLE, TRAY_ICON, QUITTING, FIRST_HIDE
    if QUITTING:
        return True
    if WINDOW:
        WINDOW.hide()
        WINDOW_VISIBLE = False
        if TRAY_ICON:
            TRAY_ICON.update_menu()
        if FIRST_HIDE:
            TRAY_ICON.notify(message="Closing minizes to system tray.\nTo restore or quit, use the tray icon.\nQuitting cancels ongoing and scheduled backups.")
            FIRST_HIDE = False
        logger.info("[DASHBOARD] Webview window hidden")
    return False

def quit_application(icon, item):
    """Callback for the quit option on the tray menu."""
    cleanup_webview()

def setup_webview():
    """Create the webview window and start the tray icon."""
    global WINDOW, TRAY_ICON, app

    logger.info("[DASHBOARD] Creating webview window")
    WINDOW = webview.create_window("AutoBackup", app, width=1280, height=720, hidden=False)
    WINDOW.events.closing += on_window_closing

    logger.info("[DASHBOARD] Creating tray icon")
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
        Image.open(ICON_PATH),
        "AutoBackup",
        menu
    )

def cleanup_webview():
    """Close the webview window and the tray icon."""
    global WINDOW, TRAY_ICON, QUITTING
    QUITTING = True
    if TRAY_ICON:
        TRAY_ICON.stop()
        TRAY_ICON = None
    if WINDOW:
        WINDOW.destroy()
        WINDOW = None


def setup():
    setup_backups()
    setup_webview()

def cleanup():
    cleanup_webview()
    cleanup_backups()


def run_app(backup_configs_dir: str|Path = None):
    global BACKUP_CONFIGS_DIR, DEFAULT_CONFIGS_DIR

    logger.info("[DASHBOARD] Running webapp")

    if backup_configs_dir is None:
        backup_configs_dir = DEFAULT_CONFIGS_DIR
    BACKUP_CONFIGS_DIR = set_backup_configs_dir(backup_configs_dir)

    try:
        setup()
        TRAY_ICON.run_detached()
        webview.start()
    except Exception as e:
        logger.error(f"Error while running webapp: {e}")
    finally:
        cleanup()
