"""TODO:
- Add a webview in another file in `dashboard/` somehow.
- Make a dashboard-style GUI.
    - Load, edit, and save `.json` configurations in `CONFIGS_DIR`.
    - View, start, and stop backups and schedulers.
- idk what else yet
"""

import threading
from pathlib import Path
from urllib.parse import quote
from flask import Flask, render_template

app = Flask(__name__)
def run_app():
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)

def run_app_in_thread():
    flask_thread = threading.Thread(target=run_app, daemon=True)
    flask_thread.start()
    return flask_thread

app.jinja_env.filters["urlencode"] = lambda s: quote(str(s), safe="")

CONFIGS_DIR = None


@app.route("/")
def page_index():
    return render_template("index.html")

@app.route("/config_editor")
def page_config_editor():
    return render_template("config_editor.html")