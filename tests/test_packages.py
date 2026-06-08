"""Test that all package __init__.py and __main__.py files import correctly."""


class TestBackupInit:
    def test_import_backup(self):
        from backup import Backup
        assert Backup is not None

    def test_all_exports(self):
        from backup import __all__
        assert "Backup" in __all__


class TestDashboardInit:
    def test_import_dashboard(self):
        import dashboard
        assert dashboard is not None


class TestAutoBackupInit:
    def test_import_autobackup(self):
        import AutoBackup
        assert AutoBackup is not None


class TestAutoBackupMain:
    def test_import_main(self):
        import AutoBackup.__main__
        assert AutoBackup.__main__ is not None
