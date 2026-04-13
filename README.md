# MediCare Enterprise PRO

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
```

Si Supabase no esta configurado, la app funciona en modo local.

## Datos locales

Los datos locales no se versionan. Se guardan en:

- `.streamlit/local_data.json`
- `.streamlit/data_store/`

## Nota

Este proyecto esta preparado para compararse con una version anterior sin reemplazarla.
