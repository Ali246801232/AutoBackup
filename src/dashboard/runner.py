import pystray
import webview
from PIL import Image
from pathlib import Path
from plyer import notification

from .app import app, set_backup_configs_dir, load_backups, save_backups, BACKUPS, BACKUP_CONFIGS_DIR, ICON_PATH
from .logger import logger


WINDOW = None
TRAY_ICON = None
WINDOW_VISIBLE = False
QUITTING = False
FIRST_HIDE = True


def setup_backups(backup_configs_dir: Path, start_schedulers: bool = False):
    """Load all backups from config directory, and optionally start their schedulers"""
    logger.info("Attempting to load backups")
    try:
        set_backup_configs_dir(backup_configs_dir)
        load_backups()
        logger.info(f"Loaded {len(BACKUPS)} backups from {BACKUP_CONFIGS_DIR}")
    except Exception as e:
        logger.error(f"Error while loading backups: {e}")
        raise

    if start_schedulers:
        logger.info("Attempting to start schedulers")
        for config_name, backup in BACKUPS.items():
            try:
                backup.start_scheduler()
                logger.info(f"Started scheduler for backup {config_name}")
            except Exception as e:
                logger.error(f"Error while starting scheduler for backup {config_name}: {e}")

def cleanup_backups():
    """Stop all schedulers, cancel all backups, and save all backup configs"""
    logger.info("Attempting to clean up backups")
    if BACKUPS is not None:
        for config_name, backup in BACKUPS.items():
            try:
                backup.stop_scheduler()
                backup.cancel_backup()
                logger.info(f"Stopped backup {config_name}")
            except Exception as e:
                logger.error(f"Error while stopping backup {config_name} during cleanup: {e}")

        if BACKUP_CONFIGS_DIR is not None:
            try:
                save_backups()
                logger.info(f"Saved {len(BACKUPS)} backups to {BACKUP_CONFIGS_DIR}")
            except Exception as e:
                logger.error(f"Error while saving backups during cleanup: {e}")


def toggle_window(icon, item):
    """Callback for the show/hide option on the tray menu."""
    global WINDOW, WINDOW_VISIBLE
    if WINDOW:
        if WINDOW_VISIBLE:
            WINDOW.hide()
            WINDOW_VISIBLE = False
            logger.info("Webview window hidden")
        else:
            WINDOW.show()
            WINDOW_VISIBLE = True
            logger.info("Webview window shown")
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
            notification.notify(
                title="AutoBackup",
                message="Closing minimizes to system tray.\nTo restore or quit, use the tray icon.\nQuitting cancels ongoing and scheduled backups.",
                timeout=5,
            )
            FIRST_HIDE = False
        logger.info("Webview window hidden")
    return False

def quit_application(icon, item):
    """Callback for the quit option on the tray menu."""
    cleanup_webview()

def setup_webview(start_minimized: bool = False):
    """Create the webview window and start the tray icon."""
    global WINDOW, TRAY_ICON, app

    logger.info("Creating webview window")
    WINDOW = webview.create_window("AutoBackup", app, width=1280, height=720, min_size=(640, 480), hidden=start_minimized)
    WINDOW.events.closing += on_window_closing

    logger.info("Creating tray icon")
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


def run_app(backup_configs_dir: str|Path = None, start_schedulers: bool = False, start_minimized: bool = False):
    logger.info("Running webapp")

    try:
        setup_backups(backup_configs_dir, start_schedulers)
        setup_webview(start_minimized)
        TRAY_ICON.run_detached()
        webview.start()
    except Exception as e:
        logger.error(f"Error while running webapp: {e}")
    finally:
        cleanup_backups()
        cleanup_webview()
