import sys
from unittest.mock import MagicMock

# modules that can't be imported in headless environments; patched properly in test_*.py files
_HEADLESS_MOCKS = {"pystray", "webview", "notifypy"}
for _mod in _HEADLESS_MOCKS:
    sys.modules.setdefault(_mod, MagicMock())
