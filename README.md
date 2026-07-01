# AutoBackup

A desktop application made with Python for automated backups with optional Google Drive upload.

## Overview

AutoBackup lets you define backup configs to use. Each config requires a name, one or more source paths, and a destination directory. Optionally, it may also specify paths to exclude, a schedule for recurring backups, and an option to upload to a Google Drive folder.

The application runs as a desktop application with a system tray icon and provides a [Flask](https://flask.palletsprojects.com/) webapp for the dashboard that runs in a [pywebview](https://pywebview.flowrl.com/) window for managing backup configs.

## Quickstart

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
4. Run the project:
    ```bash
    AutoBackup
    ```
5. Or run with a custom backup configs directory:
    ```bash
    AutoBackup --configs-dir "path/to/backup_configs/"
    ```
6. Create a new backup config with the `+` button.

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

Supported schedule units: `seconds`, `minutes`, `hours`, `days`, `weeks`, `months`, `years`.

## Dashboard

The dashboard opens in a pywebview window that runs a flask webapp; it allows you to:

- View all configured backups and their status.
- Start and cancel backups manually.
- Start and stop schedulers for recurring backups.
- Create, edit, and delete backup configurations.

The application minimizes to the system tray when the window is closed. Use the tray icon to restore the window or to quit the application.

The dashboard and backup functionality are the same program, so **quitting the dashboard will cancel all backups and schedulers.**

## Google Drive Setup

To enable Google Drive uploads, you will need a `client_secrets.json` file from the Google Cloud Console in the `src/backup/` directory. The application will handle OAuth authentication and credential storage on first use.
