# Deploy Guide

## Opcion 1: Streamlit Community Cloud

La app ya esta subida al repo:

- `https://github.com/enzogirardi84/medicare-pro-v2`

Pasos:

1. Entrar a [Streamlit Community Cloud](https://share.streamlit.io/)
2. Elegir `New app`
3. Seleccionar:
   - Repository: `enzogirardi84/medicare-pro-v2`
   - Branch: `main`
   - Main file path: `main.py`
4. En `Advanced settings` cargar secrets:

```toml
SUPABASE_URL="https://TU-PROYECTO.supabase.co"
SUPABASE_KEY="TU_SERVICE_OR_ANON_KEY"
```

Si no completas esas variables, la app puede arrancar en modo local, pero en Streamlit Cloud no conviene depender de almacenamiento local para produccion.

## Opcion 2: Supabase

En la carpeta `supabase/` quedan archivos listos para usar:

- `schema.sql`
- `storage.sql`
- `README.md`

### Fase 1

Crear la tabla `medicare_db` para compatibilidad inmediata con la version actual del codigo.

### Fase 2

Migrar a las tablas normalizadas para soportar mejor miles de pacientes y archivos grandes.

## Recomendacion real

- Streamlit Cloud para la interfaz
- Supabase Database para tablas
- Supabase Storage para PDFs, firmas e imagenes
