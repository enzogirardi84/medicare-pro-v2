# Deploy Guide (Arquitectura NextGen)

Para soportar **millones de usuarios**, Medicare Pro v2 ahora cuenta con una arquitectura distribuida (NextGen) compuesta por:
1. **Frontend:** Streamlit (Medicare Pro v2 original, optimizado)
2. **Backend API:** FastAPI (Maneja el tráfico pesado, validaciones e idempotencia)
3. **Workers:** Celery (Procesa PDFs y WhatsApp en segundo plano)
4. **Bases de Datos:** PostgreSQL (con Sharding/Particionamiento) y Redis (Caché y Colas)

## Opción 1: Despliegue Completo con Docker Compose (Recomendado para Producción)

La forma más fácil de levantar toda la infraestructura en un servidor (AWS, DigitalOcean, Azure) es usando Docker Compose.

1. Clona el repositorio en tu servidor:
```bash
git clone https://github.com/enzogirardi84/medicare-pro-v2.git
cd medicare-pro-v2
```

2. Levanta toda la arquitectura NextGen:
```bash
docker compose up -d --build
```

Esto levantará:
- **Streamlit** en el puerto `8501`
- **FastAPI** en el puerto `8000`
- **PostgreSQL** en el puerto `5432`
- **Redis** en el puerto `6379`
- **Celery Worker** en segundo plano

## Opción 2: Streamlit Community Cloud (Solo Frontend)

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

### Jira (opcional)

Para la pestaña **Jira** en `Proyecto y Roadmap`, agrega en los mismos secrets:

```toml
[jira]
base_url = "https://tu-empresa.atlassian.net"
email = "tu@correo.com"
api_token = "TOKEN_API_ATLASSIAN"
jql = "project = CLAVE ORDER BY updated DESC"
board_url = "https://tu-empresa.atlassian.net/jira/software/c/projects/CLAVE/boards/1"
max_issues = 25
```

Si omitis este bloque, la pestaña muestra instrucciones y la app sigue funcionando igual.

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

### Medicare Billing Pro en internet

`render.yaml` define dos servicios web:

- `medicare-enterprise-pro`: la app principal.
- `medicare-billing-pro`: Billing Pro, ejecutado desde `medicare_billing_pro/main.py`.

Para que todo quede en Supabase y no dependa de archivos locales, configurar en Render:

```text
SUPABASE_URL=https://TU-PROYECTO.supabase.co
SUPABASE_KEY=TU_CLAVE_PUBLICABLE_O_SERVICE
SUPABASE_SERVICE_ROLE_KEY=TU_SERVICE_ROLE_KEY
BILLING_ALLOW_LOCAL_FALLBACK=false
BILLING_SECRET=valor-seguro-generado-para-produccion
```

Usar `SUPABASE_SERVICE_ROLE_KEY` en Render/Streamlit porque Billing Pro corre del lado servidor. Esto permite guardar en tablas con RLS sin crear politicas publicas para la anon key.

En el servicio principal, configurar además:

```text
BILLING_APP_URL=https://URL-PUBLICA-DE-MEDICARE-BILLING-PRO
```

Antes de usar Billing Pro en producción, ejecutar `medicare_billing_pro/migracion_supabase.sql` en el SQL Editor de Supabase. Esa migración crea las tablas `billing_clientes`, `billing_presupuestos`, `billing_prefacturas` y `billing_cobros`.

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
