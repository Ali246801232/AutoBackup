import json
import time
import threading
from pathlib import Path
from datetime import datetime, timedelta

import pytest
from backup import Backup
from backup.backup import CancelledError


class TestInit:
    def test_defaults(self, tmp_source_dir, tmp_dest_dir):
        b = Backup("my_backup", [tmp_source_dir], tmp_dest_dir)
        assert b.config_name == "my_backup"
        assert b.sources == [tmp_source_dir.resolve()]
        assert b.destination == tmp_dest_dir.resolve()
        assert b.exclusions == []
        assert b.schedule is None
        assert b.drive_upload is False
        assert b.drive_folder_id is None
        assert b.drive_handler is None

    def test_with_schedule(self, tmp_source_dir, tmp_dest_dir):
        b = Backup("sched", [tmp_source_dir], tmp_dest_dir, schedule={"count": 2, "unit": "hours"})
        assert b.schedule == {"count": 2, "unit": "hours"}

    def test_with_exclusions(self, tmp_source_dir, tmp_dest_dir):
        excl = [tmp_source_dir / "file1.txt"]
        b = Backup("excl", [tmp_source_dir], tmp_dest_dir, exclusions=excl)
        assert len(b.exclusions) == 1
        assert b.exclusions[0] == excl[0].resolve()

    def test_with_drive(self, tmp_source_dir, tmp_dest_dir):
        b = Backup("drv", [tmp_source_dir], tmp_dest_dir, drive_upload=True, drive_folder_id="abc123")
        assert b.drive_upload is True
        assert b.drive_folder_id == "abc123"

    def test_last_scheduled_attempt(self, tmp_source_dir, tmp_dest_dir):
        dt = datetime(2025, 6, 1, 12, 0, 0)
        b = Backup("lsa", [tmp_source_dir], tmp_dest_dir, last_scheduled_attempt=dt)
        assert b.last_scheduled_attempt == dt


class TestSerialization:
    def test_to_dict(self, backup_instance):
        d = backup_instance.to_dict()
        assert d["config_name"] == "test_backup"
        assert isinstance(d["sources"], list)
        assert d["schedule"] is None
        assert d["drive_upload"] is False
        assert d["last_scheduled_attempt"] is None

    def test_to_dict_with_schedule(self, tmp_source_dir, tmp_dest_dir):
        b = Backup("s", [tmp_source_dir], tmp_dest_dir, schedule={"count": 90, "unit": "seconds"})
        d = b.to_dict()
        assert d["schedule"] == {"count": 90, "unit": "seconds"}

    def test_to_dict_with_last_attempt(self, tmp_source_dir, tmp_dest_dir):
        dt = datetime(2025, 6, 1, 12, 0, 0)
        b = Backup("s", [tmp_source_dir], tmp_dest_dir, last_scheduled_attempt=dt)
        d = b.to_dict()
        assert d["last_scheduled_attempt"] == "2025-06-01T12:00:00"

    def test_from_dict(self, backup_dict):
        b = Backup.from_dict(backup_dict)
        assert b.config_name == "test_backup"
        assert len(b.sources) == 1
        assert b.destination.name == "dest"

    def test_from_dict_with_exclusions(self, tmp_source_dir, tmp_dest_dir):
        data = {
            "config_name": "test",
            "sources": [str(tmp_source_dir)],
            "destination": str(tmp_dest_dir),
            "exclusions": [str(tmp_source_dir / "file1.txt")],
            "schedule": {"count": 60, "unit": "seconds"},
            "drive_upload": True,
            "drive_folder_id": "id123",
            "last_scheduled_attempt": "2025-06-01T12:00:00",
        }
        b = Backup.from_dict(data)
        assert b.schedule == {"count": 60, "unit": "seconds"}
        assert b.drive_upload is True
        assert b.drive_folder_id == "id123"
        assert b.last_scheduled_attempt == datetime(2025, 6, 1, 12, 0, 0)

    def test_roundtrip(self, backup_instance):
        d = backup_instance.to_dict()
        b2 = Backup.from_dict(d)
        assert b2.config_name == backup_instance.config_name
        assert b2.sources == backup_instance.sources

    def test_to_json(self, backup_instance, tmp_path):
        fp = tmp_path / "config.json"
        backup_instance.to_json(fp)
        assert fp.exists()
        data = json.loads(fp.read_text())
        assert data["config_name"] == "test_backup"

    def test_from_json(self, backup_instance, tmp_path):
        fp = tmp_path / "config.json"
        backup_instance.to_json(fp)
        b2 = Backup.from_json(fp)
        assert b2.config_name == backup_instance.config_name

    def test_json_roundtrip(self, backup_instance, tmp_path):
        fp = tmp_path / "config.json"
        backup_instance.to_json(fp)
        b2 = Backup.from_json(fp)
        assert b2.to_dict() == backup_instance.to_dict()

    def test_update_from_dict(self, backup_instance, tmp_source_dir, tmp_dest_dir):
        new_src2 = tmp_source_dir.parent / "source2"
        new_src2.mkdir(exist_ok=True)
        (new_src2 / "extra.txt").write_text("extra")
        data = {
            "config_name": "renamed",
            "sources": [str(tmp_source_dir), str(new_src2)],
            "destination": str(tmp_dest_dir),
            "exclusions": [],
            "schedule": {"count": 120, "unit": "seconds"},
            "drive_upload": True,
            "drive_folder_id": "new_id",
            "last_scheduled_attempt": None,
        }
        backup_instance.update_from_dict(data)
        assert backup_instance.config_name == "renamed"
        assert len(backup_instance.sources) == 2
        assert backup_instance.schedule == {"count": 120, "unit": "seconds"}
        assert backup_instance.drive_upload is True

    def test_update_from_dict_missing_key(self, backup_instance):
        with pytest.raises(ValueError, match="missing required key"):
            backup_instance.update_from_dict({"config_name": "x"})

    def test_update_from_dict_while_running(self, backup_instance):
        backup_instance._manual_backup_ongoing = True
        with pytest.raises(ValueError, match="Cannot edit.*while it is ongoing"):
            backup_instance.update_from_dict({"config_name": "x"})
        backup_instance._manual_backup_ongoing = False

    def test_update_from_dict_last_attempt(self, tmp_source_dir, tmp_dest_dir):
        b = Backup("t", [tmp_source_dir], tmp_dest_dir)
        data = {
            "config_name": "t",
            "sources": [str(tmp_source_dir)],
            "destination": str(tmp_dest_dir),
            "exclusions": [],
            "schedule": None,
            "drive_upload": False,
            "drive_folder_id": None,
            "last_scheduled_attempt": "2025-07-01T08:00:00",
        }
        b.update_from_dict(data)
        assert b.last_scheduled_attempt == datetime(2025, 7, 1, 8, 0, 0)

    def test_update_from_dict_invalid_iso(self, backup_instance):
        data = backup_instance.to_dict()
        data["last_scheduled_attempt"] = "not-a-date"
        with pytest.raises(ValueError):
            backup_instance.update_from_dict(data)


class TestFlattenPaths:
    def test_file(self, backup_instance, tmp_source_dir):
        result = backup_instance._flatten_paths([tmp_source_dir / "file1.txt"])
        assert len(result) == 1
        assert result[0] == (tmp_source_dir / "file1.txt").resolve()

    def test_empty_directory(self, backup_instance, tmp_path):
        empty = tmp_path / "empty_dir"
        empty.mkdir()
        result = backup_instance._flatten_paths([empty])
        assert len(result) == 1
        assert result[0] == empty.resolve()

    def test_non_empty_directory(self, backup_instance, tmp_source_dir):
        result = backup_instance._flatten_paths([tmp_source_dir])
        paths = {p.name for p in result}
        assert "file1.txt" in paths
        assert "file2.py" in paths
        assert "nested.txt" in paths
        assert "empty.txt" in paths
        assert "subdir" not in paths

    def test_symlink_ignored(self, backup_instance, tmp_path):
        real = tmp_path / "real.txt"
        real.write_text("real")
        link = tmp_path / "link.txt"
        try:
            link.symlink_to(real)
        except (OSError, NotImplementedError):
            pytest.skip("symlinks not supported")
        result = backup_instance._flatten_paths([link, real])
        names = {p.name for p in result}
        assert "real.txt" in names
        assert "link.txt" not in names

    def test_multiple_paths(self, backup_instance, tmp_source_dir, tmp_path):
        extra = tmp_path / "extra.txt"
        extra.write_text("extra")
        result = backup_instance._flatten_paths([tmp_source_dir / "file1.txt", extra])
        assert len(result) == 2


class TestEffectiveSources:
    def test_no_exclusions(self, backup_instance, tmp_source_dir):
        eff = backup_instance.effective_sources
        names = {p.name for p in eff}
        assert "file1.txt" in names

    def test_with_exclusions(self, tmp_source_dir, tmp_dest_dir):
        excl = tmp_source_dir / "file1.txt"
        b = Backup("test", [tmp_source_dir], tmp_dest_dir, exclusions=[excl])
        eff = b.effective_sources
        names = {p.name for p in eff}
        assert "file1.txt" not in names
        assert "file2.py" in names


class TestSizeBytes:
    def test_single_file(self, backup_instance, tmp_source_dir):
        fp = tmp_source_dir / "data.bin"
        fp.write_bytes(b"x" * 100)
        size = backup_instance.size_bytes
        assert size >= 100

    def test_empty_file_contributes_zero(self, backup_instance):
        size = backup_instance.size_bytes
        assert size >= 0


class TestNextBackup:
    def test_no_schedule(self, backup_instance):
        assert backup_instance.next_backup is None

    def test_no_last_attempt(self, tmp_source_dir, tmp_dest_dir):
        b = Backup("t", [tmp_source_dir], tmp_dest_dir, schedule={"count": 1, "unit": "hours"})
        nb = b.next_backup
        assert nb is not None
        assert (datetime.now() - nb).total_seconds() < 1

    def test_with_last_attempt(self, tmp_source_dir, tmp_dest_dir):
        dt = datetime.now() - timedelta(minutes=30)
        b = Backup("t", [tmp_source_dir], tmp_dest_dir, schedule={"count": 1, "unit": "hours"}, last_scheduled_attempt=dt)
        expected = dt + timedelta(hours=1)
        assert abs((b.next_backup - expected).total_seconds()) < 1


class TestBackupRunning:
    def test_not_running(self, backup_instance):
        assert backup_instance.backup_running is False

    def test_manual_running(self, backup_instance):
        backup_instance._manual_backup_ongoing = True
        assert backup_instance.backup_running is True
        backup_instance._manual_backup_ongoing = False

    def test_scheduled_running(self, backup_instance):
        backup_instance._scheduled_backup_ongoing = True
        assert backup_instance.backup_running is True
        backup_instance._scheduled_backup_ongoing = False


class TestBackupProgress:
    def test_not_running(self, backup_instance):
        assert backup_instance.backup_progress is None

    def test_running_no_progress(self, backup_instance):
        backup_instance._manual_backup_ongoing = True
        assert backup_instance.backup_progress == {}
        backup_instance._manual_backup_ongoing = False

    def test_running_with_message(self, backup_instance):
        backup_instance._manual_backup_ongoing = True
        backup_instance._progress_message = "Copying..."
        assert backup_instance.backup_progress["message"] == "Copying..."
        backup_instance._manual_backup_ongoing = False
        backup_instance._progress_message = None

    def test_running_with_percent(self, backup_instance):
        backup_instance._manual_backup_ongoing = True
        backup_instance._progress_percent = 0.5
        assert backup_instance.backup_progress["percent"] == 0.5
        backup_instance._manual_backup_ongoing = False
        backup_instance._progress_percent = None


class TestStatus:
    def test_default(self, backup_instance):
        st = backup_instance.status
        assert st["backup_running"] is False
        assert st["backup_error"] is False
        assert st["scheduler_running"] is False
        assert st["scheduler_error"] is False
        assert st["backup_progress"] is None

    def test_after_set_events(self, backup_instance):
        backup_instance.backup_error_event.set()
        backup_instance.scheduler_error_event.set()
        st = backup_instance.status
        assert st["backup_error"] is True
        assert st["scheduler_error"] is True


class TestGetDestinationPaths:
    def test_single_source(self, backup_instance, tmp_source_dir, tmp_dest_dir):
        paths = backup_instance._get_destination_paths([tmp_source_dir], tmp_dest_dir)
        assert len(paths) == 1
        assert paths[0] == tmp_dest_dir / tmp_source_dir.name

    def test_multiple_sources_common_parent(self, backup_instance, tmp_path):
        parent = tmp_path / "parent"
        parent.mkdir()
        s1 = parent / "sub1"
        s1.mkdir()
        s2 = parent / "sub2"
        s2.mkdir()
        bdest = tmp_path / "backup_dest"
        bdest.mkdir()
        paths = backup_instance._get_destination_paths([s1, s2], bdest)
        assert len(paths) == 2
        assert paths[0] == bdest / parent.name / s1.name
        assert paths[1] == bdest / parent.name / s2.name

    def test_relative_sources(self, backup_instance, tmp_path):
        bdest = tmp_path / "backup_dest_2"
        bdest.mkdir()
        rel = Path("relative/path")
        paths = backup_instance._get_destination_paths([rel], bdest)
        assert len(paths) == 1
        assert paths[0] == bdest / "relative" / "path"


class TestCopyItems:
    def test_copy_single_file(self, backup_instance, tmp_source_dir, tmp_dest_dir):
        dest_sub = tmp_dest_dir / "backup_sub"
        backup_instance.copy_items([tmp_source_dir / "file1.txt"], dest_sub)
        assert (dest_sub / "file1.txt").exists()
        assert (dest_sub / "file1.txt").read_text() == "hello"

    def test_copy_directory(self, backup_instance, tmp_source_dir, tmp_dest_dir):
        dest_sub = tmp_dest_dir / "backup_sub"
        backup_instance.copy_items([tmp_source_dir / "subdir"], dest_sub)
        assert (dest_sub / "subdir" / "nested.txt").exists()

    def test_copy_multiple(self, backup_instance, tmp_source_dir, tmp_dest_dir):
        dest_sub = tmp_dest_dir / "backup_sub"
        backup_instance.copy_items(
            [tmp_source_dir / "file1.txt", tmp_source_dir / "file2.py"], dest_sub
        )
        assert (dest_sub / tmp_source_dir.name / "file1.txt").exists()
        assert (dest_sub / tmp_source_dir.name / "file2.py").exists()

    def test_cancellation_during_copy(self, backup_instance, tmp_source_dir, tmp_dest_dir):
        backup_instance._cancel_backup_event.set()
        dest_sub = tmp_dest_dir / "backup_sub"
        with pytest.raises(CancelledError):
            backup_instance.copy_items([tmp_source_dir / "file1.txt"], dest_sub)
        backup_instance._cancel_backup_event.clear()

    def test_progress_percent(self, backup_instance, tmp_source_dir, tmp_dest_dir):
        dest_sub = tmp_dest_dir / "backup_sub"
        backup_instance.copy_items([tmp_source_dir / "file1.txt", tmp_source_dir / "file2.py"], dest_sub)
        assert backup_instance._progress_percent == 1.0

    def test_overwrite_existing_file(self, backup_instance, tmp_source_dir, tmp_dest_dir):
        dest_sub = tmp_dest_dir / "backup_sub"
        dest_sub.mkdir(parents=True)
        existing = dest_sub / "file1.txt"
        existing.write_text("old")
        backup_instance.copy_items([tmp_source_dir / "file1.txt"], dest_sub)
        assert existing.read_text() == "hello"

    def test_source_not_found(self, backup_instance, tmp_source_dir, tmp_dest_dir):
        missing = tmp_source_dir / "nonexistent.txt"
        dest_sub = tmp_dest_dir / "backup_sub"
        backup_instance.copy_items([missing], dest_sub)
        assert not (dest_sub / "nonexistent.txt").exists()


class TestVerifyDetails:
    def test_valid(self, backup_instance, tmp_source_dir, tmp_dest_dir):
        backup_instance.verify_details()

    def test_no_config_name(self, backup_instance):
        backup_instance.config_name = ""
        with pytest.raises(ValueError, match="no configuration name"):
            backup_instance.verify_details()
        backup_instance.config_name = "test_backup"

    def test_no_sources(self, backup_instance):
        backup_instance.sources = []
        with pytest.raises(ValueError, match="no sources"):
            backup_instance.verify_details()

    def test_no_destination(self, backup_instance):
        backup_instance.destination = Path("/nonexistent_xyz_dest")
        with pytest.raises(ValueError, match="does not exist"):
            backup_instance.verify_details()

    def test_source_not_exists(self, backup_instance):
        missing = Path("/nonexistent/path")
        backup_instance.sources = [missing]
        with pytest.raises(ValueError, match="not exist"):
            backup_instance.verify_details()

    def test_destination_not_exists(self, backup_instance):
        backup_instance.destination = Path("/nonexistent/dest")
        with pytest.raises(ValueError, match="not exist"):
            backup_instance.verify_details()

    def test_drive_upload_no_folder_id(self, tmp_source_dir, tmp_dest_dir):
        b = Backup("t", [tmp_source_dir], tmp_dest_dir, drive_upload=True, drive_folder_id=None)
        with pytest.raises(ValueError, match="does not have a Drive folder"):
            b.verify_details()

    def test_drive_upload_has_folder_id(self, tmp_source_dir, tmp_dest_dir):
        b = Backup("t", [tmp_source_dir], tmp_dest_dir, drive_upload=True, drive_folder_id="abc")
        b.verify_details()


class TestCreateBackup:
    def test_success(self, backup_instance, tmp_source_dir, tmp_dest_dir):
        result = backup_instance.create_backup()
        assert "backup_folder" in result
        assert result["drive_backup_folder_id"] is None
        assert result["backup_folder"].exists()

    def test_cancelled_at_start(self, backup_instance):
        backup_instance._cancel_backup_event.set()
        with pytest.raises(CancelledError):
            backup_instance.create_backup()
        backup_instance._cancel_backup_event.clear()

    def test_verify_failure(self, backup_instance):
        backup_instance.destination = Path("/nonexistent")
        with pytest.raises(RuntimeError, match="Failed to verify backup details"):
            backup_instance.create_backup()


class TestStartCancelBackup:
    def test_start_and_wait(self, backup_instance):
        backup_instance.start_backup()
        result = backup_instance.wait_for_backup()
        assert result is not None
        assert "backup_folder" in result

    def test_double_start_fails(self, backup_instance):
        backup_instance.start_backup()
        with pytest.raises(RuntimeError):
            backup_instance.start_backup()
        backup_instance.wait_for_backup()

    def test_start_while_scheduled_fails(self, backup_instance):
        backup_instance._scheduled_backup_ongoing = True
        with pytest.raises(RuntimeError, match="Scheduled backup is currently ongoing"):
            backup_instance.start_backup()
        backup_instance._scheduled_backup_ongoing = False

    def test_wait_no_backup(self, backup_instance):
        result = backup_instance.wait_for_backup()
        assert result is None

    def test_backup_progress_cleared_after_completion(self, backup_instance):
        backup_instance._progress_message = "Testing"
        backup_instance.start_backup()
        backup_instance.wait_for_backup()
        assert backup_instance._progress_message is None
        assert backup_instance._progress_percent is None

    def test_cancel_with_undo(self, tmp_path):
        """Create a backup, cancel with undo, verify no crash."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "file.txt").write_text("hello")

        dest = tmp_path / "dest"
        dest.mkdir()

        b = Backup("cancel_test", [src], dest)
        b.start_backup()
        time.sleep(0.02)
        b.cancel_backup(undo=True)
        b.wait_for_backup()

    def test_cancel_no_backup(self, backup_instance):
        backup_instance.cancel_backup()

    def test_cancel_re_raises_non_cancelled(self, backup_instance):
        backup_instance._backup_error = RuntimeError("something bad")
        backup_instance._backup_thread = threading.Thread(
            target=lambda: time.sleep(0.1), daemon=True
        )
        backup_instance._backup_thread.start()
        time.sleep(0.01)
        with pytest.raises(RuntimeError, match="something bad"):
            backup_instance.cancel_backup()
        backup_instance._backup_thread.join()


class TestScheduler:
    def test_start_no_schedule(self, backup_instance):
        backup_instance.start_scheduler()
        assert backup_instance.scheduler_running is False

    def test_start_and_stop(self, tmp_source_dir, tmp_dest_dir):
        b = Backup("sched", [tmp_source_dir], tmp_dest_dir, schedule={"count": 1, "unit": "hours"})
        b.start_scheduler()
        assert b.scheduler_running is True
        b.stop_scheduler()
        assert b.scheduler_running is False

    def test_double_start_fails(self, tmp_source_dir, tmp_dest_dir):
        b = Backup("s", [tmp_source_dir], tmp_dest_dir, schedule={"count": 1, "unit": "hours"})
        b.start_scheduler()
        with pytest.raises(RuntimeError, match="already running"):
            b.start_scheduler()
        b.stop_scheduler()

    def test_stop_no_scheduler(self, backup_instance):
        backup_instance.stop_scheduler()

    def test_start_while_manual_ongoing(self, tmp_source_dir, tmp_dest_dir):
        b = Backup("x", [tmp_source_dir], tmp_dest_dir, schedule={"count": 1, "unit": "hours"})
        b._manual_backup_ongoing = True
        with pytest.raises(RuntimeError, match="Manual backup is currently running"):
            b.start_scheduler()
        b._manual_backup_ongoing = False

    def test_wait_for_scheduler(self, tmp_source_dir, tmp_dest_dir):
        b = Backup("w", [tmp_source_dir], tmp_dest_dir, schedule={"count": 1, "unit": "hours"})
        b.start_scheduler()
        b.stop_scheduler()
        b.wait_for_scheduler()
        assert b.scheduler_running is False

    def test_wait_no_scheduler(self, backup_instance):
        backup_instance.wait_for_scheduler()

    def test_run_scheduler_no_schedule_breaks(self, backup_instance):
        backup_instance.run_scheduler()

    def test_scheduler_runs_backup(self, tmp_source_dir, tmp_dest_dir):
        b = Backup("run", [tmp_source_dir], tmp_dest_dir, schedule={"count": 1, "unit": "seconds"})
        b.start_scheduler()
        time.sleep(0.05)
        b.stop_scheduler()

    def test_run_scheduler_cancelled_during_manual_wait(self, backup_instance):
        backup_instance._manual_backup_ongoing = True

        def delayed_release():
            time.sleep(0.05)
            backup_instance._manual_backup_ongoing = False
            backup_instance._backup_result = {}

        t = threading.Thread(target=delayed_release, daemon=True)
        t.start()
        backup_instance.run_scheduler()
        t.join()
