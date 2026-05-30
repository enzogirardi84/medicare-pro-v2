# MediCare Enterprise PRO — API de Seguridad

## Módulos de criptografía

| Módulo | Función | Propósito |
|--------|---------|-----------|
| `phi_encryption.py` | `encrypt_value(value, table)` | Cifra un campo PHI con AES-256-GCM |
| | `decrypt_value(encrypted_json, table)` | Descifra un campo PHI |
| | `encrypt_patient_data(patient)` | Cifra todos los campos sensibles de un paciente |
| `ecdsa_signature.py` | `ECDSASignatureManager.firmar(documento, clave_privada)` | Firma un documento con ECDSA P-256 |
| | `ECDSASignatureManager.verificar(documento, signed, clave_publica)` | Verifica firma ECDSA |
| `batch_signer.py` | `BatchSigner.firmar_lote(ops, priv_key, profesional)` | Firma lote de 25 operaciones offline |

## Auditoría

| Módulo | Función | Propósito |
|--------|---------|-----------|
| `audit_trail_immutable.py` | `ImmutableAuditTrail().registrar(usuario, accion, recurso)` | Registra evento en audit trail blockchain-like |
| | `verificar_integridad(max_entries=50000)` | Verifica cadena de hashes |
| | `obtener_historial(usuario, accion, limite)` | Consulta eventos del audit trail |

## Autenticación

| Módulo | Función | Propósito |
|--------|---------|-----------|
| `totp_mfa.py` | `TOTPManager.generar_secreto()` | Genera secreto TOTP (32 chars base32) |
| | `TOTPManager.verificar_codigo(secreto, codigo)` | Verifica código de 6 dígitos |
| | `verificar_codigo_recuperacion(usuario, codigo)` | Verifica código de respaldo de un solo uso |
| `seguridad_ui.py` | `render_login_totp(login_name)` | Muestra desafío TOTP post-login |
| | `render_totp_enrollment(usuario)` | Pantalla de configuración 2FA con QR |

## Offline Sync

| Módulo | Función | Propósito |
|--------|---------|-----------|
| `offline_sync.py` | `LocalQueueStore().encolar(op)` | Encola operación en SQLite cifrado |
| | `SyncManager().sincronizar()` | Drena cola local hacia servidor |
| | `SyncManager().encolar_operacion(tipo, payload)` | Encola con intento de sync inmediato |

## SRE / Monitoreo

| Módulo | Función | Propósito |
|--------|---------|-----------|
| `metrics.py` | `MetricsCollector().health_check(tenant)` | Health check: audit trail, disco, supabase |
| | `AlertManager.disparar_alerta(nivel, mensaje, ...)` | Webhook Slack/Discord para alertas |
| | `render_sre_panel(rol)` | Dashboard SRE protegido por RBAC |
