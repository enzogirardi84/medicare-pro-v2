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

## Opcion 3: Render con dominio propio

La app ya queda preparada para Render con estos archivos:

- `render.yaml`
- `runtime.txt`

### Crear el servicio en Render

1. Entrar a [Render Dashboard](https://dashboard.render.com/)
2. Elegir `New +`
3. Crear `Web Service`
4. Conectar el repo:
   - `enzogirardi84/medicare-pro-v2`
5. Si Render detecta `render.yaml`, tomar la configuracion sugerida

### Variables de entorno

Agregar en Render:

```text
SUPABASE_URL=https://TU-PROYECTO.supabase.co
SUPABASE_KEY=TU_CLAVE_PUBLICABLE_O_SERVICE
```

### Dominio propio con Donweb

Recomendacion: usar subdominio. Ejemplos:

- `app.tudominio.com`
- `sistema.tudominio.com`

Pasos:

1. En Render, abrir el servicio desplegado
2. Ir a `Settings > Custom Domains`
3. Agregar el dominio o subdominio deseado
4. Render te va a mostrar el destino DNS real
5. En Donweb, crear el registro DNS indicado por Render

Casos habituales:

- Si usas subdominio: crear un `CNAME`
- Si usas dominio raiz: usar los registros `A` o la opcion que Render indique

### Recomendacion practica

Para evitar complicaciones con DNS del dominio raiz en Donweb:

1. dejar el dominio principal para la web institucional
2. usar `app.tudominio.com` para MediCare

### SSL

Render genera HTTPS automaticamente una vez que el dominio apunta bien y termina la verificacion.

## Recomendacion real

- Streamlit Cloud para la interfaz
- Supabase Database para tablas
- Supabase Storage para PDFs, firmas e imagenes
- Si queres dominio propio real, usar Render + Supabase
