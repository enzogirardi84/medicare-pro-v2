"""Tests para core.db_paginated."""
from __future__ import annotations

import pytest


class TestDbPaginated:
    """Tests para funciones públicas de core.db_paginated."""

    def test_db_paginated_importable(self):
        import core.db_paginated
        assert core.db_paginated is not None

    def test_functions_exist(self):
        import core.db_paginated
        assert callable(core.db_paginated.get_paginated_patients)
        assert callable(core.db_paginated.query_paginated)
        assert callable(core.db_paginated.search_paginated)
