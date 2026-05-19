---
name: webapp-testing
description: Testing de apps Streamlit con pytest.
---

# Testing Streamlit Apps

## Stack
- pytest 8+ con `pytest.ini` ya configurado
- `tests/conftest.py` mockea `streamlit` module globalmente
- CI ejecuta `pytest tests/ -q --tb=short`

## Reglas
- Usar `monkeypatch` para mockear `st.session_state`
- Nunca importar streamlit directamente en tests (conftest lo maneja)
- Tests de integración en `tests/integration/`
- Usar `--import-mode=importlib` en pytest para evitar conflictos de import

## Patrón común
```python
def test_algo(monkeypatch):
    fake_state = {}
    monkeypatch.setattr("streamlit.session_state", fake_state, raising=False)
    from core.utils import mi_funcion
    resultado = mi_funcion()
    assert resultado == esperado
```

## CI
- GitHub Actions en `.github/workflows/pytest.yml`
- Lint: Ruff + Black + mypy en `.github/workflows/medicare-lint.yml`
