import threading
from pathlib import Path
from pydrive2.auth import GoogleAuth, RefreshError
from pydrive2.drive import GoogleDrive
from pydrive2.files import ApiRequestError

from .logger import logger

class CancelledError(Exception):
    pass

class DriveHandler:
    def __init__(self):
        try:
            self._authenticate()
        except Exception as e:
            raise RuntimeError(f"Failed to authenticate and authorize with Google Drive: {e}") from e

        self.open_folder("root")
        
        self._folder_upload_root_id = None
        self._folder_upload_error = None
        self._folder_upload_thread = None
        self._cancel_folder_upload_event = threading.Event()
        self._folder_upload_progress_callback = None

        
    def _authenticate(self):
        """Authenticate using saved credentials, otherwise with local web server."""
        self.script_dir = Path(__file__).parent.resolve()
        client_config_file = self.script_dir / "client_secrets.json"
        credentials_file = self.script_dir / "credentials.json"

        self.gauth = GoogleAuth(settings={
            "client_config_backup": "file",
            "client_config_file": str(client_config_file),
            "save_credentials": True,
            "save_credentials_backend": "file",
            "save_credentials_file": str(credentials_file),
            "get_refresh_token": True,
        })

        if not client_config_file.exists():
            raise RuntimeError("No client_secrets.json found in script directory")        

        if credentials_file.exists():
            self.gauth.LoadCredentialsFile()
        
        # Attempt to authorize
        if self.gauth.access_token_expired:
            try:
                self.gauth.Refresh()
            except RefreshError:  # LocalWebserverAuth() calls Refresh() if save_credentials is True so I have to resort to this buffoonery
                self.gauth.credentials = None
                save_credentials = self.gauth.settings.get("save_credentials")
                try:
                    self.gauth.settings["save_credentials"] = False
                    self.gauth.LocalWebserverAuth()
                finally:
                    self.gauth.settings["save_credentials"] = save_credentials
        else:
            self.gauth.Authorize()

        self.gauth.SaveCredentialsFile()

        self.drive = GoogleDrive(self.gauth)


    def open_folder(self, folder_id: str):
        """Go to a Drive folder with a given ID, and return the folder"""
        self.current_folder = self.drive.CreateFile({"id": folder_id})
        self.current_folder.FetchMetadata()
        logger.info(f"[DRIVE] Opened folder {folder_id}")
        return self.current_folder

    def go_up(self):
        """Go to the parent of the current Drive folder, and return the folder."""
        parents = self.current_folder["parents"]
        if parents != []:
            self.open_folder(parents[0]["id"])
        return self.current_folder

    def go_to_root(self):
        """Go to the root Drive folder, and return the folder."""
        return self.open_folder("root")


    def get_children(self, folder_id: str | None = None, query: str = ""):
        """Return all items in a Drive folder, filtered by an optional query."""
        if folder_id is None:
            folder_id = self.current_folder["id"]

        if query != "":
            query = f" and ({query})"

        try:
            children = self.drive.ListFile({"q": (
                f"'{folder_id}' in parents"
                " and trashed = false"
                f"{query}"
            )}).GetList()
        except ApiRequestError as e:
            raise RuntimeError(f"Failed to fetch children ({folder_id}): {e}") from e

        children.sort(key=lambda x: x.get("title", "").lower())

        logger.info(f"[DRIVE] Fetched children for {folder_id}")
        return children

    def get_child_folders(self, folder_id: str | None = None):
        """Return all subfolders in a Drive folder."""
        return self.get_children(
            folder_id,
            query="mimeType = 'application/vnd.google-apps.folder'"
        )

    def get_child_files(self, folder_id: str | None = None):
        """Return all files in a Drive folder."""
        return self.get_children(
            folder_id,
            query="mimeType != 'application/vnd.google-apps.folder'"
        )

    def get_item(self, item_id: str):
        """Return a given Drive item by ID"""
        item = self.drive.CreateFile({"id": item_id})
        item.FetchMetadata()
        return item


    def upload_file(self, file_path: str | Path, drive_parent_id: str):
        """Upload a local file to a Drive folder."""
        file_path = Path(file_path)
        if not file_path.is_file():
            raise ValueError(f"Path is not a file: ({file_path})")
        if not file_path.exists():
            raise ValueError(f"Path does not exist ({file_path})")

        try:
            file = self.drive.CreateFile(metadata={"parents": [{"id": drive_parent_id}]})
            file.SetContentFile(file_path)
            file.Upload()
        except ApiRequestError as e:
            raise RuntimeError(f"Failed to upload file ({file_path}): {e}") from e

        return file["id"]


    @staticmethod
    def _count_items(path: Path) -> int:
        """Recursively count all files and subdirectories under a path."""
        count = 0
        for item in path.iterdir():
            count += 1
            if item.is_dir():
                count += DriveHandler._count_items(item)
        return count

    def upload_folder(self, folder_path: str | Path, drive_parent_id: str, is_root: bool = True):
        """Upload a local folder to a Drive folder."""
        folder_path = Path(folder_path)
        if not folder_path.exists():
            raise ValueError(f"Path does not exist ({folder_path})")
        if not folder_path.is_dir():
            raise ValueError(f"Path is not a directory ({folder_path})")

        if is_root:
            self._total_folder_upload_items = DriveHandler._count_items(folder_path)
            self._completed_folder_upload_items = 0

        try:
            drive_folder = self.drive.CreateFile(metadata={
                "title": folder_path.name,
                "parents": [{"id": drive_parent_id}],
                "mimeType": "application/vnd.google-apps.folder",
            })
            drive_folder.Upload()
            if is_root:
                self._folder_upload_root_id = drive_folder["id"]
        except ApiRequestError as e:
            logger.error(f"[DRIVE] Failed to upload item {folder_path.name}: {e}")
            if is_root:
                raise RuntimeError(f"Failed to create folder ({folder_path}): {e}") from e
            return None

        if self._cancel_folder_upload_event.is_set():
            raise CancelledError("Drive folder upload was cancelled")

        for item in folder_path.iterdir():
            if self._cancel_folder_upload_event.is_set():
                raise CancelledError("Drive folder upload was cancelled")
            try:
                if item.is_dir():
                    self.upload_folder(item, drive_folder["id"], is_root=False)
                elif item.is_file():
                    self.upload_file(item, drive_folder["id"])
                logger.debug(f"[DRIVE] Uploaded item {item.absolute()}")
            except CancelledError as e:
                logger.info(f"[DRIVE] {e}")
                raise
            except Exception as e:
                logger.error(f"[DRIVE] Failed to upload item {item.absolute()}: {e}")

            self._completed_folder_upload_items += 1
            if self._folder_upload_progress_callback and self._total_folder_upload_items > 0:
                self._folder_upload_progress_callback(self._completed_folder_upload_items, self._total_folder_upload_items)

        return drive_folder["id"]


    def trash_item(self, item_id):
        try:
            item = self.drive.CreateFile({'id': item_id})
            item.Trash()
        except Exception as e:
            raise RuntimeError(f"Failed to trash item {item_id}: {e}") from e

    def delete_item(self, item_id):
        try:
            item = self.drive.CreateFile({'id': item_id})
            item.Delete()
        except Exception as e:
            raise RuntimeError(f"Failed to permanently delete item {item_id}: {e}") from e


    def start_folder_upload(self, folder_path, drive_parent_id):
        if self._folder_upload_thread and self._folder_upload_thread.is_alive():
            raise RuntimeError("There is an ongoing folder upload, cancel it with .cancel_folder_upload() to start another")

        self._cancel_folder_upload_event.clear()
        self._folder_upload_root_id = None
        self._folder_upload_error = None

        def runner():
            try:
                self._folder_upload_root_id = self.upload_folder(folder_path, drive_parent_id)
            except Exception as e:
                self._folder_upload_error = e

        self._folder_upload_thread = threading.Thread(target=runner, daemon=True)
        self._folder_upload_thread.start()

    def cancel_folder_upload(self, undo: bool = False):
        """Cancel an ongoing Drive folder upload, optionally undo it."""
        if self._folder_upload_thread and self._folder_upload_thread.is_alive():
            self._cancel_folder_upload_event.set()
            self._folder_upload_thread.join()

            if undo and self._folder_upload_root_id:
                self.delete_item(self._folder_upload_root_id)
            
            if self._folder_upload_error and not isinstance(self._folder_upload_error, CancelledError):
                raise self._folder_upload_error

    def wait_for_folder_upload(self):
        if self._folder_upload_thread:
            self._folder_upload_thread.join()

        if self._folder_upload_error and not isinstance(self._folder_upload_error, CancelledError):
            raise self._folder_upload_error

        return self._folder_upload_root_id
