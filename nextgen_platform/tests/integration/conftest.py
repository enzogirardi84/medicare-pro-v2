import os

import pytest


def pytest_collection_modifyitems(config, items):
    if os.getenv("NEXTGEN_BASE_URL", "").strip():
        return
    skip_integration = pytest.mark.skip(reason="Set NEXTGEN_BASE_URL to run integration contract tests.")
    for item in items:
        if "integration" in item.path.parts:
            item.add_marker(skip_integration)
