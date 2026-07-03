"""Test src/backup/backup.py."""

import time
import threading
from pathlib import Path
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

import pytest
from backup.backup import Backup, _schedule_to_timedelta
from backup._utils import CancelledError


@pytest.fixture
def tmp_source(tmp_path):
    source = tmp_path / "fixture_source"
    source.mkdir()
    (source / "source_file_1.txt").write_text("source_file_1")
    (source / "source_file_2.txt").write_text("source_file_2")
    sub = source / "source_subdir"
    sub.mkdir()
    (sub / "source_file_nested.txt").write_text("source_file_nested")
    (sub / "source_file_empty.txt").write_text("")
    return source

@pytest.fixture
def tmp_destination(tmp_path):
    destination = tmp_path / "fixture_destination"
    destination.mkdir()
    return destination

@pytest.fixture
def tmp_exclusion(tmp_source):
    exclusion = tmp_source / "fixture_exclusion"
    exclusion.mkdir()
    (exclusion / "exclusion_file_1.txt").write_text("exclusion_file_1")
    return exclusion

@pytest.fixture
def backup_instance(tmp_source, tmp_destination, tmp_exclusion):
    return Backup(
        config_name="test_backup",
        sources=[tmp_source],
        destination=tmp_destination,
        exclusions=[tmp_exclusion],
        schedule={"count": 2, "unit": "seconds"},
        drive_upload=False,
        drive_folder_id=None,
    )

@pytest.fixture
def backup_dict(backup_instance):
    return backup_instance.to_dict()


class TestInit:
    def test_init(self, backup_instance, tmp_source, tmp_destination, tmp_exclusion):
        assert backup_instance.config_name == "test_backup"
        assert backup_instance.sources == [tmp_source.resolve()]
        assert backup_instance.destination == tmp_destination.resolve()
        assert backup_instance.exclusions == [tmp_exclusion.resolve()]
        assert backup_instance.schedule == {"count": 2, "unit": "seconds"}
        assert backup_instance.drive_upload is False
        assert backup_instance.drive_folder_id is None

class TestSerialization:
    def test_to_dict(self, backup_instance):
        backup_instance.last_scheduled_attempt = datetime(2025, 6, 1, 12, 0, 0)
        d = backup_instance.to_dict()
        assert d["config_name"] == "test_backup"
        assert len(d["sources"]) == 1
        assert d["schedule"] == {"count": 2, "unit": "seconds"}
        assert d["drive_upload"] is False
        assert d["drive_folder_id"] is None
        assert d["last_scheduled_attempt"] == "2025-06-01T12:00:00"

    def test_from_dict(self, backup_dict, tmp_source, tmp_destination, tmp_exclusion):
        backup_dict["last_scheduled_attempt"] = "2025-06-01T12:00:00"
        d = backup_dict
        b = Backup.from_dict(d)
        assert b.config_name == "test_backup"
        assert b.sources == [tmp_source.resolve()]
        assert b.destination == tmp_destination.resolve()
        assert b.exclusions == [tmp_exclusion.resolve()]
        assert b.schedule == {"count": 2, "unit": "seconds"}
        assert b.drive_upload is False
        assert b.drive_folder_id is None
        assert b.last_scheduled_attempt == datetime(2025, 6, 1, 12, 0, 0)

    def test_roundtrip(self, backup_instance):
        d = backup_instance.to_dict()
        b = Backup.from_dict(d)
        assert b.config_name == backup_instance.config_name
        assert b.sources == backup_instance.sources
        assert b.destination == backup_instance.destination
        assert b.exclusions == backup_instance.exclusions
        assert b.schedule == backup_instance.schedule
        assert b.drive_upload == backup_instance.drive_upload
        assert b.drive_folder_id == backup_instance.drive_folder_id

    def test_json_roundtrip(self, backup_instance, tmp_path):
        f = tmp_path / "config.json"
        backup_instance.to_json(f)
        b = Backup.from_json(f)
        assert b.to_dict() == backup_instance.to_dict()

    def test_update_from_dict(self, backup_instance, tmp_path, tmp_source, tmp_destination):
        new_src = tmp_path / "new_src_dir"
        new_src.mkdir(exist_ok=True)
        new_dst = tmp_destination / "new_dst_dir"
        new_dst.mkdir(exist_ok=True)
        new_exc = tmp_source / "new_exc_file.txt"
        new_exc.write_text("new_exc_file")
        d = {
            "config_name": "renamed",
            "sources": [str(tmp_source), str(new_src)],
            "destination": str(new_dst),
            "exclusions": [str(new_exc)],
            "schedule": {"count": 120, "unit": "seconds"},
            "drive_upload": True,
            "drive_folder_id": "new-drive-id",
            "last_scheduled_attempt": "2025-07-01T08:00:00",
        }
        backup_instance.update_from_dict(d)
        assert backup_instance.config_name == "renamed"
        assert backup_instance.sources == [tmp_source.resolve(), new_src.resolve()]
        assert backup_instance.destination == new_dst.resolve()
        assert backup_instance.exclusions == [new_exc.resolve()]
        assert backup_instance.schedule == {"count": 120, "unit": "seconds"}
        assert backup_instance.drive_upload is True
        assert backup_instance.drive_folder_id == "new-drive-id"
        assert backup_instance.last_scheduled_attempt == datetime(2025, 7, 1, 8, 0, 0)

    def test_update_from_dict_missing_keys(self, backup_instance):
        d = backup_instance.to_dict()
        del d["config_name"]
        with pytest.raises(ValueError):
            backup_instance.update_from_dict(d)

    def test_update_from_dict_while_running(self, backup_instance):
        d = backup_instance.to_dict()
        d["config_name"] = "renamed"
        backup_instance._manual_backup_ongoing = True
        with pytest.raises(ValueError):
            backup_instance.update_from_dict(d)

    def test_update_from_dict_invalid_iso(self, backup_instance):
        data = backup_instance.to_dict()
        data["last_scheduled_attempt"] = "not-a-date"
        with pytest.raises(ValueError):
            backup_instance.update_from_dict(data)


class TestFlattenPaths:
    def test_file(self, backup_instance, tmp_source):
        unflattened = [(tmp_source / "source_file_1.txt").resolve()]
        flattened = backup_instance._flatten_paths(unflattened)
        assert flattened == unflattened

    def test_empty_directory(self, backup_instance, tmp_path):
        empty_dir = tmp_path / "empty_dir"
        empty_dir.mkdir()
        flattened = backup_instance._flatten_paths([empty_dir])
        assert flattened == [empty_dir.resolve()]

    def test_non_empty_directory(self, backup_instance, tmp_source):
        flattened = backup_instance._flatten_paths([tmp_source])
        names = {p.name for p in flattened}
        assert "source_file_1.txt" in names
        assert "source_file_2.txt" in names
        assert "source_file_nested.txt" in names
        assert "source_file_empty.txt" in names
        assert "source_subdir" not in names

    def test_symlink_ignored(self, backup_instance, tmp_path):
        real = tmp_path / "real.txt"
        real.write_text("real")
        link = tmp_path / "link.txt"
        try:
            link.symlink_to(real)
        except (OSError, NotImplementedError):
            pytest.skip("symlinks are not supported")
        flattened = backup_instance._flatten_paths([link, real])
        names = {p.name for p in flattened}
        assert "real.txt" in names
        assert "link.txt" not in names

    def test_multiple_paths(self, backup_instance, tmp_source, tmp_path):
        new_file = tmp_path / "new_file.txt"
        new_file.write_text("new_file")
        unflattened = [(tmp_source / "source_file_1.txt").resolve(), new_file.resolve()]
        flattened = backup_instance._flatten_paths(unflattened)
        assert sorted(flattened) == sorted(unflattened)

    def test_multiple_identical(self, backup_instance, tmp_path):
        path = tmp_path / "file.txt"
        path.write_text("file")
        assert backup_instance._flatten_paths([path, path]) == [path]

    def test_missing_path(self, backup_instance):
        assert backup_instance._flatten_paths([Path("/mising")]) == []



class TestEffectiveSources:
    def test_effective_sources(self, backup_instance):
        effective_sources = backup_instance.effective_sources
        names = {p.name for p in effective_sources}
        assert "source_file_1.txt" in names
        assert "source_file_2.txt" in names
        assert "source_file_nested.txt" in names
        assert "source_file_empty.txt" in names
        assert "exclusion_file_1.txt" not in names


class TestSizeBytes:
    def test_single_file(self, backup_instance, tmp_path):
        f = tmp_path / "data_file.bin"
        f.write_bytes(b"x" * 100)
        backup_instance.sources = [f]
        size = backup_instance.size_bytes
        assert size == 100
    
    def test_multiple_files(self, backup_instance, tmp_path):
        files = [tmp_path / "data_file_1.bin", tmp_path / "data_file_2.bin"]
        files[0].write_bytes(b"x" * 100)
        files[1].write_bytes(b"x" * 200)
        backup_instance.sources = files
        size = backup_instance.size_bytes
        assert size == 300

    def test_empty_file_contributes_zero(self, backup_instance):
        backup_instance.sources = []
        size = backup_instance.size_bytes
        assert size == 0


class TestNextBackup:
    def test_no_schedule(self, backup_instance):
        backup_instance.schedule = None
        assert backup_instance.next_backup is None

    def test_no_last_scheduled_attempt(self, backup_instance):
        assert backup_instance.next_backup is not None
        assert (datetime.now() - backup_instance.next_backup).total_seconds() < 1

    def test_with_last_attempt(self, backup_instance):
        backup_instance.last_scheduled_attempt = datetime.now()
        expected_next = datetime.now() + timedelta(seconds=2)
        assert abs((backup_instance.next_backup - expected_next).total_seconds()) < 1


class TestBackupProgress:
    def test_not_running(self, backup_instance):
        assert backup_instance.backup_progress == {}

    def test_running_no_progress(self, backup_instance):
        backup_instance._manual_backup_ongoing = True
        assert backup_instance.backup_progress == {}

    def test_running_with_progress(self, backup_instance):
        backup_instance._manual_backup_ongoing = True
        backup_instance._progress_message = "progress message"
        backup_instance._progress_percent = 0.5
        progress = backup_instance.backup_progress
        assert progress["message"] == "progress message"
        assert progress["percent"] == 0.5


class TestStatus:
    def test_default(self, backup_instance):
        status = backup_instance.status
        assert status["backup_running"] is False
        assert status["backup_error"] is False
        assert status["backup_error_message"] is None
        assert status["scheduler_running"] is False
        assert status["scheduler_error"] is False
        assert status["scheduler_error_message"] is None
        assert status["backup_progress"] == {}

    def test_after_set_events(self, backup_instance):
        backup_instance._backup_error = RuntimeError("test error")
        backup_instance.backup_error_event.set()
        backup_instance._scheduler_error = RuntimeError("test error")
        backup_instance.scheduler_error_event.set()
        status = backup_instance.status
        assert status["backup_error"] is True
        assert status["backup_error_message"] == "test error"
        assert status["scheduler_error"] is True
        assert status["scheduler_error_message"] == "test error"


class TestGetDestinationPaths:
    def test_single_source(self, backup_instance, tmp_path):
        source = tmp_path / "source.txt"
        destination = tmp_path / "destination"
        destination.mkdir()
        paths = backup_instance._get_destination_paths([source], destination)
        assert paths == [destination / source.name]

    def test_multiple_sources_common_parent(self, backup_instance, tmp_path):
        parent = tmp_path / "parent"
        parent.mkdir()
        children = [parent / "child_dir", parent / "child_file.txt"]
        children[0].mkdir()
        destination = tmp_path / "destination"
        destination.mkdir()
        paths = backup_instance._get_destination_paths(children, destination)
        assert sorted(paths) == sorted([
            (destination / parent.name / children[0].name),
            (destination / parent.name / children[1].name)
        ])


    def test_relative_sources(self, backup_instance, tmp_path):
        destination = tmp_path / "destination"
        destination.mkdir()
        rel = Path("relative/path")
        paths = backup_instance._get_destination_paths([rel], destination)
        assert paths == [destination / "relative" / "path"]


class TestCopyItems:
    def test_copy_file(self, backup_instance, tmp_path):
        destination = tmp_path / "destination"
        source_file = tmp_path / "source_file.txt"
        source_file.write_text("source_file")
        backup_instance.copy_items([source_file], destination)
        assert (destination / "source_file.txt").exists()
        assert (destination / "source_file.txt").read_text() == "source_file"

    def test_copy_directory(self, backup_instance, tmp_path):
        destination = tmp_path / "destination"
        source_dir = tmp_path / "source_dir"
        source_dir.mkdir()
        (source_dir / "source_file.txt").write_text("source_file")
        backup_instance.copy_items([source_dir], destination)
        assert (destination / "source_dir" / "source_file.txt").exists()
        assert (destination / "source_dir" / "source_file.txt").read_text() == "source_file"

    def test_cancel_during_copy(self, backup_instance):
        backup_instance._cancel_backup_event.set()
        with pytest.raises(CancelledError):
            backup_instance.copy_items(backup_instance.sources, backup_instance.destination)

    def test_overwrite_existing(self, backup_instance, tmp_path):
        destination = tmp_path / "destination"
        destination.mkdir()
        source_file = tmp_path / "file.txt"
        source_file.write_text("source_file")
        existing_file = destination / "file.txt"
        existing_file.write_text("existing_file")
        backup_instance.copy_items([source_file], destination)
        assert existing_file.read_text() == "source_file"

    def test_missing_source(self, backup_instance, tmp_path):
        missing_file = tmp_path / "missing_file.txt"
        destination = tmp_path / "destination"
        backup_instance.copy_items([missing_file], destination)
        assert not (destination / "missing_file.txt").exists()

    def test_empty_sources(self, backup_instance, tmp_path):
        destination = tmp_path / "destination"
        backup_instance.copy_items([], destination)
        assert destination.exists()
        assert not list(destination.iterdir())

    def test_progress_updates(self, backup_instance):
        backup_instance.copy_items(backup_instance.sources, backup_instance.destination)
        assert backup_instance._progress_percent == 1.0


class TestVerifyDetails:
    def test_valid(self, backup_instance):
        backup_instance.verify_details()

    def test_valid_minimal(self, backup_instance):
        backup_instance.exclusions = []
        backup_instance.schedule = None
        backup_instance.drive_upload = False
        backup_instance.drive_folder_id = None
        backup_instance.last_scheduled_attempt = None
        backup_instance.verify_details()

    def test_verify_config_name(self, backup_instance):
        backup_instance.config_name = None
        with pytest.raises(ValueError):
            backup_instance.verify_details()
        backup_instance.config_name = ""
        with pytest.raises(ValueError):
            backup_instance.verify_details()
        backup_instance.config_name = 1
        with pytest.raises(ValueError):
            backup_instance.verify_details()

    def test_verify_sources(self, backup_instance):
        backup_instance.sources = []
        with pytest.raises(ValueError):
            backup_instance.verify_details()
        backup_instance.sources = [1, 2.0, True]
        with pytest.raises(ValueError):
            backup_instance.verify_details()
        backup_instance.sources = [Path("/missing")]
        with pytest.raises(ValueError):
            backup_instance.verify_details()

    def test_verify_destination(self, backup_instance):
        backup_instance.destination = None
        with pytest.raises(ValueError):
            backup_instance.verify_details()
        backup_instance.destination = 1
        with pytest.raises(ValueError):
            backup_instance.verify_details()
        backup_instance.destination = Path("/missing")
        with pytest.raises(ValueError):
            backup_instance.verify_details()

    def test_verify_exclusions(self, backup_instance):
        backup_instance.exclusions = [1, 2.0, True]
        with pytest.raises(ValueError):
            backup_instance.verify_details()

    def test_verify_schedule(self, backup_instance):
        backup_instance.schedule = 1
        with pytest.raises(ValueError):
            backup_instance.verify_details()
        backup_instance.schedule = {"count": 5}
        with pytest.raises(ValueError):
            backup_instance.verify_details()
        backup_instance.schedule = {"unit": "seconds"}
        with pytest.raises(ValueError):
            backup_instance.verify_details()
        backup_instance.schedule = {"count": 0, "unit": "seconds"}
        with pytest.raises(ValueError):
            backup_instance.verify_details()
        backup_instance.schedule = {"count": 5, "unit": "invalid"}
        with pytest.raises(ValueError):
            backup_instance.verify_details()

    def test_verify_drive_details(self, backup_instance):
        backup_instance.drive_upload = True
        backup_instance.drive_folder_id = None
        with pytest.raises(ValueError):
            backup_instance.verify_details()

class TestBackup:
    def test_start_and_wait(self, backup_instance):
        backup_instance.start_backup()
        result = backup_instance.wait_for_backup()
        assert result["backup_folder"].exists()
        assert result["drive_backup_folder_id"] is None

    def test_double_start_fails(self, backup_instance):
        backup_instance.start_backup()
        with pytest.raises(RuntimeError):
            backup_instance.start_backup()
        backup_instance.wait_for_backup()

    def test_start_while_scheduled_fails(self, backup_instance):
        backup_instance._scheduled_backup_ongoing = True
        with pytest.raises(RuntimeError):
            backup_instance.start_backup()

    def test_backup_progress_cleared_after_completion(self, backup_instance):
        backup_instance._progress_message = "progress message"
        backup_instance.start_backup()
        backup_instance.wait_for_backup()
        assert backup_instance._progress_message is None
        assert backup_instance._progress_percent is None

    def test_cancel_with_undo(self, backup_instance, tmp_path):
        sources = [tmp_path / "source_dir"]
        sources[0].mkdir()
        (sources[0] / "file.txt").write_text("file")
        destination = tmp_path / "destination"
        destination.mkdir()
        backup_instance.sources = sources
        backup_instance.destination = destination
        backup_instance.start_backup()
        backup_instance.cancel_backup(undo=True)
        assert not (destination / "source_dir").exists()

    def test_cancel_re_raises(self, backup_instance):
        backup_instance._backup_error = RuntimeError("test backup error")
        backup_instance._backup_thread = threading.Thread(target=lambda: time.sleep(0.1), daemon=True)
        backup_instance._backup_thread.start()
        with pytest.raises(RuntimeError, match="test backup error"):
            backup_instance.cancel_backup()
        backup_instance._backup_thread.join()

    def test_wait_re_raises(self, backup_instance):
        backup_instance._backup_error = RuntimeError("test backup error")
        with pytest.raises(RuntimeError, match="test backup error"):
            backup_instance.wait_for_backup()


class TestScheduler:
    def test_start_no_schedule(self, backup_instance):
        backup_instance.schedule = None
        backup_instance.start_scheduler()
        assert backup_instance.scheduler_running is False

    def test_start_stop(self, backup_instance):
        backup_instance.start_scheduler()
        assert backup_instance.scheduler_running is True
        backup_instance.stop_scheduler()
        assert backup_instance.scheduler_running is False

    def test_double_start_fails(self, backup_instance):
        backup_instance.start_scheduler()
        with pytest.raises(RuntimeError):
            backup_instance.start_scheduler()
        backup_instance.stop_scheduler()

    def test_stop_no_scheduler(self, backup_instance):
        backup_instance.stop_scheduler()

    def test_start_while_manual_ongoing(self, backup_instance):
        backup_instance._manual_backup_ongoing = True
        with pytest.raises(RuntimeError):
            backup_instance.start_scheduler()

    def test_wait_no_scheduler(self, backup_instance):
        backup_instance.wait_for_scheduler()

    def test_stop_re_raises(self, backup_instance):
        backup_instance._scheduler_error = RuntimeError("test scheduler error")
        backup_instance._scheduler_thread = threading.Thread(target=lambda: time.sleep(0.1), daemon=True)
        backup_instance._scheduler_thread.start()
        with pytest.raises(RuntimeError, match="test scheduler error"):
            backup_instance.stop_scheduler()
        backup_instance._scheduler_thread.join()

    def test_wait_re_raises(self, backup_instance):
        backup_instance._scheduler_error = RuntimeError("test scheduler error")
        with pytest.raises(RuntimeError, match="test scheduler error"):
            backup_instance.wait_for_scheduler()

    def test_scheduled_backup_sets_last_attempt(self, backup_instance):
        backup_instance.start_scheduler()
        time.sleep(0.1)
        backup_instance.wait_for_backup()
        backup_instance.stop_scheduler()
        assert backup_instance.last_scheduled_attempt is not None


class TestScheduleToTimedelta:
    def test_seconds(self):
        td = _schedule_to_timedelta({"count": 30, "unit": "seconds"})
        assert td.total_seconds() == 30

    def test_minutes(self):
        td = _schedule_to_timedelta({"count": 5, "unit": "minutes"})
        assert td.total_seconds() == 300

    def test_hours(self):
        td = _schedule_to_timedelta({"count": 2, "unit": "hours"})
        assert td.total_seconds() == 7200

    def test_days(self):
        td = _schedule_to_timedelta({"count": 7, "unit": "days"})
        assert td.days == 7

    def test_weeks(self):
        td = _schedule_to_timedelta({"count": 3, "unit": "weeks"})
        assert td.days == 21

    def test_months(self):
        rd = _schedule_to_timedelta({"count": 2, "unit": "months"})
        assert isinstance(rd, relativedelta)
        assert rd.months == 2

    def test_years(self):
        rd = _schedule_to_timedelta({"count": 1, "unit": "years"})
        assert isinstance(rd, relativedelta)
        assert rd.years == 1
