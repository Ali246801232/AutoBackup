"""Test that all package __init__.py and __main__.py files import correctly."""


class TestBackup:
    def test_import_backup_init(self):
        import backup
        assert backup is not None

    def test_all_exports(self):
        from backup import Backup, DriveHandler
        assert Backup is not None and DriveHandler is not None


class TestDashboard:
    def test_import_dashboard_init(self):
        import dashboard
        assert dashboard is not None

    def test_import_dashboard_main(self):
        import dashboard.__main__
        assert dashboard.__main__ is not None


class TestAutoBackup:
    def test_import_autobackup_init(self):
        import AutoBackup
        assert AutoBackup is not None

    def test_import_autobackup_main(self):
        import AutoBackup.__main__
        assert AutoBackup.__main__ is not None
