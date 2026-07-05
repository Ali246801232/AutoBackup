"""Test src/backup/drive.py."""

import time
import json
import threading

import pytest
from unittest.mock import MagicMock, patch
from backup import drive


def make_file(file_id="test-id", title="Test Item", parents=[]):
    """Factory for Drive file mocks with dict access."""
    data = {"id": file_id, "title": title, "parents": parents}
    mock = MagicMock()
    mock.__getitem__.side_effect = data.__getitem__
    mock.get.side_effect = lambda k, d=None: data.get(k, d)
    return mock

def _create_file_side_effect(*args, **kwargs):
    metadata = args[0] if args else kwargs.get("metadata", {})
    return make_file(
        file_id=metadata.get("id", "test-id"),
        title=metadata.get("title", "Test Item"),
        parents=metadata.get("parents", []),
    )


def api_request_error():
    from googleapiclient.errors import HttpError
    from pydrive2.files import ApiRequestError
    resp = MagicMock()
    resp.status = 500
    content = json.dumps({"error": "api request error"}).encode()
    return ApiRequestError(HttpError(resp, content))

def refresh_error():
    from pydrive2.auth import RefreshError
    return RefreshError("refresh error")


@pytest.fixture(autouse=True)
def script_dir(tmp_path):
    """Patch SCRIPT_DIR and create empty JSON config files."""
    scripts_dir = tmp_path / "script_dir"
    scripts_dir.mkdir()
    (scripts_dir / "client_secrets.json").write_text("{}")
    (scripts_dir / "credentials.json").write_text("{}")
    with patch("backup.drive.SCRIPT_DIR", scripts_dir):
        yield scripts_dir

@pytest.fixture(autouse=True)
def mock_pydrive2():
    """Patch GoogleAuth and GoogleDrive with configured side effects."""
    with (
        patch("backup.drive.GoogleAuth") as GoogleAuth,
        patch("backup.drive.GoogleDrive") as GoogleDrive,
    ):
        gauth = GoogleAuth.return_value
        gauth.access_token_expired = False
        gauth.settings = {}
        drive = GoogleDrive.return_value
        drive.CreateFile.side_effect = _create_file_side_effect
        drive.ListFile.return_value.GetList.return_value = []
        yield

@pytest.fixture
def handler_instance(mock_pydrive2, script_dir):
    handler_instance = drive.DriveHandler()
    handler_instance.authenticate()
    return handler_instance


class TestInit:
    def test_authenticate(self):
        handler_instance = drive.DriveHandler()
        handler_instance.authenticate()
        assert handler_instance.gauth is not None
        assert handler_instance.drive is not None

    def test_authenticate_error(self):
        handler_instance = drive.DriveHandler()
        with patch("backup.drive.GoogleAuth", side_effect=Exception("error")):
            with pytest.raises(RuntimeError):
                handler_instance.authenticate()


class TestNavigation:
    def test_open_folder(self, handler_instance):
        result = handler_instance.open_folder("drive-id")
        assert result["id"] == handler_instance.current_folder["id"] == "drive-id"

    def test_go_up(self, handler_instance):
        handler_instance.current_folder = make_file(file_id="child-id", parents=[{"id": "parent-id"}])
        result = handler_instance.go_up()
        assert result["id"] == handler_instance.current_folder["id"] == "parent-id"

    def test_go_up_no_parent(self, handler_instance):
        handler_instance.current_folder = make_file(file_id="drive-id", parents=[])
        result = handler_instance.go_up()
        assert result["id"] == handler_instance.current_folder["id"] == "drive-id"

    def test_go_to_root(self, handler_instance):
        result = handler_instance.go_to_root()
        assert result["id"] == handler_instance.current_folder["id"] == "root"


class TestGetters:
    def test_get_children(self, handler_instance):
        handler_instance.current_folder = make_file(file_id="drive-id")
        expected_children = [
            {"title": "b.txt"},
            {"title": "a.txt"},
        ]
        handler_instance.drive.ListFile.return_value.GetList.return_value = expected_children
        children = handler_instance.get_children()
        q = handler_instance.drive.ListFile.call_args[0][0]["q"]
        assert q == "'drive-id' in parents and trashed = false"
        assert children == sorted(expected_children, key=lambda x: x.get("title", "").lower())

    def test_get_children_with_query(self, handler_instance):
        handler_instance.current_folder = make_file(file_id="drive-id")
        handler_instance.get_children(query="mimeType = 'folder'")
        q = handler_instance.drive.ListFile.call_args[0][0]["q"]
        assert q == "'drive-id' in parents and trashed = false and (mimeType = 'folder')"

    def test_get_children_with_folder_id(self, handler_instance):
        handler_instance.get_children(folder_id="overriden-id")
        q = handler_instance.drive.ListFile.call_args[0][0]["q"]
        assert q == "'overriden-id' in parents and trashed = false"

    def test_get_children_api_error(self, handler_instance):
        handler_instance.current_folder = make_file()
        handler_instance.drive.ListFile.side_effect = api_request_error()
        with pytest.raises(RuntimeError):
            handler_instance.get_children()

    def test_get_child_folders(self, handler_instance):
        handler_instance.current_folder = make_file()
        with patch.object(handler_instance, "get_children") as get_children:
            handler_instance.get_child_folders()
            get_children.assert_called_with(None, query="mimeType = 'application/vnd.google-apps.folder'")

    def test_get_child_files(self, handler_instance):
        handler_instance.current_folder = make_file()
        with patch.object(handler_instance, "get_children") as get_children:
            handler_instance.get_child_files()
            get_children.assert_called_with(None, query="mimeType != 'application/vnd.google-apps.folder'")

    def test_get_item(self, handler_instance):
        result = handler_instance.get_item("drive-id")
        assert result["id"] == "drive-id"


class TestUploadFile:
    def test_upload_file(self, tmp_path, handler_instance):

        local_file = tmp_path / "test.txt"
        local_file.write_text("test")

        drive_file = make_file(file_id="drive-id")
        drive_file.SetContentFile = MagicMock()
        drive_file.Upload = MagicMock()
        handler_instance.drive.CreateFile.side_effect = None
        handler_instance.drive.CreateFile.return_value = drive_file

        result = handler_instance.upload_file(local_file, "parent-id")
        assert result == "drive-id"
        handler_instance.drive.CreateFile.assert_called_with(metadata={"parents": [{"id": "parent-id"}]})
        drive_file.SetContentFile.assert_called_with(local_file)
        drive_file.Upload.assert_called_once()

    def test_upload_file_missing(self, tmp_path, handler_instance):
        local_file = tmp_path / "missing.txt"
        with pytest.raises(ValueError):
            handler_instance.upload_file(local_file, "parent-id")

    def test_upload_file_api_error(self, tmp_path, handler_instance):
        local_file = tmp_path / "test.txt"
        local_file.write_text("test")
        handler_instance.drive.CreateFile.side_effect = api_request_error()
        with pytest.raises(RuntimeError):
            handler_instance.upload_file(local_file, "parent-id")

class TestUploadFolder:
    def test_upload_folder(self, tmp_path, handler_instance):

        local_folder = tmp_path / "test"
        local_folder.mkdir()
        (local_folder / "test.txt").write_text("test")

        drive_folder = make_file(file_id="drive-id")
        drive_folder.Upload = MagicMock()
        handler_instance.drive.CreateFile.side_effect = None
        handler_instance.drive.CreateFile.return_value = drive_folder

        result = handler_instance.upload_folder(local_folder, "parent-id")
        assert result == "drive-id"
        assert handler_instance.drive.CreateFile.call_count == 2
        assert drive_folder.Upload.call_count == 2

    def test_upload_folder_missing(self, tmp_path, handler_instance):
        with pytest.raises(ValueError):
            handler_instance.upload_folder(tmp_path / "missing", "parent-id")

    def test_upload_folder_is_file(self, tmp_path, handler_instance):
        local_file = tmp_path / "test.txt"
        local_file.write_text("test")
        with pytest.raises(ValueError):
            handler_instance.upload_folder(local_file, "parent-id")


class TestDeleteTrash:
    def test_trash_item(self, handler_instance):
        item = MagicMock()
        handler_instance.drive.CreateFile.side_effect = None
        handler_instance.drive.CreateFile.return_value = item
        handler_instance.trash_item("drive-id")
        item.Trash.assert_called_once()

    def test_trash_item_error(self, handler_instance):
        handler_instance.drive.CreateFile.side_effect = Exception("error")
        with pytest.raises(RuntimeError):
            handler_instance.trash_item("drive-id")

    def test_delete_item(self, handler_instance):
        item = MagicMock()
        handler_instance.drive.CreateFile.side_effect = None
        handler_instance.drive.CreateFile.return_value = item
        handler_instance.delete_item("drive-id")
        item.Delete.assert_called_once()

    def test_delete_item_error(self, handler_instance):
        handler_instance.drive.CreateFile.side_effect = Exception("error")
        with pytest.raises(RuntimeError):
            handler_instance.delete_item("drive-id")


class TestFolderUploadThread:
    def test_start_and_wait(self, tmp_path, handler_instance):
        folder = tmp_path / "test"
        folder.mkdir()
        handler_instance.drive.CreateFile.side_effect = None
        handler_instance.drive.CreateFile.return_value = make_file(file_id="folder-id")
        handler_instance.start_folder_upload(folder, "parent-id")
        result = handler_instance.wait_for_folder_upload()
        assert result == "folder-id"

    def test_double_start_fails(self, tmp_path, handler_instance):
        folder = tmp_path / "test"
        folder.mkdir()
        handler_instance.start_folder_upload(folder, "parent-id")
        with pytest.raises(RuntimeError, match="ongoing folder upload"):
            handler_instance.start_folder_upload(folder, "parent-id")
        handler_instance.wait_for_folder_upload()

    def test_cancel_with_undo(self, tmp_path, handler_instance):
        folder = tmp_path / "test"
        folder.mkdir()
        handler_instance.drive.CreateFile.side_effect = None
        handler_instance.drive.CreateFile.return_value = make_file(file_id="folder-id")
        handler_instance.start_folder_upload(folder, "parent-id")
        with patch.object(handler_instance, "delete_item") as delete_item:
            handler_instance.cancel_folder_upload(undo=True)
            delete_item.assert_called_once_with("folder-id")

    def test_cancel_reraises(self, handler_instance):
        handler_instance._folder_upload_error = RuntimeError("error")
        handler_instance._folder_upload_thread = threading.Thread(target=lambda: time.sleep(0.1), daemon=True)
        handler_instance._folder_upload_thread.start()
        with pytest.raises(RuntimeError, match="error"):
            handler_instance.cancel_folder_upload()
        handler_instance._folder_upload_thread.join()

    def test_wait_reraises(self, handler_instance):
        handler_instance._folder_upload_error = RuntimeError("error")
        with pytest.raises(RuntimeError, match="error"):
            handler_instance.wait_for_folder_upload()