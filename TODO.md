## Rewrite tests

Existing tests are bumass garbage; planning to:

[ ] Fully rewrite `test_drive.py` because the mocks look fucking abhorrent.

[ ] Replace `test_dashboard_app.py` and `test_dashboard_runner.py` with a fully rewritten `test_dashboard.py` that tests both
    - since the mocks are ugly and `runner.py` kinda depends on `app.py`.

[x] Refactor `test_backup.py` to merge edge-case classes

[x] Add a `test_startup.py`  to test `src/startup/`
