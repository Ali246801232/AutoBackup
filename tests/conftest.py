import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


import pytest
from backup import Backup


@pytest.fixture
def tmp_source_dir(tmp_path):
    d = tmp_path / "source"
    d.mkdir()
    (d / "file1.txt").write_text("hello")
    (d / "file2.py").write_text("print(\"hi\")")
    sub = d / "subdir"
    sub.mkdir()
    (sub / "nested.txt").write_text("nested")
    (sub / "empty.txt").write_text("")
    return d


@pytest.fixture
def tmp_dest_dir(tmp_path):
    d = tmp_path / "dest"
    d.mkdir()
    return d


@pytest.fixture
def backup_instance(tmp_source_dir, tmp_dest_dir):
    return Backup(
        config_name="test_backup",
        sources=[tmp_source_dir],
        destination=tmp_dest_dir,
        exclusions=[],
        schedule=None,
        drive_upload=False,
    )


@pytest.fixture
def backup_dict(backup_instance):
    return backup_instance.to_dict()
