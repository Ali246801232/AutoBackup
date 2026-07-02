import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from datetime import datetime

import pytest
from backup import Backup

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
