## Startup functionality

So that the scheduling actually has a point.

`src/startup/`:
- Add script to run `"{app.PYTHON_EXECUTABLE}" -m AutoBackup --configs-dir "{app.BACKUP_CONFIGS_DIR}" --start-minimized --start-schedulers` at device startup.
- Maybe add a delay of like 5 minutes before starting idk.
- Probably one script that we add/remove the commands for each config dir to.

`src/dashboard/`:
- Add a little modal and way to access model that has a add/remove from startup button and shows whether currently added to startup; connects with the API cals added to `app.py`.
- As `app.py` implements, we just use the configs path that the app itself was launched with. If the user wants to have multiple config paths for whatever reason, they can I guess; just launch the app multiple times with different config dirs, and then add to startup from each.
- Add a little hint in monospace in the sticky header showing the current backup configs dir.