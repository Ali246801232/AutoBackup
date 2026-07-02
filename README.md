# AutoBackup

A desktop application made with Python for automated backups with optional Google Drive upload.


## Overview

AutoBackup lets you define backup configs to use. Each config requires a name, one or more source paths, and a destination directory. Optionally, it may also specify paths to exclude, a schedule for recurring backups (requires adding to startup), and an option to upload to a Google Drive folder (requires [some setup](#google-drive-setup)).

The application runs as a desktop application with a system tray icon and provides a [Flask](https://flask.palletsprojects.com/) webapp for the dashboard that runs in a [pywebview](https://pywebview.flowrl.com/) window for managing backup configs.


## Quickstart

> [!IMPORTANT]
> Python 3.10+ is required for this project.

1. Clone the repository:
    ```bash
    git clone https://github.com/Ali246801232/AutoBackup
    cd AutoBackup
    ```

2. Create a virtual environment (optional, but recommended):
    ```bash
    python -m venv .venv
    .venv/Scripts/Activate  # Windows
    .venv/bin/activate      # Linux/macOS
    ```

3. Install the project:
    ```bash
    pip install .
    ```

4. Run the project with the default configs directory:
    ```bash
    AutoBackup
    ```

5. Or run with a custom backup configs directory:
    ```bash
    AutoBackup --configs-dir "path/to/backup_configs/"
    ```

6. Create a new backup config with the `+` button.

7. To use scheduling, add the config directory to run at startup from `≡` → `⏻ Startup Settings` → `Add to Startup`.

> [!NOTE]
> Scheduling is only supported for Windows, Linux, and macOS.

## Google Drive Setup

To allow Google Drive uploads, you will need a `client_secrets.json` file to allow the app to access the Google Drive API and upload files. To do this, follow these steps:

1. Go to the [Google Cloud console](https://console.cloud.google.com/) and select a project you've made or create a new project.

2. Enable the [Google Drive API](https://console.cloud.google.com/apis/library/drive.googleapis.com) for your project.

3. Configure your project's [OAuth consent screen](https://console.cloud.google.com/auth/overview) by following the instructions on the page.

4. On the [credentials page](https://console.cloud.google.com/apis/credentials), click "Create credentials" and then "OAuth client ID":
    1. Select "Web application" for *Application type*.
    2. Enter an appropriate *Name*.
    3. Add `http://localhost:8080/` to *Authorized redirect URIs*.
    4. Click *Create*.
    5. On the *OAuth client created* window, scroll down and click *Download JSON*.

5. Rename the downloaded file to `client_secrets.json` and place it in [`src/backup/`](src/backup/).


## Dashboard

The dashboard opens in a pywebview window that runs a flask webapp; it allows you to:

- View all configured backups and their status.
- Start and cancel backups manually.
- Start and stop schedulers for recurring backups.
- Create, edit, and delete backup configurations.

The application minimizes to the system tray when the window is closed. Use the tray icon to restore the window or to quit the application.

The dashboard and backup functionality are the same program, so **quitting the dashboard will cancel all backups and schedulers.**


## Config Files

In the configs directory, each config is stored in a `.json` file:

```json
{
    "config_name": "my_backup",
    "sources": [
        "/home/user/Documents/report.pdf",
        "/home/user/Documents/notes",
        "/home/user/Pictures"
    ],
    "destination": "/mnt/backup",
    "exclusions": [
        "/home/user/Pictures/thumbs.db"
    ],
    "schedule": {
        "count": 1,
        "unit": "days"
    },
    "drive_upload": true,
    "drive_folder_id": "some-drive-folder-id"
}
```

| Field | Description |
|---|---|
| `config_name` | A name for the backup config. |
| `sources` | Files and folders to back up. |
| `destination` | Destination directory for the backup. |
| `exclusions` | Files and folders to exclude from the backup. |
| `schedule` | Schedule interval (`count` and `unit`); `null` for no schedule. |
| `drive_upload` | Whether to upload the backup to Google Drive. |
| `drive_folder_id` | Google Drive folder ID for uploads. |

By default these `.json` files are stored in:
- `/home/user_name/AutoBackup/backup_configs/` on Linux.
- `/Users/user_name/AutoBackup/backup_configs/` on macOS.
- `C:\Users\user_name\AutoBackup\backup_configs\` on Windows.