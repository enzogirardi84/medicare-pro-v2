# Plan de estabilizacion MediCare Pro

## Objetivo

Recuperar el acceso al programa, dejar un unico flujo de arranque/deploy y evitar que fallas de nube se presenten como errores falsos de usuario o contrasena.

## Diagnostico actual

- La app desplegada cae a modo local cuando no puede conectar con Supabase.
- El `SUPABASE_URL` configurado localmente apunta a un host que no resuelve por DNS.
- En ese estado, el login normal no puede validar usuarios de Mi equipo.
- El entrypoint quedo unificado en `streamlit_app.py` para Streamlit Cloud, Render, Docker y scripts locales.

## Cambios aplicados

- Login: bloquea el fallback local en produccion salvo que `ALLOW_LOGIN_LOCAL_FALLBACK=true`.
- Login: intenta acceso de emergencia antes de consultar Supabase, para permitir recuperacion si la nube esta caida.
- Supabase: lectura de secrets tolerante a BOM accidental y cliente HTTP con `trust_env=False` y timeout explicito.
- Deploy: `streamlit_app.py` como entrypoint canonico.
- Render: se elimino el servicio `medicare-billing-pro` que apuntaba a una carpeta inexistente.
- Docker: crea `storage` antes de enlazar `storage/estudios`.
- Tests: cobertura nueva para secrets, fallback local, usuarios faltantes, entrypoint y login de emergencia.

## Checklist para volver a operar

1. Subir estos cambios a GitHub y desplegar.
2. En Streamlit Cloud, confirmar `Main file path = streamlit_app.py`.
3. En Secrets, verificar:
   - `SUPABASE_URL` con el proyecto real, formato `https://<project-ref>.supabase.co`.
   - `SUPABASE_KEY` del mismo proyecto.
   - `MEDICARE_ENV = "production"`.
   - `SUPERADMIN_EMERGENCY_PASSWORD` configurada y conocida por administracion.
4. No activar `ALLOW_LOGIN_LOCAL_FALLBACK` en produccion salvo emergencia controlada.
5. Reiniciar la app en Streamlit Cloud.
6. Probar acceso con usuario operativo y con usuario de recuperacion.

## Validacion local

```bash
python -m pytest -q
python scripts/diagnostico_deploy.py
streamlit run streamlit_app.py
```

## Riesgo pendiente

El codigo ya evita el falso error de credenciales, pero el acceso productivo depende de corregir el `SUPABASE_URL` real en los Secrets del deploy. Sin ese dato correcto, ningun usuario normal puede autenticarse contra la nube.
