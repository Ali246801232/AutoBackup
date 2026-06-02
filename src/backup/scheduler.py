import json
import threading
from pathlib import Path
from datetime import datetime

from .backup import Backup
from .logger import logger

class Scheduler:
    """Scheduler to repeatedly perform a Backup as per its schedule."""

    def __init__(self, config_path: str|Path, output_path: str|Path):
        self.config_path = Path(config_path)
        self.output_path = Path(output_path)

        self._stop_event = threading.Event()
        self._thread = None
        self.backup = self._load_backup()
        self._write_status("initialized")

    def _load_backup(self) -> Backup:
        """Load backup from configuration file."""
        backup = Backup.from_json(self.config_path)
        backup._cancel_event = self._stop_event
        logger.info(f"[SCHEDULER] Loaded backup {self.config_path}")
        return backup

    def _write_status(
        self,
        state: str,
        next_run: datetime | None = None,
        last_error: Exception | None = None,
    ):
        """Write current scheduler state to a status JSON file."""
        status = {
            "state": state,
            "config_path": str(self.config_path),
            "last_backup": self.backup.last_backup.isoformat() if self.backup.last_backup else None,
            "next_run": next_run.isoformat() if next_run else None,
            "schedule_seconds": self.backup.schedule.total_seconds() if self.backup.schedule else None,
            "last_error": str(last_error) if last_error else None,
            "updated_at": datetime.now().isoformat(),
        }

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_path, "w", encoding="utf-8") as status_file:
            json.dump(status, status_file, indent=4)

    def _calculate_next_run(self) -> datetime:
        """Return the next scheduled run time for the configured backup."""
        if self.backup.schedule is None:
            raise ValueError("Backup schedule is not configured")

        if self.backup.last_backup is None:
            return datetime.now()

        return self.backup.last_backup + self.backup.schedule

    def _wait_until(self, target_time: datetime) -> bool:
        """Wait until a target datetime or until stop is requested."""
        timeout = max(0.0, (target_time - datetime.now()).total_seconds())
        if timeout == 0.0:
            return False

        self._stop_event.wait(timeout)
        return self._stop_event.is_set()

    def _run(self):
        """Main scheduler loop that waits and executes backups."""
        while not self._stop_event.is_set():
            self.backup = self._load_backup()
            if self.backup.schedule is None:
                self._write_status("disabled")
                break

            next_run = self._calculate_next_run()
            self._write_status("waiting", next_run=next_run)

            if self._wait_until(next_run):
                break

            if self._stop_event.is_set():
                break

            self._write_status("running", next_run=next_run)
            try:
                self.backup.last_backup = datetime.now()
                self.backup.create_backup()
                self.backup.to_json(self.config_path)
                self._write_status("idle")
            except Exception as error:
                self._write_status("error", next_run=next_run, last_error=error)

        self._write_status("stopped")

    def start(self):
        """Start scheduler execution in a background thread."""
        if self._thread and self._thread.is_alive():
            raise RuntimeError("Scheduler is already running")
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._write_status("started")
        logger.info(f"[SCHEDULER] Started scheduler {self.output_path}")

    def stop(self):
        """Request scheduler stop and wait for the thread to finish."""
        self._stop_event.set()
        if self._thread:
            self._thread.join()
        self._write_status("stopped")
        logger.info(f"[SCHEDULER] Stopped scheduler {self.output_path}")


    def restart(self):
        """Restart the scheduler by stopping it first then starting again."""
        self.stop()
        self.start()
