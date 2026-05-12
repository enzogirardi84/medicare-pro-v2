# Security Remediation - 2026-05-12

## Corregido en esta tanda

- Se elimino la deserializacion insegura con `pickle.loads` en `core.query_optimizer`.
- El compresor de datos ahora usa JSON + zlib para evitar ejecucion de payloads arbitrarios.
- Produccion ahora falla temprano si faltan `SECRET_KEY`, `PASSWORD_SALT`, `SUPABASE_URL` o `SUPABASE_KEY`.
- Produccion rechaza placeholders conocidos e impide arrancar con claves inseguras.
- Las altas y recuperaciones de contrasena ya no guardan texto plano si bcrypt no esta disponible.
- El timeout de sesion queda configurable, con valor por defecto de 30 minutos y limites seguros.
- Se removieron claves reales versionadas de ejemplos y documentacion de deploy.
- Se agregaron tests para configuracion segura, compresion segura y politica de contrasenas.

## Verificacion

Suite completa ejecutada:

```bash
python -m pytest tests -q
```

Resultado: 361 tests pasan.

## Riesgo residual

- Los usuarios legacy con `pass` en texto plano todavia pueden autenticar para permitir migracion progresiva.
- Hay que rotar todas las claves que alguna vez estuvieron versionadas en Git.
- Falta auditoria externa de Supabase: RLS, permisos, service role, backups y retencion.
- Falta refactorizar el monolito principal y ampliar pruebas end-to-end.
- Esto reduce riesgos criticos, pero no reemplaza pentest ni validacion legal/regulatoria.
