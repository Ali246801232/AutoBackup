import json
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _reset_backups():
    import dashboard.app
    old = dashboard.app.BACKUPS, dashboard.app.BACKUP_CONFIGS_DIR
    dashboard.app.BACKUPS = {}
    dashboard.app.BACKUP_CONFIGS_DIR = None
    yield
    dashboard.app.BACKUPS, dashboard.app.BACKUP_CONFIGS_DIR = old


@pytest.fixture
def client():
    import dashboard.app
    dashboard.app.app.config["TESTING"] = True
    with dashboard.app.app.test_client() as c:
        yield c


@pytest.fixture
def setup_backups(tmp_path):
    import dashboard.app
    configs_dir = tmp_path / "configs"
    configs_dir.mkdir()
    dashboard.app.BACKUP_CONFIGS_DIR = configs_dir
    yield configs_dir


@pytest.fixture
def valid_backup_dict(tmp_source_dir, tmp_dest_dir):
    return {
        "config_name": "test_config",
        "sources": [str(tmp_source_dir)],
        "destination": str(tmp_dest_dir),
        "exclusions": [],
        "schedule": None,
        "drive_upload": False,
        "drive_folder_id": None,
        "last_scheduled_attempt": None,
    }


@pytest.fixture
def created_backup(client, setup_backups, valid_backup_dict):
    resp = client.post("/api/backups/create_backup", json=valid_backup_dict)
    assert resp.status_code == 201
    return resp.get_json()


class TestCreateBackup:
    def test_create_success(self, client, setup_backups, valid_backup_dict):
        resp = client.post("/api/backups/create_backup", json=valid_backup_dict)
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["config_name"] == "test_config"
        assert "sources" in data

    def test_create_no_body(self, client, setup_backups):
        resp = client.post("/api/backups/create_backup", content_type="application/json", data="{}")
        assert resp.status_code == 400

    def test_create_no_config_name(self, client, setup_backups):
        resp = client.post("/api/backups/create_backup", json={"sources": ["/x"], "destination": "/y"})
        assert resp.status_code == 400
        assert "config name" in resp.get_json()["error"].lower()

    def test_create_no_sources(self, client, setup_backups):
        resp = client.post("/api/backups/create_backup", json={"config_name": "x", "destination": "/y"})
        assert resp.status_code == 400
        assert "source" in resp.get_json()["error"].lower()

    def test_create_no_destination(self, client, setup_backups):
        resp = client.post("/api/backups/create_backup", json={"config_name": "x", "sources": ["/y"]})
        assert resp.status_code == 400
        assert "destination" in resp.get_json()["error"].lower()

    def test_create_duplicate(self, client, setup_backups, created_backup, valid_backup_dict):
        resp = client.post("/api/backups/create_backup", json=valid_backup_dict)
        assert resp.status_code == 409

    def test_create_verify_failure(self, client, setup_backups):
        resp = client.post("/api/backups/create_backup", json={
            "config_name": "bad",
            "sources": ["/nonexistent_source"],
            "destination": "/nonexistent_dest",
        })
        assert resp.status_code == 400

    def test_create_saves_to_disk(self, client, setup_backups, valid_backup_dict):
        resp = client.post("/api/backups/create_backup", json=valid_backup_dict)
        assert resp.status_code == 201
        config_file = setup_backups / "test_config.json"
        assert config_file.exists()
        data = json.loads(config_file.read_text())
        assert data["config_name"] == "test_config"


class TestListBackups:
    def test_empty(self, client, setup_backups):
        resp = client.get("/api/backups/")
        assert resp.status_code == 200
        assert resp.get_json() == {}

    def test_with_backups(self, client, setup_backups, created_backup):
        resp = client.get("/api/backups/")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "test_config" in data
        assert data["test_config"]["config_name"] == "test_config"


class TestGetStatus:
    def test_exists(self, client, setup_backups, created_backup):
        resp = client.get("/api/backups/test_config/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "backup_running" in data
        assert data["backup_running"] is False

    def test_not_found(self, client, setup_backups):
        resp = client.get("/api/backups/nonexistent/status")
        assert resp.status_code == 404


class TestUpdateBackup:
    def test_update_name(self, client, setup_backups, created_backup, valid_backup_dict):
        update = dict(valid_backup_dict)
        update["config_name"] = "renamed"
        resp = client.post("/api/backups/test_config/save_backup", json=update)
        assert resp.status_code == 200

        import dashboard.app
        assert "renamed" in dashboard.app.BACKUPS
        assert "test_config" not in dashboard.app.BACKUPS

    def test_update_name_conflict(self, client, setup_backups, created_backup, valid_backup_dict):
        d2 = dict(valid_backup_dict)
        d2["config_name"] = "other"
        client.post("/api/backups/create_backup", json=d2)

        update = dict(valid_backup_dict)
        update["config_name"] = "other"
        resp = client.post("/api/backups/test_config/save_backup", json=update)
        assert resp.status_code == 409

    def test_update_invalid_data(self, client, setup_backups, created_backup):
        resp = client.post("/api/backups/test_config/save_backup", json={"config_name": "test_config", "sources": []})
        assert resp.status_code == 500

    def test_update_not_found(self, client, setup_backups):
        resp = client.post("/api/backups/nonexistent/save_backup", json={"config_name": "x"})
        assert resp.status_code == 404

    def test_update_rolls_back_on_failure(self, client, setup_backups, created_backup, valid_backup_dict):
        import dashboard.app
        update = dict(valid_backup_dict)
        update["config_name"] = "will_fail"
        update["destination"] = "/nonexistent/destination"
        resp = client.post("/api/backups/test_config/save_backup", json=update)
        assert resp.status_code == 500

        assert "test_config" in dashboard.app.BACKUPS
        assert "will_fail" not in dashboard.app.BACKUPS

    def test_update_preserves_data(self, client, setup_backups, created_backup, valid_backup_dict):
        import dashboard.app
        update = dict(valid_backup_dict)
        update["config_name"] = "renamed"
        resp = client.post("/api/backups/test_config/save_backup", json=update)
        assert resp.status_code == 200
        assert "renamed" in dashboard.app.BACKUPS
        assert dashboard.app.BACKUPS["renamed"].config_name == "renamed"


class TestDeleteBackup:
    def test_delete(self, client, setup_backups, created_backup):
        resp = client.post("/api/backups/test_config/delete_backup")
        assert resp.status_code == 200

        import dashboard.app
        assert "test_config" not in dashboard.app.BACKUPS

    def test_delete_not_found(self, client, setup_backups):
        resp = client.post("/api/backups/nonexistent/delete_backup")
        assert resp.status_code == 404

    def test_delete_removes_file(self, client, setup_backups, created_backup):
        config_file = setup_backups / "test_config.json"
        assert config_file.exists()
        resp = client.post("/api/backups/test_config/delete_backup")
        assert resp.status_code == 200
        assert not config_file.exists()


class TestStartCancelBackup:
    def test_start_backup(self, client, setup_backups, created_backup):
        import dashboard.app
        with patch.object(dashboard.app.Backup, "start_backup") as mock_start:
            resp = client.post("/api/backups/test_config/start_backup")
            assert resp.status_code == 202
            mock_start.assert_called_once()

    def test_start_backup_not_found(self, client, setup_backups):
        resp = client.post("/api/backups/nonexistent/start_backup")
        assert resp.status_code == 404

    def test_cancel_backup(self, client, setup_backups, created_backup):
        import dashboard.app
        with patch.object(dashboard.app.Backup, "cancel_backup") as mock_cancel:
            resp = client.post("/api/backups/test_config/cancel_backup")
            assert resp.status_code == 200
            mock_cancel.assert_called_once()

    def test_cancel_not_found(self, client, setup_backups):
        resp = client.post("/api/backups/nonexistent/cancel_backup")
        assert resp.status_code == 404


class TestSchedulerAPI:
    def test_start_scheduler(self, client, setup_backups, created_backup):
        import dashboard.app
        with patch.object(dashboard.app.Backup, "start_scheduler") as mock_start:
            resp = client.post("/api/backups/test_config/start_scheduler")
            assert resp.status_code == 202
            mock_start.assert_called_once()

    def test_start_not_found(self, client, setup_backups):
        resp = client.post("/api/backups/nonexistent/start_scheduler")
        assert resp.status_code == 404

    def test_stop_scheduler(self, client, setup_backups, created_backup):
        import dashboard.app
        with patch.object(dashboard.app.Backup, "stop_scheduler") as mock_stop:
            resp = client.post("/api/backups/test_config/stop_scheduler")
            assert resp.status_code == 200
            mock_stop.assert_called_once()

    def test_stop_not_found(self, client, setup_backups):
        resp = client.post("/api/backups/nonexistent/stop_scheduler")
        assert resp.status_code == 404


class TestPages:
    def test_index_page(self, client):
        import dashboard.app
        with patch.object(dashboard.app, "render_template", return_value="<html>index</html>"):
            resp = client.get("/")
            assert resp.status_code == 200

    def test_config_editor_page(self, client):
        import dashboard.app
        with patch.object(dashboard.app, "render_template", return_value="<html>editor</html>"):
            resp = client.get("/config_editor")
            assert resp.status_code == 200


class TestLoadBackups:
    def test_load_backups(self, tmp_path):
        from dashboard.app import load_backups
        configs_dir = tmp_path / "configs"
        configs_dir.mkdir()
        config = {
            "config_name": "loaded",
            "sources": [str(tmp_path)],
            "destination": str(tmp_path),
            "exclusions": [],
            "schedule": None,
            "drive_upload": False,
            "drive_folder_id": None,
            "last_scheduled_attempt": None,
        }
        (configs_dir / "loaded.json").write_text(json.dumps(config))
        backups = load_backups(configs_dir)
        assert "loaded" in backups
        assert backups["loaded"].config_name == "loaded"

    def test_load_backups_skips_non_json(self, tmp_path):
        from dashboard.app import load_backups
        configs_dir = tmp_path / "configs"
        configs_dir.mkdir()
        (configs_dir / "not_json.txt").write_text("{}")
        result = load_backups(configs_dir)
        assert result == {}

    def test_load_backups_dir_not_exist(self, tmp_path):
        from dashboard.app import load_backups
        with pytest.raises(ValueError, match="No config files directory at"):
            load_backups(tmp_path / "nonexistent")


class TestSaveBackups:
    def test_save_backups(self, tmp_path, backup_instance):
        from dashboard.app import save_backups
        configs_dir = tmp_path / "configs"
        configs_dir.mkdir()
        save_backups({"test": backup_instance}, configs_dir)
        assert (configs_dir / "test.json").exists()
        data = json.loads((configs_dir / "test.json").read_text())
        assert data["config_name"] == "test_backup"

    def test_save_backups_dir_not_exist(self, tmp_path, backup_instance):
        from dashboard.app import save_backups
        with pytest.raises(ValueError, match="No config files directory at"):
            save_backups({"test": backup_instance}, tmp_path / "nonexistent")


class TestErrorHandling:
    def test_create_server_error(self, client, setup_backups):
        import dashboard.app
        with patch.object(dashboard.app.Backup, "from_dict", side_effect=Exception("unexpected")):
            resp = client.post("/api/backups/create_backup", json={
                "config_name": "x", "sources": ["/a"], "destination": "/b",
            })
            assert resp.status_code == 500
