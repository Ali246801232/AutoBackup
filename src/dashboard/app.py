"""TODO:
- Add a webview in another file in `dashboard/` somehow.
- Make a dashboard-style GUI.
    - Load, edit, and save `.json` configurations in `CONFIGS_DIR`.
    - View, start, and stop backups and schedulers.
- idk what else yet
"""
import argparse
from pathlib import Path
from waitress import serve
from urllib.parse import quote
from flask import Flask, render_template, abort, jsonify, request
from werkzeug.exceptions import HTTPException

from backup import Backup
from .logger import logger


BACKUP_CONFIGS_DIR: Path = None
BACKUPS: dict[str, Backup] = None


app = Flask(__name__)

app.jinja_env.filters["urlencode"] = lambda s: quote(str(s), safe="")

@app.route("/")
def page_index():
    return render_template("index.html")

@app.route("/edit_config/<config_name>")
def page_config_editor(config_name):
    return render_template("edit_config.html", config_name=config_name)


@app.route("/api/backups/")
def api_backups():
    logger.info("Attempting to get backups (/api/backups)")
    backups = {}
    try:
        for config_name, backup in BACKUPS.items():
            backups[config_name] = backup.to_dict()
        return jsonify(backups)
    except Exception as e:
        logger.error(f"[FLASK APP] Failed to get backups: {e}")
        return jsonify({"error": f"Error while getting backups: {e}"}), 500

@app.route("/api/backups/<config_name>/status")
def api_backup_status(config_name):
    logger.info(f"[FLASK APP] Attempting to get backup status (/api/backups/{config_name}/status)")
    backup = BACKUPS.get(config_name)
    if not backup:
        abort(404, f"No backup found for {config_name}")
    try:
        return jsonify(backup.status)
    except Exception as e:
        logger.error(f"[FLASK APP] Failed to get status for {config_name}: {e}")
        return jsonify({"error": f"Error while getting status for {config_name}: {e}"}), 500


@app.route("/api/backups/<config_name>/start_backup", methods=["POST"])
def api_start_backup(config_name):
    logger.info(f"[FLASK APP] Attempting to start backup (/api/backups/{config_name}/start_backup)")
    backup = BACKUPS.get(config_name)
    if not backup:
        abort(404, f"No backup found for {config_name}")
    try:
        backup.start_backup()
        return jsonify({"status": "backup started"}), 202
    except Exception as e:
        logger.error(f"[FLASK APP] Failed to start backup for {config_name}: {e}")
        return jsonify({"error": f"Error while starting backup for {config_name}: {e}"}), 500

@app.route("/api/backups/<config_name>/cancel_backup", methods=["POST"])
def api_cancel_backup(config_name):
    logger.info(f"[FLASK APP] Attempting to cancel backup (/api/backups/{config_name}/cancel_backup)")
    backup = BACKUPS.get(config_name)
    if not backup:
        abort(404, f"No backup found for {config_name}")
    try:
        backup.cancel_backup()
        return jsonify({"status": "backup cancelled"}), 200
    except Exception as e:
        logger.error(f"[FLASK APP] Failed to cancel backup for {config_name}: {e}")
        return jsonify({"error": f"Error while cancelling backup for {config_name}: {e}"}), 500

@app.route("/api/backups/<config_name>/start_scheduler", methods=["POST"])
def api_start_scheduler(config_name):
    logger.info(f"[FLASK APP] Attempting to start scheduler (/api/backups/{config_name}/start_scheduler)")
    backup = BACKUPS.get(config_name)
    if not backup:
        abort(404, f"No backup found for {config_name}")
    try:
        backup.start_scheduler()
        return jsonify({"status": "scheduler started"}), 202
    except Exception as e:
        logger.error(f"[FLASK APP] Failed to start scheduler for {config_name}: {e}")
        return jsonify({"error": f"Error while starting scheduler for {config_name}: {e}"}), 500

@app.route("/api/backups/<config_name>/stop_scheduler", methods=["POST"])
def api_stop_scheduler(config_name):
    logger.info(f"[FLASK APP] Attempting to stop scheduler (/api/backups/{config_name}/stop_scheduler)")
    backup = BACKUPS.get(config_name)
    if not backup:
        abort(404, f"No backup found for {config_name}")
    try:
        backup.stop_scheduler()
        return jsonify({"status": "scheduler stopped"}), 200
    except Exception as e:
        logger.error(f"[FLASK APP] Failed to stop scheduler for {config_name}: {e}")
        return jsonify({"error": f"Error while stopping scheduler for {config_name}: {e}"}), 500


@app.route("/api/backups/<config_name>/edit", methods=["POST"])
def api_edit_backup(config_name):
    logger.info(f"[FLASK APP] Attempting to edit backup (/api/backups/{config_name}/edit)")
    backup = BACKUPS.get(config_name)
    if not backup:
        abort(404, f"No backup found for {config_name}")

    old_config = backup.to_dict()
    old_name = backup.config_name
    new_name = old_name
    try:
        new_config = request.get_json()
        new_name = new_config.get("config_name", old_name)

        if new_name != old_name and new_name in BACKUPS:
            abort(409, f"A backup with the name '{new_name}' already exists")

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
        logger.error(f"[FLASK APP] Failed to update backup for {config_name}: {e}")
        return jsonify({"error": f"Error while updating backup for {config_name}: {e}"}), 500

@app.route("/api/backups/new", methods=["POST"])
def api_new_backup():
    logger.info("[FLASK APP] Attempting to create backup (/api/backups/new)")

    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is required"}), 400

        config_name = data.get("config_name")
        if not config_name:
            return jsonify({"error": "A config name is required"}), 400
        if config_name in BACKUPS:
            return jsonify({"error": f"A backup config with the name '{config_name}' already exists"}), 409
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
        logger.error(f"[FLASK APP] Failed to create backup: {e}")
        return jsonify({"error": f"Error while creating backup: {e}"}), 500

@app.route("/api/backups/<config_name>/delete", methods=["POST"])
def api_delete_backup(config_name):
    logger.info(f"[FLASK APP] Attempting to delete backup (/api/backups/{config_name}/delete)")
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
        logger.error(f"[FLASK APP] Failed to delete backup for {config_name}: {e}")
        return jsonify({"error": f"Error while deleting backup for {config_name}: {e}"}), 500


def load_backups(configs_dir: str|Path) -> dict[str, Backup]:
    """Return a dictionary of backups loaded from a directory of config JSONs."""
    backups = {}
    configs_dir = Path(configs_dir).resolve()
    if not(configs_dir.exists() and configs_dir.is_dir()):
        raise ValueError(f"No config files directory at {configs_dir.absolute()}")
    for config_file in configs_dir.iterdir():
        if not(config_file.is_file() and config_file.suffix == ".json"):
            continue
        backups[config_file.stem] = Backup.from_json(config_file)
    return backups

def save_backups(backups: dict[str, Backup], configs_dir: str|Path):
    """Save a dictionary of backups to a directory as config JSONs."""
    configs_dir = Path(configs_dir).resolve()
    if not(configs_dir.exists() and configs_dir.is_dir()):
        raise ValueError(f"No config files directory at {configs_dir.absolute()}")
    for config_name, backup in backups.items():
        config_file = configs_dir / f"{config_name}.json"
        backup.to_json(config_file)

def main(configs_dir: str, port: int):
    global BACKUP_CONFIGS_DIR, BACKUPS

    # Load backups
    logger.info("Attempting to load backups")
    try:
        BACKUP_CONFIGS_DIR = Path(configs_dir).resolve()
        BACKUP_CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
        BACKUPS = load_backups(BACKUP_CONFIGS_DIR)
        logger.info(f"[FLASK APP] Loaded {len(BACKUPS)} backups")
    except Exception as e:
        logger.error(f"[FLASK APP] Error while loading backups: {e}")
        raise

    # Start schedulers
    logger.info("Attempting to start schedulers")
    for config_name, backup in BACKUPS.items():
        try:
            backup.start_scheduler()
            logger.info(f"[FLASK APP] Started scheduler for backup {config_name}")
        except Exception as e:
            logger.error(f"[FLASK APP] Error while starting scheduler for backup {config_name}: {e}")

    # Run flask app
    logger.info("Attempting to start flask app")
    try:
        host = "127.0.0.1"
        serve(app, host=host, port=port)
    except Exception as e:
        logger.error(f"[FLASK APP] Error while running flask app: {e}")
        raise

    # Clean up
    finally:
        logger.info("Attempting to clean up")
        if BACKUPS is not None:
            # Stop all schedulers and cancel all backups
            for config_name, backup in BACKUPS.items():
                try:
                    backup.stop_scheduler()
                    backup.cancel_backup()
                except Exception as e:
                    logger.error(f"[FLASK APP] Error while stopping backup {config_name} during cleanup: {e}")

            # Save all backups
            if BACKUP_CONFIGS_DIR is not None:
                try:
                    save_backups(BACKUPS, BACKUP_CONFIGS_DIR)
                except Exception as e:
                    logger.error(f"[FLASK APP] Error while saving backups during cleanup: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Flask webapp for AutoBackup")
    parser.add_argument("--configs-dir", type=str, required=True, help="Directory for backup configurations")
    parser.add_argument("--port", type=int, required=False, help="Port of 127.0.0.1 to host flask app on", default=5000)
    args = parser.parse_args()
    main(args.configs_dir, args.port)
