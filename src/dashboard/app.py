import sys
import webview
from notifypy import Notify
from pathlib import Path
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
        abort(404, f"No backup found for {config_name}")
    return render_template("config_form.html", config_data=backup.to_dict())

@app.route("/new_backup")
def page_new_backup():
    return render_template("config_form.html")


@app.route("/api/backups/")
def api_backups():
    logger.info("Attempting to get backups (/api/backups)")
    backups = {}
    try:
        if BACKUPS is not None:
            for config_name, backup in BACKUPS.items():
                backups[config_name] = backup.to_dict()
                backups[config_name]["status"] = backup.status
        return jsonify(backups)
    except Exception as e:
        logger.error(f"Failed to get backups: {e}")
        return jsonify({"error": f"Error while getting backups: {e}"}), 500


@app.route("/api/backups/<config_name>/start_backup", methods=["POST"])
def api_start_backup(config_name):
    logger.info(f"Attempting to start backup (/api/backups/{config_name}/start_backup)")
    backup = BACKUPS.get(config_name)
    if not backup:
        abort(404, f"No backup found for {config_name}")
    try:
        backup.start_backup()
        return jsonify({"status": "backup started"}), 202
    except Exception as e:
        logger.error(f"Failed to start backup for {config_name}: {e}")
        return jsonify({"error": f"Error while starting backup for {config_name}: {e}"}), 500

@app.route("/api/backups/<config_name>/cancel_backup", methods=["POST"])
def api_cancel_backup(config_name):
    logger.info(f"Attempting to cancel backup (/api/backups/{config_name}/cancel_backup)")
    backup = BACKUPS.get(config_name)
    if not backup:
        abort(404, f"No backup found for {config_name}")
    try:
        backup.cancel_backup()
        return jsonify({"status": "backup cancelled"}), 200
    except Exception as e:
        logger.error(f"Failed to cancel backup for {config_name}: {e}")
        return jsonify({"error": f"Error while cancelling backup for {config_name}: {e}"}), 500


@app.route("/api/backups/<config_name>/start_scheduler", methods=["POST"])
def api_start_scheduler(config_name):
    logger.info(f"Attempting to start scheduler (/api/backups/{config_name}/start_scheduler)")
    backup = BACKUPS.get(config_name)
    if not backup:
        abort(404, f"No backup found for {config_name}")
    try:
        backup.start_scheduler()
        return jsonify({"status": "scheduler started"}), 202
    except Exception as e:
        logger.error(f"Failed to start scheduler for {config_name}: {e}")
        return jsonify({"error": f"Error while starting scheduler for {config_name}: {e}"}), 500

@app.route("/api/backups/<config_name>/stop_scheduler", methods=["POST"])
def api_stop_scheduler(config_name):
    logger.info(f"Attempting to stop scheduler (/api/backups/{config_name}/stop_scheduler)")
    backup = BACKUPS.get(config_name)
    if not backup:
        abort(404, f"No backup found for {config_name}")
    try:
        backup.stop_scheduler()
        return jsonify({"status": "scheduler stopped"}), 200
    except Exception as e:
        logger.error(f"Failed to stop scheduler for {config_name}: {e}")
        return jsonify({"error": f"Error while stopping scheduler for {config_name}: {e}"}), 500


@app.route("/api/backups/<config_name>/delete", methods=["POST"])
def api_delete_backup(config_name):
    logger.info(f"Attempting to delete backup (/api/backups/{config_name}/delete)")
    backup = BACKUPS.get(config_name)
    if not backup:
        abort(404, f"No backup found for {config_name}")

    try:
        if backup.scheduler_running:
            backup.stop_scheduler()
        if backup.backup_running:
            backup.cancel_backup()

        del BACKUPS[config_name]

        config_file = BACKUP_CONFIGS_DIR / f"{config_name}.json"
        config_file.unlink(missing_ok=True)
        return jsonify({"status": "backup deleted"}), 200
    except Exception as e:
        logger.error(f"Failed to delete backup for {config_name}: {e}")
        return jsonify({"error": f"Error while deleting backup for {config_name}: {e}"}), 500


@app.route("/api/backups/new", methods=["POST"])
def api_new_backup():
    logger.info("Attempting to create backup (/api/backups/new)")

    try:
        data = request.get_json() or {}
        if not data:
            return jsonify({"error": "Request body is required"}), 400

        config_name = data.get("config_name")
        if not config_name:
            return jsonify({"error": "A config name is required"}), 400
        if config_name in BACKUPS:
            return jsonify({"error": f"A backup config with the name {config_name} already exists"}), 409
        if not data.get("sources"):
            return jsonify({"error": "At least one source is required"}), 400
        if not data.get("destination"):
            return jsonify({"error": "A Destination is required"}), 400

        backup = Backup.from_dict(data)

        try:
            backup.verify_details()
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        BACKUPS[config_name] = backup
        config_file = BACKUP_CONFIGS_DIR / f"{config_name}.json"
        backup.to_json(config_file)
        return jsonify(backup.to_dict()), 201
    except Exception as e:
        logger.error(f"Failed to create backup: {e}")
        return jsonify({"error": f"Error while creating backup: {e}"}), 500


@app.route("/api/backups/<config_name>/edit", methods=["POST"])
def api_edit_backup(config_name):
    logger.info(f"Attempting to edit backup (/api/backups/{config_name}/edit)")
    backup = BACKUPS.get(config_name)
    if not backup:
        abort(404, f"No backup found for {config_name}")

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
        return jsonify({"status": "backup updated"}), 200
    except HTTPException:
        raise
    except Exception as e:
        if new_name != old_name:
            BACKUPS[old_name] = BACKUPS.pop(new_name)
        backup.update_from_dict(old_config)
        logger.error(f"Failed to update backup for {config_name}: {e}")
        return jsonify({"error": f"Error while updating backup for {config_name}: {e}"}), 500


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
            return jsonify({"error": "This configs directory is already registered for startup"}), 409
        add_to_startup(BACKUP_CONFIGS_DIR, PYTHON_EXECUTABLE)
        return jsonify({"status": "added to startup"}), 200
    except Exception as e:
        logger.error(f"Failed to add to startup: {e}")
        return jsonify({"error": f"Error adding to startup: {e}"}), 500

@app.route("/api/startup/remove", methods=["POST"])
def api_startup_remove():
    try:
        if not is_in_startup(BACKUP_CONFIGS_DIR):
            return jsonify({"error": "This configs directory is not registered for startup"}), 404
        remove_from_startup(BACKUP_CONFIGS_DIR)
        return jsonify({"status": "removed from startup"}), 200
    except Exception as e:
        logger.error(f"Failed to remove from startup: {e}")
        return jsonify({"error": f"Error removing from startup: {e}"}), 500


@app.route("/api/file_dialog", methods=["POST"])
def api_file_dialog():
    logger.info("Attempting to open file dialog")

    data = request.get_json() or {}
    dialog_type = data.get("type", "folder")

    try:
        if dialog_type == "file":
            result = webview.windows[0].create_file_dialog(webview.FileDialog.OPEN)
        else:
            result = webview.windows[0].create_file_dialog(webview.FileDialog.FOLDER)
    except Exception as e:
        logger.error(f"Error while using file dialog: {e}")
        return jsonify({"error": str(e)}), 500

    if result is None:
        return jsonify({"path": None})
    if isinstance(result, (tuple, list)):
        result = result[0]
    return jsonify({"path": str(result)})


@app.route("/api/drive/auth", methods=["POST"])
def api_drive_auth():
    global DRIVE_BROWSER

    logger.info("Attempting to authenticate for Drive browser")

    try:
        handler = DRIVE_BROWSER
        handler.authenticate()
        handler.go_to_root()
        return jsonify({
            "folder_id": handler.current_folder["id"],
            "folder_name": handler.current_folder["title"]
        })
    except Exception as e:
        logger.error(f"Eror authenticating for Drive browser: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/drive/browse", methods=["POST"])
def api_drive_browse():
    global DRIVE_BROWSER

    logger.info("Attempting to open folder in Drive browser")

    data = request.get_json() or {}
    folder_id = data.get("folder_id")

    handler = DRIVE_BROWSER
    if not handler:
        return jsonify({"error": "Google Drive not authenticated"}), 401

    try:
        if folder_id:
            handler.open_folder(folder_id)
        children = handler.get_child_folders()
        return jsonify({
            "folder_id": handler.current_folder["id"],
            "folder_name": handler.current_folder["title"],
            "children": [{"id": c["id"], "name": c["title"]} for c in children]
        })
    except Exception as e:
        logger.error(f"Error opening folder in Drive browser: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/drive/up", methods=["POST"])
def api_drive_up():
    global DRIVE_BROWSER

    logger.info("Attempting to open parent in Drive browser")

    handler = DRIVE_BROWSER
    if not handler:
        return jsonify({"error": "Drive not authenticated"}), 401

    try:
        handler.go_up()
        children = handler.get_child_folders()
        return jsonify({
            "folder_id": handler.current_folder["id"],
            "folder_name": handler.current_folder["title"],
            "children": [{"id": c["id"], "name": c["title"]} for c in children]
        })
    except Exception as e:
        logger.error(f"Error navigating to parent in Drive browser: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/drive/select", methods=["POST"])
def api_drive_select():
    logger.info("Attempting to select folder in Drive browser")

    data = request.get_json() or {}
    folder_id = data.get("folder_id")
    folder_name = data.get("folder_name")

    if not folder_id or not folder_name:
        return jsonify({"error": "folder_id and folder_name are required"}), 400
    logger.info(f"Drive folder selected: {folder_name} ({folder_id})")

    return jsonify({"folder_id": folder_id, "folder_name": folder_name})


@app.route("/api/notify", methods=["POST"])
def api_notify():
    data = request.get_json() or {}
    title = data.get("title", "AutoBackup")
    message = data.get("message", "")
    logger.info(f"Sending notification: {title} — {message}")
    try:
        NOTIFIER.title = title
        NOTIFIER.message = message
        NOTIFIER.send(block=False)
        return jsonify({"status": "notification sent"})
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")
        return jsonify({"error": str(e)}), 500
