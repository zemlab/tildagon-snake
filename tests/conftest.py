import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
STUBS_DIR = Path(__file__).parent / "badge_stubs"

# The badge-firmware modules (app, app_components, events.*, system.*) don't
# exist off-badge. Put local stubs on sys.path ahead of everything else so
# `import app` etc. inside the app under test resolve to them.
sys.path.insert(0, str(STUBS_DIR))


def _load_app_module():
    # Loaded under a name other than "app" - the repo's own file is also
    # called app.py, and it does `import app` to reach the *stub* module
    # above, so the module under test can't itself be registered as "app".
    spec = importlib.util.spec_from_file_location("snake_app_under_test", REPO_ROOT / "app.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def snake_module():
    return _load_app_module()


@pytest.fixture(autouse=True)
def _reset_eventbus():
    from system.eventbus import eventbus

    eventbus.emitted.clear()
    yield
    eventbus.emitted.clear()
