"""Test that all package __init__.py and __main__.py files import correctly."""


class TestBackup:
    def test_init(self):
        import backup
        assert backup is not None

    def test_all_exports(self):
        from backup import Backup, DriveHandler
        assert Backup is not None and DriveHandler is not None


class TestDashboard:
    def test_init(self):
        import dashboard
        assert dashboard is not None

    def test_all_exports(self):
        from dashboard import run_app, set_backup_configs_dir
        assert run_app is not None and set_backup_configs_dir is not None


class TestAutoBackup:
    def test_init(self):
        import AutoBackup
        assert AutoBackup is not None

    def test_main(self):
        import AutoBackup.__main__
        assert AutoBackup.__main__ is not None
