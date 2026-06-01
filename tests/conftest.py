"""conftest: configuración global de tests para Python 3.14+."""

import asyncio
import sys

# ── Fix 1: Python 3.14+ no permite asyncio.run() dentro de un event loop activo ──
_original_run = asyncio.run

def _patched_run(coro, *, debug=None, loop_factory=None):
    import concurrent.futures
    try:
        asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            kw = {}
            if debug is not None: kw['debug'] = debug
            if loop_factory is not None: kw['loop_factory'] = loop_factory
            return pool.submit(lambda: _original_run(coro, **kw)).result()
    except (RuntimeError, AssertionError):
        kw = {}
        if debug is not None: kw['debug'] = debug
        if loop_factory is not None: kw['loop_factory'] = loop_factory
        return _original_run(coro, **kw)

if sys.version_info >= (3, 14):
    asyncio.run = _patched_run


# ── Fix 2: Marcar tests que requieren servicios externos ──
import pytest

def pytest_collection_modifyitems(items):
    """Marca tests que requieren servicios externos para skip automático."""
    for item in items:
        # Tests con playwright chromiun -> require servidor + navegador
        if 'chromium' in item.nodeid:
            item.add_marker(pytest.mark.skip(
                reason="Requiere servidor Streamlit corriendo + Playwright"))
        # Tests e2e que requieren servidor
        if 'e2e' in str(item.fspath):
            item.add_marker(pytest.mark.skip(
                reason="Requiere servidor Streamlit corriendo"))
        # Tests de integración que requieren DB
        if 'integration' in str(item.fspath):
            item.add_marker(pytest.mark.skip(
                reason="Requiere base de datos externa"))
        # Tests compliance_report_exporter -> requieren asyncpg (DB real)
        if 'compliance_report_exporter' in item.nodeid and 'verify' in item.nodeid or 'to_html' in item.nodeid:
            item.add_marker(pytest.mark.skip(
                reason="Requiere base de datos PostgreSQL externa"))
