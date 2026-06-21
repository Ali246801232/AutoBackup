import os
import json
import shutil
import threading
from pathlib import Path
from typing import List
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from .logger import logger
from .drive import DriveHandler

class CancelledError(Exception):
    pass

_SCHEDULE_UNITS = {
    "seconds": lambda count: timedelta(seconds=count),
    "minutes": lambda count: timedelta(minutes=count),
    "hours": lambda count: timedelta(hours=count),
    "days": lambda count: timedelta(days=count),
    "weeks": lambda count: timedelta(weeks=count),
    "months": lambda count: relativedelta(months=count),
    "years": lambda count: relativedelta(years=count),
}

def _schedule_to_timedelta(schedule: dict) -> timedelta|relativedelta:
    return _SCHEDULE_UNITS[schedule["unit"]](schedule["count"])

class Backup:
    def __init__(
        self,
        config_name: str,
        sources: List[str|Path],
        destination: str|Path,
        exclusions: List[str|Path] = None,
        schedule: dict|None = None,
        drive_upload: bool = False,
        drive_folder_id = None,
        last_scheduled_attempt: datetime|None = None,
    ):
        # Backup configuration
        self.config_name: str = config_name
        self.sources: List[Path] = [Path(source).resolve() for source in sources]
        self.destination: Path = Path(destination).resolve()
        self.exclusions: List[Path] = [Path(exclusion).resolve() for exclusion in (exclusions or [])]
        self.schedule: dict|None = schedule
        self.drive_upload: bool = drive_upload
        self.drive_folder_id = drive_folder_id

        # Drive handler
        self.drive_handler: DriveHandler = None
        
        # Backup thread
        self._backup_thread: threading.Thread|None = None
        self._backup_result: dict|None = None
        self._backup_error: Exception|None = None
        self._cancel_backup_event: threading.Event = threading.Event()
        self._progress_message: str|None = None
        self._progress_percent: float|None = None

        # Scheduler thread
        self._scheduler_thread: threading.Thread|None = None
        self._scheduler_error: Exception|None = None
        self._stop_scheduler_event: threading.Event = threading.Event()
        self.last_scheduled_attempt: datetime|None = last_scheduled_attempt

        # Externally exposed state
        self.backup_started_event = threading.Event()
        self.backup_error_event = threading.Event()
        self.scheduler_started_event = threading.Event()
        self.scheduler_error_event = threading.Event()
        self.scheduler_running: bool = False

        # Thread locking
        self._backup_thread_lock = threading.Lock()
        self._manual_backup_ongoing = False
        self._scheduled_backup_ongoing = False


    def to_dict(self) -> dict:
        return {
            "config_name": str(self.config_name),
            "sources": [str(p.absolute()) for p in self.sources],
            "destination": str(self.destination.absolute()),
            "exclusions": [str(p.absolute()) for p in self.exclusions] if self.exclusions else [],
            "schedule": self.schedule,
            "drive_upload": self.drive_upload,
            "drive_folder_id": self.drive_folder_id,
            "last_scheduled_attempt": self.last_scheduled_attempt.isoformat() if self.last_scheduled_attempt else None,
        }

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            config_name = data["config_name"],
            sources = [Path(p).resolve() for p in data["sources"]],
            destination = Path(data["destination"]).resolve(),
            exclusions = [Path(p).resolve() for p in data.get("exclusions", [])],
            schedule = data.get("schedule"),
            drive_upload = data.get("drive_upload", False),
            drive_folder_id = data.get("drive_folder_id"),
            last_scheduled_attempt = datetime.fromisoformat(data["last_scheduled_attempt"]) if data.get("last_scheduled_attempt") else None
        )

    def to_json(self, file_path: str|Path):
        """Save the backup configuration of this instance to a JSON file."""
        logger.info(f"[BACKUP] Attempting to save backup details to {file_path}")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=4)
        logger.info(f"[BACKUP] Saved backup details to {file_path}")

    @classmethod
    def from_json(cls, file_path: str|Path) -> Backup:
        """Return a Backup instance loaded from a backup configuration from a JSON file."""
        logger.info(f"[BACKUP] Attempting to load backup details from {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        instance = cls.from_dict(data)
        logger.info(f"[BACKUP] Loaded backup details from {file_path}")
        return instance

    def update_from_dict(self, data: dict):
        """Update backup configuration"""
        if self.backup_running:
            raise ValueError("Cannot edit a backup's config while it is ongoing.")

        try:
            config_name = data["config_name"]
            sources = [Path(p).resolve() for p in data["sources"]]
            destination = Path(data["destination"]).resolve()
            exclusions = [Path(p).resolve() for p in data.get("exclusions", [])]
            schedule = data.get("schedule")
            drive_upload = data.get("drive_upload", False)
            drive_folder_id = data.get("drive_folder_id")
            last_scheduled_attempt = datetime.fromisoformat(data["last_scheduled_attempt"]) if data.get("last_scheduled_attempt") else None
        except KeyError as e:
            raise ValueError(f"Config missing required key: {e}") from e

        self.config_name = config_name
        self.sources = sources
        self.destination = destination
        self.exclusions = exclusions
        self.schedule = schedule
        self.drive_upload = drive_upload
        self.drive_folder_id = drive_folder_id
        self.last_scheduled_attempt = last_scheduled_attempt


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
        logger.debug("[BACKUP] Attempting to fetch effective sources")
        sources = self._flatten_paths(self.sources)
        exclusions = self._flatten_paths(self.exclusions)
        effective_sources = [source for source in sources if source not in exclusions]
        logger.debug(f"[BACKUP] Fetched effective sources: {[str(source.absolute()) for source in effective_sources]}")
        return effective_sources

    @property
    def size_bytes(self) -> int:
        """Calculate and return the size of the backup by summing the sizes of all effective sources."""
        logger.debug("[BACKUP] Attempting to calculate backup size")
        size_bytes = sum(path.stat().st_size for path in self.effective_sources)
        logger.debug(f"[BACKUP] Calculated backup file size: {size_bytes} B")
        return size_bytes

    @property
    def next_backup(self):
        """Return the datetime of the next scheduled backup if a schedule is set."""
        if self.schedule is None:
            return None
        if self.last_scheduled_attempt is None:
            return datetime.now()
        return self.last_scheduled_attempt + _schedule_to_timedelta(self.schedule)

    @property
    def backup_running(self):
        """Return whether there is a backup ongoing"""
        return self._scheduled_backup_ongoing or self._manual_backup_ongoing

    @property
    def backup_progress(self) -> dict|None:
        """Return the progress of the ongoing backup as a dict = {"message": str, "percent": float}"""
        if not self.backup_running:
            return None
        progress = {}
        if self._progress_message is not None:
            progress["message"] = self._progress_message
        if self._progress_percent is not None:
            progress["percent"] = self._progress_percent
        return progress

    @property
    def status(self) -> dict:
        """Return a dictionary of class status attributes"""
        return {
            "backup_running": self.backup_running,
            "backup_error": self.backup_error_event.is_set(),
            "scheduler_running": self.scheduler_running,
            "scheduler_error": self.scheduler_error_event.is_set(),
            "backup_progress": self.backup_progress
        }


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

        total = len(sources)

        for count, (source, destination_path) in enumerate(zip(sources, destination_paths)):
            if self._cancel_backup_event.is_set():
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
                elif source.is_dir():
                    shutil.copytree(source, destination_path)
                logger.debug(f"[BACKUP] Copied source {source} to {destination_path}")
            except CancelledError as e:
                logger.info(f"[BACKUP] {e}")
                raise
            except Exception as e:
                logger.error(f"[BACKUP] Failed to copy source {source}: {e}")
            
            self._progress_percent = (count+1) / total


    def verify_details(self):
        """Verify that the details of the backup are valid; raise an error if not."""
        errors = []

        if not self.config_name:
            errors.append("Backup has no configuration name set.")
        elif not isinstance(self.config_name, str):
            errors.append("Backup configuration name is not a string")

        if not self.sources:
            errors.append("Backup has no sources set.")
        elif not (isinstance(self.sources, list) and all(isinstance(source, Path) for source in self.sources)):
            errors.append("Backup sources is not a list of paths")
        else:
            missing_sources = [str(s.absolute()) for s in self.sources if not s.exists()]
            if missing_sources:
                errors.append(f"The following backup sources do not exist: {missing_sources}")

        if not self.destination:
            errors.append("Backup has no destination set.")
        elif not self.destination.exists():
            errors.append(f"Backup destination {self.destination.absolute()} does not exist.")

        if self.schedule is not None:
            if not isinstance(self.schedule, dict):
                errors.append("Backup schedule is not a dictionary in the form {\"count\": int, \"unit\": str}")
            else:
                count = self.schedule.get("count")
                unit = self.schedule.get("unit")
                if not (isinstance(count, int) and isinstance(unit, str)):
                    errors.append("Backup schedule is not a dictionary in the form {\"count\": int, \"unit\": str}")
                else:
                    if count < 1:
                        errors.append("Backup schedule count must be positive")
                    if _SCHEDULE_UNITS.get(unit) is None:
                        errors.append(f"Backup schedule unit is not one of {list(_SCHEDULE_UNITS.keys())}")

        if self.destination:
            try:
                free_space = shutil.disk_usage(self.destination).free
                if self.size_bytes > free_space:
                    errors.append(f"Backup destination at {self.destination} does not have enough space to store backup.")
            except OSError:
                errors.append(f"Cannot determine disk usage for destination {self.destination}.")

        if self.drive_upload and not (self.drive_folder_id and isinstance(self.drive_folder_id, str)):
            errors.append("Backup does not have a Drive folder to upload to.")

        if errors:
            raise ValueError("\n".join(errors))


    def create_backup(self) -> dict:
        """User the backup details to create a backup."""
        if self._cancel_backup_event.is_set():
            raise CancelledError("Backup was cancelled")

        # Verify backup details
        self._progress_message = "Verifying backup details"
        self._progress_percent = None
        logger.info("[BACKUP] Verifying backup details")
        try:
            self.verify_details()
            logger.info("[BACKUP] Verified backup details")
        except Exception as e:
            raise RuntimeError(f"Failed to verify backup details: {e}") from e

        if self._cancel_backup_event.is_set():
            raise CancelledError("Backup was cancelled")

        # Create local backup
        self._progress_message = "Creating local backup (0%)"
        self._progress_percent = 0.0
        logger.info("[BACKUP] Attempting to create local backup")
        try:
            backup_folder = self.destination / f"{self.config_name}_{datetime.now():%Y-%m-%d_%H-%M-%S}"
            self.copy_items(self.effective_sources, backup_folder)
            logger.info(f"[BACKUP] Created local backup: {backup_folder}")
        except Exception as e:
            raise RuntimeError(f"Failed to create local backup: {e}") from e

        if self._cancel_backup_event.is_set():
            raise CancelledError("Backup was cancelled")

        # Upload backup to Drive
        if self.drive_upload:
            self._progress_message = "Uploading backup to Google Drive"
            self._progress_percent = 0.0
            logger.info("[BACKUP] Attempting to upload backup to Google Drive")
            try:
                self.drive_handler = DriveHandler()
                self.drive_handler._cancel_folder_upload_event = self._cancel_backup_event
                self.drive_handler.authenticate()
                self.drive_handler._folder_upload_progress_callback = lambda current, total: setattr(self, "_progress_percent", current / total)
                self.drive_handler.start_folder_upload(backup_folder, self.drive_folder_id)
                drive_backup_folder_id = self.drive_handler.wait_for_folder_upload()
                logger.info(f"[BACKUP] Uploaded backup to Google Drive: https://drive.google.com/drive/folders/{drive_backup_folder_id}")
            except Exception as e:
                raise RuntimeError(f"Failed to upload backup to Google Drive: {e}") from e
        else:
            drive_backup_folder_id = None

        self._progress_message = None
        self._progress_percent = None
        
        backup_result = {
            "backup_folder": backup_folder,
            "drive_backup_folder_id": drive_backup_folder_id
        }

        return backup_result

    def start_backup(self, scheduled: bool = False):
        """Start a backup in a thread."""
        with self._backup_thread_lock:
            if self._scheduled_backup_ongoing:
                raise RuntimeError("Scheduled backup is currently ongoing.")
            if self._manual_backup_ongoing:
                raise RuntimeError("Manual backup is currently ongoing.")
            if self._backup_thread and self._backup_thread.is_alive():
                raise RuntimeError("A backup is ongoing.")

            self._cancel_backup_event.clear()
            self._backup_result = None
            self._backup_error = None

            def runner():
                try:
                    if scheduled: self.last_scheduled_attempt = datetime.now()
                    self._backup_result = self.create_backup()
                except Exception as e:
                    self.backup_error_event.set()
                    self._backup_error = e
                finally:
                    if scheduled: self._scheduled_backup_ongoing = False
                    else: self._manual_backup_ongoing = False
                    self.backup_started_event.clear()

            if scheduled: self._scheduled_backup_ongoing = True
            else: self._manual_backup_ongoing = True
            self.backup_started_event.set()
            self.backup_error_event.clear()

            self._backup_thread = threading.Thread(target=runner, daemon=True)
            self._backup_thread.start()
    
    def cancel_backup(self, undo: bool = False):
        """Cancel an ongoing thread backup, optionally undo it."""
        if self._backup_thread and self._backup_thread.is_alive():
            self._cancel_backup_event.set()

            if self.drive_handler:
                self.drive_handler.cancel_folder_upload(undo=undo)

            self._backup_thread.join()

            if self._backup_result:
                backup_folder = self._backup_result.get("backup_folder")
                if undo and backup_folder and backup_folder.exists():
                    shutil.rmtree(backup_folder)
            
            if self._backup_error and not isinstance(self._backup_error, CancelledError):
                raise self._backup_error

    def wait_for_backup(self) -> dict:
        """Wait for the result of the ongoing thread backup."""
        if self._backup_thread and self._backup_thread.is_alive():
            self._backup_thread.join()

        if self._backup_error and not isinstance(self._backup_error, CancelledError):
            raise self._backup_error

        if self.drive_handler:
            self.drive_handler.wait_for_folder_upload()
        
        return self._backup_result


    def run_scheduler(self):
        """Indefinitely wait for and create scheduled backups."""
        logger.info(f"[BACKUP] Started scheduler")

        while not self._stop_scheduler_event.is_set():
            # No schedule configured
            if self.next_backup is None:
                break
                
            # Wait until the next scheduled backup
            logger.info(f"[BACKUP] Waiting until the next backup: {self.next_backup}")
            timeout = max(0.0, (self.next_backup - datetime.now()).total_seconds())
            if self._stop_scheduler_event.wait(timeout):
                break

            # Wait for a manual backup if ongoing
            if self._manual_backup_ongoing:
                try:
                    self.wait_for_backup()
                except Exception:
                    pass

            # Start the scheduled backup on a thread
            logger.info(f"[BACKUP] Starting scheduled backup")
            try:
                self.start_backup(scheduled=True)
                backup_folder = self.wait_for_backup()
                logger.info(f"[BACKUP] Created scheduled backup: {backup_folder}")
            except Exception as e:
                logger.info(f"[BACKUP] Scheduled backup errored: {e}")

        logger.info(f"[BACKUP] Stopped scheduler")


    def start_scheduler(self):
        """Start a scheduler in a thread."""
        if self.schedule is None:
            return        
        if self._manual_backup_ongoing:
            raise RuntimeError("Manual backup is currently running.")
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            raise RuntimeError("Scheduler is already running, restart with .restart_scheduler()")

        self._stop_scheduler_event.clear()
        self._scheduler_error = None

        def runner():
            try:
                self.run_scheduler()
            except Exception as e:
                self.scheduler_error_event.set()
                self._scheduler_error = e
            finally:
                self.scheduler_running = False
                self.scheduler_started_event.clear()

        self.scheduler_running = True
        self.scheduler_started_event.set()
        self.scheduler_error_event.clear()

        self._scheduler_thread = threading.Thread(target=runner, daemon=True)
        self._scheduler_thread.start()

    def stop_scheduler(self):
        """Stop the thread scheduler, cancel ongoing scheduled backup."""
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            self._stop_scheduler_event.set()

            if self._scheduled_backup_ongoing:
                self.cancel_backup()

            self._scheduler_thread.join()
            
            if self._scheduler_error:
                raise self._scheduler_error

    def wait_for_scheduler(self):
        """Wait until the scheduler stops, in case .stop_scheduler() call expected elsewhere."""
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            self._scheduler_thread.join()

        if self._scheduler_error:
            raise self._scheduler_error