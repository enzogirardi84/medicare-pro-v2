# MediCare Enterprise PRO

[![Pytest](https://github.com/enzogirardi84/medicare-pro-v2/actions/workflows/pytest.yml/badge.svg?branch=main)](https://github.com/enzogirardi84/medicare-pro-v2/actions/workflows/pytest.yml)

Sistema de gestion clinica y domiciliaria en Streamlit.

## Modulos principales

- Admision y pacientes
- Clinica, evolucion y signos vitales (plan de enfermeria integrado en Evolucion)
- Recetas con firma y trazabilidad legal
- Estudios y adjuntos
- Emergencias y ambulancia
- Escalas clinicas
- PDF, consentimientos y respaldo clinico
- RRHH, fichajes y auditoria

## Requisitos

Instalar dependencias:

```bash
pip install -r requirements.txt
```

### Desarrollo y tests (opcional)

Para ejecutar la suite de pruebas en local o alinear con GitHub Actions:

```bash
pip install -r requirements-dev.txt
pytest
```

Opciones de pytest: `pyproject.toml` → `[tool.pytest.ini_options]`.

En produccion (Streamlit Cloud, Render) solo se usa `requirements.txt`.

El archivo `.python-version` y `runtime.txt` indican Python 3.12.x para entornos locales y Render.

## Ejecucion local

```bash
streamlit run main.py
```

## Deploy con dominio propio

La app tambien queda preparada para desplegarse en Render con dominio personalizado.

Archivos incluidos:

- `render.yaml`
- `runtime.txt`

Comando de arranque configurado:

```bash
streamlit run main.py --server.port $PORT --server.address 0.0.0.0
```

La guia paso a paso para Render + Donweb esta en:

- `DEPLOY_GUIDE.md`

## Configuracion

Si se quiere usar Supabase, crear:

`.streamlit/secrets.toml`

con variables como:

```toml
SUPABASE_URL="https://TU-PROYECTO.supabase.co"
SUPABASE_KEY="TU_KEY"
# URL publica HTTPS sin barra final (SEO, canonical, redireccion apex→www)
SITE_URL="https://www.tu-dominio.com"
```

Si Supabase no esta configurado, la app funciona en modo local.

## Datos locales

Los datos locales no se versionan. Se guardan en:

- `.streamlit/local_data.json`
- `.streamlit/data_store/`

## Nota

Este proyecto esta preparado para compararse con una version anterior sin reemplazarla.
