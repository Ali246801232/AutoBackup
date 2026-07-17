"""Test that all package __init__.py and __main__.py files import correctly."""


class TestAutoBackup:
    def test_init(self):
        import AutoBackup
        assert AutoBackup is not None

    def test_main(self):
        import AutoBackup.__main__
        assert AutoBackup.__main__ is not None


class TestBackup:
    def test_init(self):
        from AutoBackup import backup
        assert backup is not None

    def test_exports(self):
        from AutoBackup.backup import Backup, DriveHandler
        assert Backup is not None
        assert DriveHandler is not None


class TestDashboard:
    def test_init(self):
        from AutoBackup import dashboard
        assert dashboard is not None

    def test_exports(self):
        from AutoBackup.dashboard import run_app
        assert run_app is not None


class TestStartup:
    def test_init(self):
        from AutoBackup import startup
        assert startup is not None
    
    def test_exports(self):
        from AutoBackup.startup import is_in_startup, add_to_startup, remove_from_startup
        assert is_in_startup is not None
        assert add_to_startup is not None
        assert remove_from_startup is not None
