import threading
from unittest.mock import MagicMock, patch

import pytest
from backup.drive import DriveHandler, CancelledError


@pytest.fixture
def mock_google():
    with (
        patch("backup.drive.GoogleAuth") as MockGA,
        patch("backup.drive.GoogleDrive") as MockGD,
    ):
        gauth = MagicMock()
        gauth.settings = {}
        gauth.access_token_expired = False
        gauth.credentials = MagicMock()
        MockGA.return_value = gauth

        gdrive = MagicMock()
        MockGD.return_value = gdrive

        file_mock = MagicMock()
        file_mock.__getitem__ = MagicMock(side_effect=lambda k: "root" if k == "id" else MagicMock())
        file_mock.__setitem__ = MagicMock()
        file_mock.FetchMetadata = MagicMock()
        gdrive.CreateFile.return_value = file_mock

        gdrive.ListFile.return_value.GetList.return_value = []

        yield MockGA, MockGD, gauth, gdrive, file_mock


@pytest.fixture
def handler(mock_google):
    _, _, _, _, file_mock = mock_google
    h = DriveHandler()
    h.authenticate()
    h.current_folder = file_mock
    return h


class TestInit:
    def test_authenticate_mocked(self, mock_google):
        MockGA, MockGD, _, _, _ = mock_google
        h = DriveHandler()
        h.authenticate()
        assert MockGA.called
        assert MockGD.called
        assert h.current_folder is not None

    def test_authenticate_failure(self):
        with patch("backup.drive.GoogleAuth", side_effect=Exception("auth fail")):
            with pytest.raises(RuntimeError, match="Failed to authenticate"):
                h = DriveHandler()
                h.authenticate()


class TestFolderNavigation:
    def test_open_folder(self, handler, mock_google):
        _, _, _, gdrive, _ = mock_google
        new_mock = MagicMock()
        new_mock.__getitem__ = MagicMock(side_effect=lambda k: "abc" if k == "id" else MagicMock())
        new_mock.FetchMetadata = MagicMock()
        gdrive.CreateFile.return_value = new_mock

        result = handler.open_folder("abc")
        gdrive.CreateFile.assert_called_with({"id": "abc"})
        assert result == new_mock

    def test_go_up(self, handler):
        parent_mock = MagicMock()
        parent_mock.__getitem__ = MagicMock(side_effect=lambda k: "parent_id" if k == "id" else MagicMock())
        parent_mock.FetchMetadata = MagicMock()
        handler.current_folder = MagicMock()
        handler.current_folder.__getitem__ = MagicMock(return_value=[{"id": "parent_id"}])
        handler.drive.CreateFile = MagicMock(return_value=parent_mock)

        result = handler.go_up()
        handler.drive.CreateFile.assert_called_with({"id": "parent_id"})
        assert result == parent_mock

    def test_go_up_no_parent(self, handler):
        handler.current_folder = MagicMock()
        handler.current_folder.__getitem__ = MagicMock(return_value=[])
        result = handler.go_up()
        assert result == handler.current_folder

    def test_go_to_root(self, handler, mock_google):
        _, _, _, gdrive, _ = mock_google
        handler.drive = gdrive
        handler.go_to_root()
        gdrive.CreateFile.assert_called_with({"id": "root"})


class TestGetChildren:
    def test_get_children_no_query(self, handler, mock_google):
        _, _, _, gdrive, _ = mock_google
        handler.current_folder = MagicMock()
        handler.current_folder.__getitem__ = MagicMock(return_value="folder_id")
        handler.drive = gdrive
        gdrive.ListFile.return_value.GetList.return_value = [
            {"title": "b.txt"},
            {"title": "a.txt"},
        ]

        children = handler.get_children()
        gdrive.ListFile.assert_called_once()
        q = gdrive.ListFile.call_args[0][0]["q"]
        assert "'folder_id' in parents" in q
        assert "trashed = false" in q
        assert children == sorted(children, key=lambda x: x.get("title", "").lower())

    def test_get_children_with_query(self, handler, mock_google):
        _, _, _, gdrive, _ = mock_google
        handler.current_folder = MagicMock()
        handler.current_folder.__getitem__ = MagicMock(return_value="fid")
        handler.drive = gdrive

        handler.get_children(query="mimeType = 'folder'")
        q = gdrive.ListFile.call_args[0][0]["q"]
        assert "mimeType = 'folder'" in q

    def test_get_children_specific_folder(self, handler, mock_google):
        _, _, _, gdrive, _ = mock_google
        handler.drive = gdrive
        handler.get_children(folder_id="specific_id")
        q = gdrive.ListFile.call_args[0][0]["q"]
        assert "'specific_id' in parents" in q

    def test_get_children_api_error(self, handler, mock_google):
        import json
        from googleapiclient.errors import HttpError
        from pydrive2.files import ApiRequestError

        _, _, _, gdrive, _ = mock_google
        handler.current_folder = MagicMock()
        handler.current_folder.__getitem__ = MagicMock(return_value="fid")
        handler.drive = gdrive

        resp = MagicMock()
        resp.status = 500
        content = json.dumps({"error": "API error"}).encode()
        http_error = HttpError(resp, content)
        api_error = ApiRequestError(http_error)

        gdrive.ListFile.side_effect = api_error
        with pytest.raises(RuntimeError, match="Failed to fetch children"):
            handler.get_children()

    def test_get_child_folders(self, handler, mock_google):
        _, _, _, gdrive, _ = mock_google
        handler.current_folder = MagicMock()
        handler.current_folder.__getitem__ = MagicMock(return_value="fid")
        handler.drive = gdrive

        with patch.object(handler, "get_children", wraps=handler.get_children) as spy:
            handler.get_child_folders()
            spy.assert_called_with(None, query="mimeType = 'application/vnd.google-apps.folder'")

    def test_get_child_files(self, handler, mock_google):
        _, _, _, gdrive, _ = mock_google
        handler.current_folder = MagicMock()
        handler.current_folder.__getitem__ = MagicMock(return_value="fid")
        handler.drive = gdrive

        with patch.object(handler, "get_children", wraps=handler.get_children) as spy:
            handler.get_child_files()
            spy.assert_called_with(None, query="mimeType != 'application/vnd.google-apps.folder'")


class TestGetItem:
    def test_get_item(self, handler, mock_google):
        _, _, _, gdrive, _ = mock_google
        item = MagicMock()
        handler.drive = gdrive
        gdrive.CreateFile.return_value = item

        result = handler.get_item("item_id")
        gdrive.CreateFile.assert_called_with({"id": "item_id"})
        item.FetchMetadata.assert_called_once()
        assert result == item


class TestUploadFile:
    def test_upload_file(self, handler, mock_google, tmp_path):
        _, _, _, gdrive, _ = mock_google
        handler.drive = gdrive
        fp = tmp_path / "test.txt"
        fp.write_text("data")
        file_mock = MagicMock()
        file_mock.__getitem__ = MagicMock(return_value="uploaded_id")
        gdrive.CreateFile.return_value = file_mock

        result = handler.upload_file(fp, "parent_id")
        assert result == "uploaded_id"
        gdrive.CreateFile.assert_called_with(metadata={"parents": [{"id": "parent_id"}]})
        file_mock.SetContentFile.assert_called_with(fp)
        file_mock.Upload.assert_called_once()

    def test_upload_file_nonexistent(self, handler, tmp_path):
        fp = tmp_path / "nonexistent.txt"
        with pytest.raises(ValueError, match="not a file"):
            handler.upload_file(fp, "pid")

    def test_upload_file_api_error(self, handler, mock_google, tmp_path):
        import json
        from googleapiclient.errors import HttpError
        from pydrive2.files import ApiRequestError

        _, _, _, gdrive, _ = mock_google
        handler.drive = gdrive
        fp = tmp_path / "test.txt"
        fp.write_text("data")

        resp = MagicMock()
        resp.status = 500
        content = json.dumps({"error": "upload fail"}).encode()
        http_error = HttpError(resp, content)
        api_error = ApiRequestError(http_error)

        file_mock = MagicMock()
        file_mock.Upload.side_effect = api_error
        gdrive.CreateFile.return_value = file_mock

        with pytest.raises(RuntimeError, match="Failed to upload file"):
            handler.upload_file(fp, "pid")


class TestUploadFolder:
    def test_upload_root_folder(self, handler, mock_google, tmp_path):
        _, _, _, gdrive, _ = mock_google
        handler.drive = gdrive
        folder = tmp_path / "myfolder"
        folder.mkdir()
        (folder / "a.txt").write_text("a")

        drive_folder_mock = MagicMock()
        drive_folder_mock.__getitem__ = MagicMock(side_effect=lambda k: "new_folder_id" if k == "id" else "MyFolder")
        drive_folder_mock.Upload = MagicMock()
        gdrive.CreateFile.return_value = drive_folder_mock

        result = handler.upload_folder(folder, "parent_id")
        assert result == "new_folder_id"
        assert handler._folder_upload_root_id == "new_folder_id"

    def test_upload_folder_not_exists(self, handler, tmp_path):
        with pytest.raises(ValueError, match="does not exist"):
            handler.upload_folder(tmp_path / "nonexistent", "pid")

    def test_upload_folder_is_file(self, handler, tmp_path):
        fp = tmp_path / "file.txt"
        fp.write_text("x")
        with pytest.raises(ValueError, match="not a directory"):
            handler.upload_folder(fp, "pid")

    def test_upload_folder_cancelled(self, handler, mock_google, tmp_path):
        _, _, _, gdrive, _ = mock_google
        handler.drive = gdrive
        folder = tmp_path / "myfolder"
        folder.mkdir()

        drive_folder_mock = MagicMock()
        drive_folder_mock.__getitem__ = MagicMock(side_effect=lambda k: "fid" if k == "id" else "MyFolder")
        drive_folder_mock.Upload = MagicMock()
        gdrive.CreateFile.return_value = drive_folder_mock
        handler._cancel_folder_upload_event.set()

        with pytest.raises(CancelledError):
            handler.upload_folder(folder, "parent_id")
        handler._cancel_folder_upload_event.clear()

    def test_upload_subfolder_cancelled(self, handler, mock_google, tmp_path):
        _, _, _, gdrive, _ = mock_google
        handler.drive = gdrive
        folder = tmp_path / "myfolder"
        folder.mkdir()
        (folder / "sub").mkdir()

        gdrive.CreateFile.side_effect = [
            MagicMock(**{
                "__getitem__.__getitem__.return_value": "fid",
                "Upload": MagicMock()
            }),
            MagicMock(**{
                "__getitem__.__getitem__.return_value": "sub_folder_id",
                "Upload": MagicMock()
            }),
        ]
        handler._cancel_folder_upload_event.set()

        with pytest.raises(CancelledError):
            handler.upload_folder(folder, "parent_id")
        handler._cancel_folder_upload_event.clear()

    def test_upload_subfolder_api_error_logged(self, handler, mock_google, tmp_path):
        _, _, _, gdrive, _ = mock_google
        handler.drive = gdrive
        folder = tmp_path / "myfolder"
        folder.mkdir()
        sub = folder / "sub"
        sub.mkdir()
        (sub / "f.txt").write_text("x")

        root_folder_mock = MagicMock()
        root_folder_mock.__getitem__ = MagicMock(side_effect=lambda k: "fid" if k == "id" else "MyFolder")
        root_folder_mock.Upload = MagicMock()
        gdrive.CreateFile.side_effect = [root_folder_mock, Exception("API error")]

        result = handler.upload_folder(folder, "parent_id")
        assert result == "fid"


class TestDeleteTrash:
    def test_trash_item(self, handler, mock_google):
        _, _, _, gdrive, _ = mock_google
        handler.drive = gdrive
        item = MagicMock()
        gdrive.CreateFile.return_value = item

        handler.trash_item("item_id")
        gdrive.CreateFile.assert_called_with({"id": "item_id"})
        item.Trash.assert_called_once()

    def test_trash_item_error(self, handler, mock_google):
        _, _, _, gdrive, _ = mock_google
        handler.drive = gdrive
        item = MagicMock()
        item.Trash.side_effect = Exception("trash fail")
        gdrive.CreateFile.return_value = item

        with pytest.raises(RuntimeError, match="Failed to trash item"):
            handler.trash_item("item_id")

    def test_delete_item(self, handler, mock_google):
        _, _, _, gdrive, _ = mock_google
        handler.drive = gdrive
        item = MagicMock()
        gdrive.CreateFile.return_value = item

        handler.delete_item("item_id")
        gdrive.CreateFile.assert_called_with({"id": "item_id"})
        item.Delete.assert_called_once()

    def test_delete_item_error(self, handler, mock_google):
        _, _, _, gdrive, _ = mock_google
        handler.drive = gdrive
        item = MagicMock()
        item.Delete.side_effect = Exception("delete fail")
        gdrive.CreateFile.return_value = item

        with pytest.raises(RuntimeError, match="Failed to permanently delete item"):
            handler.delete_item("item_id")


class TestFolderUploadThread:
    def test_start_and_wait(self, handler, mock_google, tmp_path):
        _, _, _, gdrive, _ = mock_google
        handler.drive = gdrive
        folder = tmp_path / "upload"
        folder.mkdir()
        (folder / "f.txt").write_text("x")

        drive_folder_mock = MagicMock()
        drive_folder_mock.__getitem__ = MagicMock(side_effect=lambda k: "folder_id" if k == "id" else "Upload")
        drive_folder_mock.Upload = MagicMock()
        gdrive.CreateFile.return_value = drive_folder_mock

        handler.start_folder_upload(folder, "parent_id")
        result = handler.wait_for_folder_upload()
        assert result == "folder_id"

    def test_double_start_fails(self, handler, mock_google, tmp_path):
        _, _, _, gdrive, _ = mock_google
        handler.drive = gdrive
        folder = tmp_path / "upload"
        folder.mkdir()

        drive_folder_mock = MagicMock()
        drive_folder_mock.__getitem__ = MagicMock(side_effect=lambda k: "fid" if k == "id" else "Upload")
        drive_folder_mock.Upload = MagicMock()
        gdrive.CreateFile.return_value = drive_folder_mock

        blocker = threading.Event()
        handler._folder_upload_thread = threading.Thread(
            target=blocker.wait, daemon=True
        )
        handler._folder_upload_thread.start()

        with pytest.raises(RuntimeError, match="ongoing folder upload"):
            handler.start_folder_upload(folder, "pid")

        blocker.set()
        handler._folder_upload_thread.join()

    def test_cancel_folder_upload(self, handler, mock_google, tmp_path):
        _, _, _, gdrive, _ = mock_google
        handler.drive = gdrive
        folder = tmp_path / "upload"
        folder.mkdir()
        (folder / "f.txt").write_text("x")

        drive_folder_mock = MagicMock()
        drive_folder_mock.__getitem__ = MagicMock(side_effect=lambda k: "fid" if k == "id" else "Upload")
        drive_folder_mock.Upload = MagicMock(side_effect=lambda: handler._cancel_folder_upload_event.wait())
        gdrive.CreateFile.return_value = drive_folder_mock

        handler.start_folder_upload(folder, "pid")
        handler.cancel_folder_upload(undo=False)

    def test_cancel_with_undo(self, handler, mock_google, tmp_path):
        _, _, _, gdrive, _ = mock_google
        handler.drive = gdrive
        folder = tmp_path / "upload"
        folder.mkdir()
        (folder / "f.txt").write_text("x")

        drive_folder_mock = MagicMock()
        drive_folder_mock.__getitem__ = MagicMock(side_effect=lambda k: "fid" if k == "id" else "Upload")
        drive_folder_mock.Upload = MagicMock(side_effect=lambda: handler._cancel_folder_upload_event.wait())
        gdrive.CreateFile.return_value = drive_folder_mock

        with patch.object(handler, "delete_item") as mock_delete:
            handler.start_folder_upload(folder, "pid")
            handler.cancel_folder_upload(undo=True)
        mock_delete.assert_called_once_with("fid")

    def test_cancel_no_thread(self, handler):
        handler._folder_upload_thread = None
        handler.cancel_folder_upload()

    def test_wait_no_thread(self, handler):
        handler._folder_upload_thread = None
        assert handler.wait_for_folder_upload() is None

    def test_folder_upload_error_raised(self, handler, mock_google, tmp_path):
        _, _, _, gdrive, _ = mock_google
        handler.drive = gdrive
        folder = tmp_path / "upload"
        folder.mkdir()

        gdrive.CreateFile.side_effect = Exception("create fail")

        handler.start_folder_upload(folder, "pid")
        with pytest.raises(Exception, match="create fail"):
            handler.wait_for_folder_upload()

    def test_cancel_with_non_cancelled_error(self, handler, mock_google, tmp_path):
        _, _, _, gdrive, _ = mock_google
        handler.drive = gdrive
        folder = tmp_path / "upload"
        folder.mkdir()

        gdrive.CreateFile.side_effect = Exception("real error")

        handler.start_folder_upload(folder, "pid")
        handler._folder_upload_thread.join()
        with pytest.raises(Exception, match="real error"):
            handler.wait_for_folder_upload()
