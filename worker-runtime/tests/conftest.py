import platform
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

# The historical full-report test contains assertions intentionally specific to
# KARMO-DEV01 (Darwin/arm64). Keep it active on that machine, but do not fake
# Apple-Silicon identity on an x86_64 Linux CI host. Portable host-truth
# coverage is provided by test_portability.py and runs everywhere.
_DEV01_ONLY_TEST = "test_resource_discovery_full_report_runs_without_error"


def pytest_collection_modifyitems(config, items):
    is_karmo_dev01_class = platform.system() == "Darwin" and platform.machine() == "arm64"
    if is_karmo_dev01_class:
        return

    marker = pytest.mark.skip(
        reason="KARMO-DEV01-specific Darwin/arm64 assertions; portable host-truth tests run separately"
    )
    for item in items:
        if item.name == _DEV01_ONLY_TEST:
            item.add_marker(marker)
