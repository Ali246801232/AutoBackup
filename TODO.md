## Startup functionality

- Upon startup, we run a script with a number of `"{app.PYTHON_EXECUTABLE}" -m AutoBackup --configs-dir "{app.BACKUP_CONFIGS_DIR}" --start-minimized --start-schedulers` commands to start the app and its schedulers.
- To add a backup configs dir to start, you run the app manually with that configs dir (`AutoBackup --configs-dir "whatever/configs/dir"`) and then add it to startup from there.
- So if the user wants to have multiple configs dirs, to add them to startup, launch the app multiple times with each configs dirs, and then add to startup from each.

`src/startup/`:
- Adds the right type script to the right place depending on the platform; planning to support Windows, Linux, macOS.
- Allows registering and unregistering of a configs dir to startup by modifying the script, and checking the script for if a configs dir already registered.

`src/dashboard/`:
- Replace the theme button with a hamburger button that opens a dropdown with the theme button and a button to open the startup modal.
- Startup modal shows whether the configs dir is added to startup and has a button that switches between "Add to Startup" and "Remove from Startup" depending on status.
- Status and buttons use the API cals in `app.py`: `/api/startup/status`, `/api/startup/add`, `api/startup/remove`.
- Add a little hint to the left of the hamburger button in monospace in the sticky header showing the current backup configs dir.