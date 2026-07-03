import sys
import webview
from pathlib import Path
from notifypy import Notify
from urllib.parse import quote
from flask import Flask, render_template, abort, jsonify, request
from werkzeug.exceptions import HTTPException

from backup import Backup, DriveHandler
from startup import is_in_startup, add_to_startup, remove_from_startup
from .logger import logger


app = Flask(__name__)
app.jinja_env.filters["urlencode"] = lambda s: quote(str(s), safe="")

@app.context_processor
def inject_globals():
    return {"configs_dir": str(BACKUP_CONFIGS_DIR)}


PYTHON_EXECUTABLE: str = sys.executable
DRIVE_BROWSER: DriveHandler = DriveHandler()
STATIC_DIR = Path(__file__).resolve().parent / "static"
ICON_PATH = str(STATIC_DIR / "img" / "logo.png")
NOTIFIER = Notify()
NOTIFIER.icon = ICON_PATH


DEFAULT_BACKUP_CONFIGS_DIR = Path.home() / "AutoBackup" / "backup_configs"
BACKUP_CONFIGS_DIR: Path = DEFAULT_BACKUP_CONFIGS_DIR
BACKUPS: dict[str, Backup]  = {}

def set_backup_configs_dir(dir_path: str | Path = None) -> Path:
    global BACKUP_CONFIGS_DIR
    if dir_path is None:
        dir_path = DEFAULT_BACKUP_CONFIGS_DIR
    BACKUP_CONFIGS_DIR = Path(dir_path).resolve()
    BACKUP_CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
    return BACKUP_CONFIGS_DIR

def load_backups():
    """Load the dictionary of backups from the directory of config JSONs."""
    global BACKUP_CONFIGS_DIR, BACKUPS
    BACKUPS = {}
    if not (BACKUP_CONFIGS_DIR.exists() and BACKUP_CONFIGS_DIR.is_dir()):
        raise ValueError(f"No config files directory at {BACKUP_CONFIGS_DIR.absolute()}")
    for config_file in BACKUP_CONFIGS_DIR.iterdir():
        if not (config_file.is_file() and config_file.suffix == ".json"):
            continue
        BACKUPS[config_file.stem] = Backup.from_json(config_file)

def save_backups():
    """Save the dictionary of backups to the directory as config JSONs."""
    global BACKUPS, BACKUP_CONFIGS_DIR
    if not (BACKUP_CONFIGS_DIR.exists() and BACKUP_CONFIGS_DIR.is_dir()):
        raise ValueError(f"No config files directory at {BACKUP_CONFIGS_DIR.absolute()}")
    for config_name, backup in BACKUPS.items():
        config_file = BACKUP_CONFIGS_DIR / f"{config_name}.json"
        backup.to_json(config_file)


@app.route("/")
def page_index():
    return render_template("index.html")

@app.route("/edit_backup/<config_name>")
def page_edit_backup(config_name):
    backup = BACKUPS.get(config_name)
    if not backup:
        abort(404, f"No backup found for \"{config_name}\"")
    return render_template("config_form.html", config_data=backup.to_dict())

@app.route("/new_backup")
def page_new_backup():
    return render_template("config_form.html")


@app.route("/api/backups/")
def api_backups():
    backups = {}
    try:
        if BACKUPS is not None:
            for config_name, backup in BACKUPS.items():
                backups[config_name] = backup.to_dict()
                backups[config_name]["status"] = backup.status

        logger.info(f"Fetched {len(backups)} backups")
        return jsonify(backups)
    except Exception as e:
        logger.error(f"Failed to fetch backups: {e}")
        return jsonify({"error": f"Failed to fetch backups: {e}"}), 500


@app.route("/api/backups/<config_name>/start_backup", methods=["POST"])
def api_start_backup(config_name):
    backup = BACKUPS.get(config_name)
    if not backup:
        abort(404, f"No backup found for \"{config_name}\"")
    try:
        backup.start_backup()

        logger.info(f"Started backup for \"{config_name}\"")
        return jsonify({"status": f"Started backup for \"{config_name}\""}), 202
    except Exception as e:
        logger.error(f"Failed to start backup for \"{config_name}\": {e}")
        return jsonify({"error": f"Failed to start backup for \"{config_name}\": {e}"}), 500

@app.route("/api/backups/<config_name>/cancel_backup", methods=["POST"])
def api_cancel_backup(config_name):
    backup = BACKUPS.get(config_name)
    if not backup:
        abort(404, f"No backup found for \"{config_name}\"")
    try:
        backup.cancel_backup()

        logger.info(f"Cancelled backup for \"{config_name}\"")
        return jsonify({"status": f"Cancelled backup for \"{config_name}\""}), 200
    except Exception as e:
        logger.error(f"Failed to cancel backup for \"{config_name}\": {e}")
        return jsonify({"error": f"Failed to cancel backup for \"{config_name}\": {e}"}), 500


@app.route("/api/backups/<config_name>/start_scheduler", methods=["POST"])
def api_start_scheduler(config_name):
    backup = BACKUPS.get(config_name)
    if not backup:
        abort(404, f"No backup found for \"{config_name}\"")
    try:
        backup.start_scheduler()

        logger.info(f"Started scheduler for \"{config_name}\"")
        return jsonify({"status": f"Started scheduler for \"{config_name}\""}), 202
    except Exception as e:
        logger.error(f"Failed to start scheduler for \"{config_name}\": {e}")
        return jsonify({"error": f"Failed to start scheduler for \"{config_name}\": {e}"}), 500

@app.route("/api/backups/<config_name>/stop_scheduler", methods=["POST"])
def api_stop_scheduler(config_name):
    backup = BACKUPS.get(config_name)
    if not backup:
        abort(404, f"No backup found for \"{config_name}\"")
    try:
        backup.stop_scheduler()

        logger.info(f"Stopped scheduler for \"{config_name}\"")
        return jsonify({"status": f"Stopped scheduler for \"{config_name}\""}), 200
    except Exception as e:
        logger.error(f"Failed to stop scheduler for \"{config_name}\": {e}")
        return jsonify({"error": f"Failed to stop scheduler for \"{config_name}\": {e}"}), 500


@app.route("/api/backups/<config_name>/delete", methods=["POST"])
def api_delete_backup(config_name):
    backup = BACKUPS.get(config_name)
    if not backup:
        abort(404, f"No backup found for \"{config_name}\"")

    try:
        if backup.scheduler_running:
            backup.stop_scheduler()
        if backup.backup_running:
            backup.cancel_backup()

        del BACKUPS[config_name]

        config_file = BACKUP_CONFIGS_DIR / f"{config_name}.json"
        config_file.unlink(missing_ok=True)

        logger.info(f"Deleted backup for \"{config_name}\"")
        return jsonify({"status": f"Deleted backup for \"{config_name}\""}), 200
    except Exception as e:
        logger.error(f"Failed to delete backup for \"{config_name}\": {e}")
        return jsonify({"error": f"Failed to delete backup for \"{config_name}\": {e}"}), 500


@app.route("/api/backups/new", methods=["POST"])
def api_new_backup():

    data = request.get_json() or {}
    if not data:
        return jsonify({"error": "Request body is empty"}), 400
    config_name = data.get("config_name")

    try:
        if config_name in BACKUPS:
            return jsonify({"error": f"A backup config with the name {config_name} already exists"}), 409
        try:
            backup = Backup.from_dict(data)
            backup.verify_details()
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        BACKUPS[config_name] = backup
        config_file = BACKUP_CONFIGS_DIR / f"{config_name}.json"
        backup.to_json(config_file)

        logger.info(f"Created backup: {config_name}")
        return jsonify(backup.to_dict()), 201
    except Exception as e:
        logger.error(f"Failed to create backup: {e}")
        return jsonify({"error": f"Failed to create backup: {e}"}), 500


@app.route("/api/backups/<config_name>/edit", methods=["POST"])
def api_edit_backup(config_name):
    backup = BACKUPS.get(config_name)
    if not backup:
        abort(404, f"No backup found for \"{config_name}\"")

    old_config = backup.to_dict()
    old_name = backup.config_name
    new_name = old_name
    try:
        new_config = request.get_json() or {}
        new_name = new_config.get("config_name", old_name)

        if new_name != old_name and new_name in BACKUPS:
            abort(409, f"A backup with the name {new_name} already exists")

        BACKUPS[new_name] = BACKUPS.pop(old_name)
        backup.update_from_dict(new_config)
        backup.verify_details()

        if new_name != old_name:
            (BACKUP_CONFIGS_DIR / f"{old_name}.json").unlink(missing_ok=True)
        config_file = BACKUP_CONFIGS_DIR / f"{new_name}.json"

        backup.to_json(config_file)

        logger.info(f"Updated backup for \"{config_name}\"" + (f"to {new_name}" if new_name else ""))
        return jsonify({"status": f"Updated backup for \"{config_name}\"" + (f"to {new_name}" if new_name else "")}), 200
    except HTTPException:
        raise
    except Exception as e:
        if new_name != old_name:
            BACKUPS[old_name] = BACKUPS.pop(new_name)
        backup.update_from_dict(old_config)
        logger.error(f"Failed to update backup for \"{config_name}\": {e}")
        return jsonify({"error": f"Failed to update backup for \"{config_name}\": {e}"}), 500


@app.route("/api/startup/status")
def api_startup_status():
    return jsonify({
        "registered": is_in_startup(BACKUP_CONFIGS_DIR),
        "configs_dir": str(BACKUP_CONFIGS_DIR),
    })

@app.route("/api/startup/add", methods=["POST"])
def api_startup_add():
    if not PYTHON_EXECUTABLE:
        return jsonify({"error": "Python executable path not available"}), 500
    try:
        if is_in_startup(BACKUP_CONFIGS_DIR):
            return jsonify({"error": "This configs directory is already registered to run at startup"}), 409
        add_to_startup(BACKUP_CONFIGS_DIR, PYTHON_EXECUTABLE)
        
        logger.info(f"Added to startup")
        return jsonify({"status": "Added to startup"}), 200
    except Exception as e:
        logger.error(f"Failed to add to startup: {e}")
        return jsonify({"error": f"Failed to add to startup: {e}"}), 500

@app.route("/api/startup/remove", methods=["POST"])
def api_startup_remove():
    try:
        if not is_in_startup(BACKUP_CONFIGS_DIR):
            return jsonify({"error": "This configs directory is not registered to run at startup"}), 404
        remove_from_startup(BACKUP_CONFIGS_DIR)
        logger.info(f"Removed from startup")
        return jsonify({"status": "Removed from startup"}), 200
    except Exception as e:
        logger.error(f"Failed to remove from startup: {e}")
        return jsonify({"error": f"Failed to remove from startup: {e}"}), 500


@app.route("/api/file_dialog", methods=["POST"])
def api_file_dialog():

    data = request.get_json() or {}
    dialog_type = data.get("type", "folder")
    initial_path = data.get("initial_path")

    kwargs = {}
    if initial_path:
        p = Path(initial_path)
        if p.is_file():
            kwargs = {"directory": str(p.parent)}
        elif p.is_dir():
            kwargs = {"directory": initial_path}

    try:
        if dialog_type == "file":
            result = webview.windows[0].create_file_dialog(webview.FileDialog.OPEN, **kwargs)
        else:
            result = webview.windows[0].create_file_dialog(webview.FileDialog.FOLDER, **kwargs)
    except Exception as e:
        logger.error(f"Error while using file dialog: {e}")
        return jsonify({"error": f"Error while using file dialog: {e}"}), 500

    if result is None:
        return jsonify({"path": None})
    if isinstance(result, (tuple, list)):
        result = result[0]

    logger.info(f"Got {result} from file dialog")
    return jsonify({"path": str(result)})


@app.route("/api/drive/auth", methods=["POST"])
def api_drive_auth():
    global DRIVE_BROWSER


    try:
        handler = DRIVE_BROWSER
        handler.authenticate()
        handler.go_to_root()

        logger.info(f"Authenticated for Drive browser")
        return jsonify({
            "folder_id": handler.current_folder["id"],
            "folder_name": handler.current_folder["title"]
        })
    except Exception as e:
        logger.error(f"Error authenticating for Drive browser: {e}")
        return jsonify({"error": f"Error authenticating for Drive browser: {e}"}), 500

@app.route("/api/drive/browse", methods=["POST"])
def api_drive_browse():
    global DRIVE_BROWSER

    data = request.get_json() or {}
    folder_id = data.get("folder_id")
    handler = DRIVE_BROWSER
    if not handler:
        return jsonify({"error": "Google Drive not authenticated"}), 401

    try:
        if folder_id:
            handler.open_folder(folder_id)
        children = handler.get_child_folders()

        logger.info(f"Opened folder {folder_id} in Drive browser")
        return jsonify({
            "folder_id": handler.current_folder["id"],
            "folder_name": handler.current_folder["title"],
            "children": [{"id": c["id"], "name": c["title"]} for c in children]
        })
    except Exception as e:
        logger.error(f"Error opening folder {folder_id} in Drive browser: {e}")
        return jsonify({"error": f"Error opening folder {folder_id} in Drive browser: {e}"}), 500

@app.route("/api/drive/up", methods=["POST"])
def api_drive_up():
    global DRIVE_BROWSER


    handler = DRIVE_BROWSER
    if not handler:
        return jsonify({"error": "Google Drive is not authenticated"}), 401

    try:
        handler.go_up()
        children = handler.get_child_folders()

        logger.info("Opened parent in Drive browser")
        return jsonify({
            "folder_id": handler.current_folder["id"],
            "folder_name": handler.current_folder["title"],
            "children": [{"id": c["id"], "name": c["title"]} for c in children]
        })
    except Exception as e:
        logger.error(f"Error navigating to parent in Drive browser: {e}")
        return jsonify({"error": f"Error navigating to parent in Drive browser: {e}"}), 500

@app.route("/api/notify", methods=["POST"])
def api_notify():
    data = request.get_json() or {}
    title = data.get("title", "AutoBackup")
    message = data.get("message", "")
    try:
        NOTIFIER.title = title
        NOTIFIER.message = message
        NOTIFIER.send(block=False)
        logger.info("Sent notification")
        return jsonify({"status": "Sent notification"})
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")
        return jsonify({"error": f"Failed to send notification: {e}"}), 500
