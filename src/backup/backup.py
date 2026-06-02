import os
import json
import shutil
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

from .logger import logger
from .drive import DriveHandler

class CancelledError(Exception):
    pass

class Backup:
    def __init__(
        self,
        sources: List[str|Path],
        destination: str|Path,
        exclusions: List[str|Path] = None,
        schedule: timedelta|None = None,
        drive_upload: bool = False,
        drive_folder_id = None,
        last_backup: datetime|None = None,
        cancel_event = None
    ):
        # Backup config
        self.sources: List[Path] = [Path(source).resolve() for source in sources]
        self.destination: Path = Path(destination).resolve()
        self.exclusions: List[Path] = [Path(exclusion).resolve() for exclusion in (exclusions or [])]
        self.schedule: timedelta|None = schedule
        self.drive_upload: bool = drive_upload
        self.drive_folder_id = drive_folder_id
        self.last_backup = last_backup

        # Cache for properties
        self._size_bytes: int | None = None
        self._effective_sources: List[Path] | None = None

        # Drive handler
        self.drive_handler: DriveHandler = None
        
        # Thread stuff
        self._backup_folder = None
        self._backup_error = None
        self._backup_thread = None
        self._cancel_event = cancel_event if cancel_event is not None else threading.Event()


    def _flatten_paths(self, paths: List[Path]) -> List[Path]:
        """Flatten and return a list of paths as only files and empty directories."""
        flattened = set()
        for path in paths:
            if path.is_symlink():  # ignore symlinks
                continue
            elif path.is_file():  # add files as is
                flattened.add(path)
            elif path.is_dir():
                children = list(path.iterdir())
                if not children:  # add empty directories as is
                    flattened.add(path)
                else:  # recursively flatten and add non-empty directories
                    flattened.update(self._flatten_paths(children))
        return list(flattened)
    
    @property
    def effective_sources(self) -> List[Path]:
        """Return the list of sources flattened and with exclusions removed."""
        logger.debug("[BACKUP] Attempting to fetch effecting sources")
        if self._effective_sources is None:
            sources = self._flatten_paths(self.sources)
            exclusions = self._flatten_paths(self.exclusions)
            self._effective_sources = [source for source in sources if source not in exclusions]
        logger.debug(f"[BACKUP] Fetched effective sources: {self._effective_sources}")
        return self._effective_sources

    @property
    def size_bytes(self) -> int:
        """Calculate and return the size of the backup by summing the sizes of all effective sources."""
        logger.debug("[BACKUP] Attempting to calculate backup size")
        if self._size_bytes is None:
            self._size_bytes = sum(path.stat().st_size for path in self.effective_sources)
        logger.debug(f"[BACKUP] Calculated backup file size: {self._size_bytes} B")
        return self._size_bytes

    def verify_details(self):
        """Verify that the details of the backup are valid; raise an error if not."""
        if not self.sources:
            raise ValueError("Backup has no sources.")
        
        if not self.destination:
            raise ValueError("Backup has no destination.")

        for source in self.sources:
            if not source.exists():
                raise FileNotFoundError(f"Source at {source.absolute()} does not exist.")
        
        for exclusion in self.exclusions:
            if not exclusion.exists():
                raise FileNotFoundError(f"Exclusion at {exclusion.absolute()} does not exist.")
        
        free_space = shutil.disk_usage(self.destination).free
        if self.size_bytes > free_space:
            raise ValueError(f"Destination at {self.destination} does not have enough space to store backup.")

        if self.drive_upload and not self.drive_folder_id:
            raise ValueError(f"Backup does not have a Drive folder to upload to.")

    
    def _get_destination_paths(self, sources: List[Path], destination: Path) -> List[Path]:
        """Construct and return a list of destination paths given the source paths and a destination folder."""
        if all(s.is_absolute() for s in sources) and len({s.drive for s in sources}) == 1:
            common_path = Path(os.path.commonpath([str(s) for s in sources]))
        else:  # handle drives for windows
            destination_paths = []
            for source in sources:
                if source.is_absolute():
                    relative_parts = source.relative_to(source.anchor).parts
                    if source.drive:
                        drive_letter = source.drive[0]
                        destination_parts = [f"Drive {drive_letter}"] + list(relative_parts)
                    else:
                        destination_parts = relative_parts
                else:
                    destination_parts = source.parts
                destination_paths.append(destination.joinpath(*destination_parts))
            return destination_paths

        if common_path.name == "":  # no common parent, must be Windows due to different drives
            drive_letter = common_path.drive[0]
            parent_name = f"Drive {drive_letter}"
        else:
            parent_name = common_path.name

        destination_paths = []
        for source in sources:
            rel = source.relative_to(common_path)
            if rel == Path("."):
                destination_paths.append(destination / parent_name)
            else:
                destination_paths.append(destination / parent_name / rel)

        return destination_paths

    def copy_items(self, sources: List[Path], destination: Path):
        """Copy a non-overlapping list of paths to a destination folder."""
        # Ensure destination directory exists
        destination = destination.resolve()
        destination.mkdir(parents=True, exist_ok=True)
        destination_paths = self._get_destination_paths(sources, destination)

        for source, destination_path in zip(sources, destination_paths):
            if self._cancel_event.is_set():
                raise CancelledError("Backup was cancelled")
            
            logger.debug(f"[BACKUP] Attempting to copy source {source}")
            try:
                source = source.resolve()

                # Delete any existing files at the destination path
                if destination_path.exists():
                    if destination_path.is_file():
                        destination_path.unlink()
                    elif destination_path.is_dir():
                        shutil.rmtree(destination_path)

                # Ensure destination path exists
                destination_path.parent.mkdir(parents=True, exist_ok=True)

                # Copy source
                if source.is_file():
                    shutil.copy2(source, destination_path)
                if source.is_dir():
                    shutil.copytree(source, destination_path)
                logger.debug(f"[BACKUP] Copied source {source} to {destination_path}")
            except CancelledError as e:
                logger.info(f"[BACKUP] {e}")
                raise
            except Exception as e:
                logger.error(f"[BACKUP] Failed to copy source {source}: {e}")


    def create_backup(self):
        """User the backup details to create a backup."""
        if self._cancel_event.is_set():
            raise CancelledError("Backup was cancelled")

        logger.info("[BACKUP] Verifying backup details")
        try:
            self.verify_details()
            logger.info("[BACKUP] Verified backup details")
        except Exception as e:
            raise RuntimeError(f"Failed to verify backup details: {e}") from e

        if self._cancel_event.is_set():
            raise CancelledError("Backup was cancelled")

        logger.info("[BACKUP] Attempting to create local backup")
        try:
            self._backup_folder = self.destination / f"Backup_{datetime.now():%Y-%m-%d_%H-%M-%S}"
            self.copy_items(self.effective_sources, self._backup_folder)
            logger.info(f"[BACKUP] Created local backup: {self._backup_folder}")
        except Exception as e:
            raise RuntimeError(f"Failed to create local backup: {e}") from e

        if self._cancel_event.is_set():
            raise CancelledError("Backup was cancelled")

        if self.drive_upload:
            logger.info("[BACKUP] Attempting to upload backup to Google Drive")
            try:
                self.drive_handler = DriveHandler(cancel_event=self._cancel_event)
                self.drive_handler.start_folder_upload(self._backup_folder, self.drive_folder_id)
                drive_backup_folder_id = self.drive_handler.wait_for_folder_upload()
                logger.info(f"[BACKUP] Uploaded backup to Google Drive: https://drive.google.com/drive/folders/{drive_backup_folder_id}")
            except Exception as e:
                raise RuntimeError(f"Failed to upload backup to Google Drive: {e}") from e


    def start_backup(self):
        """Start creating a backup."""
        self._cancel_event.clear()

        if self._backup_thread and self._backup_thread.is_alive():
            raise RuntimeError("There is an ongoing backup, cancel it with .cancel() to start another")

        self._backup_folder = None
        self._backup_error = None

        def runner():
            try:
                self.create_backup()
            except Exception as e:
                self._backup_error = e
            self._size_bytes = None
            self._effective_sources = None

        self._backup_thread = threading.Thread(target=runner, daemon=True)
        self._backup_thread.start()
    
    def cancel_backup(self, undo: bool = False):
        """Cancel an ongoing backup, optionally undo it."""
        if self._backup_thread and self._backup_thread.is_alive():
            self._cancel_event.set()

            if self.drive_handler:
                self.drive_handler.cancel_folder_upload(undo=undo)

            self._backup_thread.join()

            if undo and self._backup_folder and self._backup_folder.exists():
                shutil.rmtree(self._backup_folder)

    def wait_for_backup(self):
        if self._backup_thread:
            self._backup_thread.join()

        if self._backup_error:
            raise self._backup_error

        if self.drive_handler:
            self.drive_handler.wait_for_folder_upload()


    def to_json(self, file_path: str | Path):
        """Save the backup configuration of this instance to a JSON file."""
        logger.info(f"[BACKUP] Attempting to save backup details to {file_path}")
        data = {
            "sources": [str(p.absolute()) for p in self.sources],
            "destination": str(self.destination),
            "exclusions": [str(p.absolute()) for p in self.exclusions] if self.exclusions else [],
            "schedule": self.schedule.total_seconds() if self.schedule else None,
            "drive_upload": self.drive_upload,
            "drive_folder_id": self.drive_folder_id,
            "last_backup": self.last_backup.isoformat() if self.last_backup else None,
        }
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        logger.info(f"[BACKUP] Saved backup details to {file_path}")

    @classmethod
    def from_json(cls, file_path: str | Path) -> Backup:
        """Load a backup configuration from a JSON file and update this instance."""
        logger.info(f"[BACKUP] Attempting to load backup details from {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        instance = cls(
            sources = [Path(p).resolve() for p in data["sources"]],
            destination = Path(data["destination"]).resolve(),
            exclusions = [Path(p).resolve() for p in data.get("exclusions", [])],
            schedule = timedelta(seconds=data["schedule"]) if data.get("schedule") else None,
            drive_upload = data.get("drive_upload", False),
            drive_folder_id = data.get("drive_folder_id"),
            last_backup = datetime.fromisoformat(data["last_backup"]) if data.get("last_backup") else None
        )
        logger.info(f"[BACKUP] Loaded backup details from {file_path}")
        return instance
