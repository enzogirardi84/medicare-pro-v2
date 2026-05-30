# MediCare Enterprise PRO
## Whitepaper de Arquitectura de Seguridad Técnica y Compliance

**Documento:** MSP-WP-2026-001  
**Versión:** 1.0  
**Clasificación:** CONFIDENCIAL - USO INSTITUCIONAL  
**Fecha:** Mayo 2026

---

## 1. Resumen Ejecutivo y Modelo de Confianza Cero (Zero Trust)

MediCare Enterprise PRO es una plataforma SaaS multi-inquilino de gestión sanitaria diseñada para instituciones de salud domiciliaria, emergencias y operación clínica. El sistema opera bajo un modelo de **Confianza Cero (Zero Trust)** donde ninguna entidad — interna o externa — es considerada confiable por defecto. Cada solicitud de acceso es autenticada, autorizada y auditada de forma independiente.

### Principios Rectores

| Principio | Implementación |
|-----------|---------------|
| **Verificar explícitamente** | Autenticación multifactor TOTP (RFC 6238) + verificación de firma ECDSA en cada transacción |
| **Acceso con mínimo privilegio** | RBAC granular con 7 roles operativos; cada rol tiene permisos atómicos sobre recursos específicos |
| **Asumir brecha** | Cifrado AES-256-GCM en reposo por campo PHI; audit trail inmutable estilo blockchain; zero-trust networking mediante Nginx con CSP headers |
| **Segmentación** | Aislamiento físico por tenant en sistema de archivos y base de datos; sharding por clínica en Supabase |

El modelo Zero Trust se extiende a la capa de identidad: cada profesional de la salud posee un **par de claves asimétricas ECDSA**. La clave privada nunca abandona el dispositivo del usuario (cifrada con PBKDF2-AES-256-GCM), y la clave pública se almacena en el servidor para verificación. Cada evolución médica, receta o registro clínico es firmado con esta clave, garantizando **No Repudio** ante auditorías legales.

---

## 2. Protocolos de Cifrado y Garantía de No Repudio Legal

### 2.1 Cifrado en Reposo: AES-256-GCM con Derivación de Claves

El sistema implementa un esquema de cifrado híbrido para la protección de Información de Salud Protegida (PHI). Cada campo sensible es cifrado individualmente utilizando **AES-256 en modo GCM (Galois/Counter Mode)**, que proporciona autenticación integrada y protección contra manipulación.

**Arquitectura de derivación de claves:**

```
Master Key (derivada del secreto del tenant)
    │
    ├── PBKDF2 (SHA-256, 600,000 iteraciones)
    │       │
    │       └── Data Encryption Key (DEK) por tabla
    │               │
    │               ├── AES-256-GCM → Pacientes (nombre, DNI, dirección)
    │               ├── AES-256-GCM → Evoluciones (diagnóstico, notas)
    │               ├── AES-256-GCM → Recetas (medicamentos, indicaciones)
    │               ├── AES-256-GCM → Estudios (resultados, observaciones)
    │               └── AES-256-GCM → Check-ins (coordenadas GPS)
    │
    └── Nonce único de 12 bytes por cifrado
```

Cada tabla tiene su propia clave de cifrado derivada (`PHIEncryptionManager._derive_key()`), lo que limita el alcance de una eventual fuga: comprometer la clave de una tabla no expone los datos de las demás. Los campos cifrados incluyen una flag `_encrypted` para detección automática al desencriptar, garantizando compatibilidad con datos legacy no cifrados.

**Estándares aplicados:** NIST SP 800-38D (AES-GCM), NIST SP 800-132 (PBKDF2), FIPS 197 (AES-256).

### 2.2 Firmas Asimétricas ECDSA para No Repudio

Cada profesional de la salud posee un par de claves basado en **curva elíptica SECP256R1 (NIST P-256)**. Este esquema de criptografía asimétrica garantiza que:

1. **Autenticidad:** Solo el poseedor de la clave privada pudo generar la firma.
2. **Integridad:** Cualquier modificación posterior invalida la firma.
3. **No Repudio:** El firmante no puede negar haber autorizado el documento, verificable por cualquier tercero con acceso a la clave pública.

**Proceso de firma:**

1. El documento clínico se serializa a JSON canónico (`sort_keys=True`).
2. Se computa `SHA-256(JSON_canónico)` → `hash_documento`.
3. El hash se firma con la clave privada del profesional usando `ECDSA(hashes.SHA256())`.
4. La firma se almacena como `SignedDocument` con: `documento_id`, `contenido_hash`, `firma_b64`, `timestamp`, `firmante`.
5. La clave pública se registra con un **fingerprint** (`SHA-256(clave_pública)`).

**Proceso de verificación:**

1. Se recalcula el hash del documento actual.
2. Se compara con `contenido_hash` almacenado.
3. Se verifica la firma ECDSA con la clave pública del profesional.
4. Se consulta el `KeyRevocationManager` para asegurar que la clave no fue revocada.

**Estándares aplicados:** FIPS 186-5 (ECDSA), NIST SP 800-186 (SECP256R1), FIPS 180-4 (SHA-256).

---

## 3. Trazabilidad Forense e Integridad de Registros (Audit Trail)

### 3.1 Motor de Auditoría Inmutable

El sistema implementa un **audit trail inmutable con encadenamiento de hashes SHA-256**, una arquitectura fundamentalmente similar a la de blockchain, diseñada para garantizar la integridad forense de todos los accesos y operaciones sobre datos clínicos.

**Estructura de cada entrada:**

```
Entry = {
    timestamp: float,
    usuario: string,
    accion: "lectura" | "escritura" | "login" | "logout" | "firma",
    recurso: string (ej. "historial:paciente_XXXX"),
    detalle: string,
    hash_prev: string (SHA-256 de la entrada anterior),
    hash_actual: string (SHA-256 de esta entrada),
    firmado: boolean
}
```

**Propiedades de seguridad:**

- **Append-only:** Las entradas se agregan al final del archivo JSON Lines. Nunca se modifican ni eliminan entradas existentes.
- **Encadenamiento criptográfico:** Cada entrada contiene el hash de la entrada anterior. La alteración de cualquier entrada rompería la cadena completa, detectable mediante verificación automatizada.
- **Entrada génesis:** El archivo se inicializa con un bloque génesis cuyo `hash_prev = "0" * 64`.
- **Rotación blindada:** Al alcanzar 50 MB, el archivo se comprime con gzip y se mueve a almacenamiento frío con permisos `0444` (solo lectura). El nuevo archivo se encadena al hash del archivo rotado.

### 3.2 Verificación Diaria de Integridad

El script `scripts/audit_integrity_check.py` ejecuta una verificación completa de la cadena de hashes:

```python
errores = auditor.verificar_integridad(max_entries=50000)
```

Si se detecta una anomalía — un hash que no coincide con el esperado — el sistema dispara una **alerta CRÍTICA** a través del `AlertManager`, que notifica al equipo de SRE vía webhook (Slack/Discord/Telegram) y registra el evento en el propio audit trail como evidencia de la detección.

**Especificaciones operativas:**

- Frecuencia de verificación: Diaria (cron) o bajo demanda desde el dashboard SRE.
- Almacenamiento frío: Archivos rotados a bucket S3 con ACL de solo lectura.
- Retención: Mínimo 1 año según requerimientos HIPAA/GDPR.

---

## 4. Resiliencia Operativa y Arquitectura Local-First

### 4.1 Persistencia Local Cifrada

La plataforma está diseñada para operar en entornos de conectividad intermitente (ambulancias, zonas rurales, sótanos de hospitales). El módulo `LocalQueueStore` proporciona una **cola de persistencia local cifrada** basada en SQLite con las siguientes garantías:

**Seguridad:**

- Cada operación se cifra individualmente con AES-256-GCM.
- La clave de cifrado se deriva del identificador único de la máquina mediante PBKDF2 con 600,000 iteraciones.
- El archivo de clave local tiene permisos `0600`.
- Las columnas sensibles (`payload_enc`) se almacenan exclusivamente como BLOB cifrados.

**Estructura:**

| Columna | Tipo | Propósito |
|---------|------|-----------|
| `operation_id` | UUID4 | Identificador único (idempotencia) |
| `timestamp` | REAL | Orden cronológico de las operaciones |
| `tipo` | TEXT | "evolucion" | "checkin" | "receta" |
| `payload_enc` | BLOB | Payload cifrado con AES-256-GCM |
| `firma_ecdsa` | TEXT | Firma digital del payload |
| `intentos` | INTEGER | Contador de reintentos |
| `ultimo_error` | TEXT | Traza del último error |

### 4.2 Sincronización Asíncrona (SyncManager)

El `SyncManager` implementa un **heartbeat de conectividad** que verifica la disponibilidad del servidor central cada 15 segundos mediante una solicitud HEAD al endpoint `/healthz`. Cuando se detecta conectividad, el motor procede a drenar la cola local:

**Pipeline de sincronización:**

1. **Orden cronológico estricto:** Las operaciones se sincronizan en el mismo orden en que fueron creadas (ORDER BY timestamp ASC).
2. **Procesamiento por lotes:** Se sincronizan hasta 25 operaciones por ciclo para no saturar el servidor.
3. **Reintentos con límite:** Cada operación tiene un máximo de 5 reintentos. Al alcanzar el límite, se elimina de la cola y se registra como fallida.
4. **Idempotencia:** Cada operación lleva un UUID4 único. Si una operación se sincroniza dos veces, el servidor detecta el duplicado y lo ignora.

### 4.3 Resolución de Conflictos (LWW con Historial Versionado)

Dado que múltiples profesionales pueden operar sobre el mismo paciente (uno offline y otro online), el sistema implementa una estrategia de resolución de conflictos **Last-Write-Wins (LWW)** con preservación del historial:

1. Se comparan los timestamps de la versión local vs. remota.
2. La versión con timestamp más reciente se considera ganadora.
3. La versión perdedora se adjunta al historial de conflictos del registro ganador.
4. El historial mantiene hasta 10 versiones anteriores para trazabilidad forense.

Este enfoque garantiza que **ningún dato se pierde** — incluso la versión perdedora queda registrada y auditable.

---

## 5. Geoprocesamiento Seguro y Evidencia Física de Atención

### 5.1 Pipeline Geométrico de Filtrado

Las coordenadas GPS capturadas durante visitas domiciliarias o traslados de emergencia son procesadas por un pipeline geométrico de 3 etapas que elimina ruido de sensores y comprime trayectorias para almacenamiento eficiente:

**Etapa 1 — Filtro de Velocidad Máxima:**
Se calcula la velocidad entre puntos consecutivos usando la fórmula de Haversine. Los puntos que implican velocidades superiores a 180 km/h se descartan como ruido del sensor GPS (pérdida temporal de satélites, rebotes urbanos).

**Etapa 2 — Compresión Estacionaria:**
Si el profesional permanece dentro de un radio de 20 metros durante más de 30 segundos (ej. atendiendo una evolución en un domicilio), todos los puntos intermedios se reducen al primer y último punto del período, eliminando redundancia.

**Etapa 3 — Algoritmo de Douglas-Peucker:**
Se aplica una simplificación geométrica con tolerancia ε de ~50 metros para reducir trayectorias rectilíneas a sus puntos clave, minimizando la cantidad de datos a almacenar y renderizar sin perder precisión geográfica significativa.

### 5.2 Geofencing y Detección de Visitas

El `GeofencingEngine` utiliza la **fórmula de Haversine** para detectar automáticamente cuándo un profesional ingresa al radio de un domicilio (50 metros por defecto):

```
a = sin²(Δlat/2) + cos(lat1) · cos(lat2) · sin²(Δlon/2)
c = 2 · atan2(√a, √(1-a))
distancia = R · c
donde R = 6,371 km (radio terrestre medio)
```

Este cálculo puramente matemático evita dependencias de APIs externas durante el procesamiento por lotes. Las visitas detectadas se registran con: hora de entrada, hora de salida, duración total y radio de tolerancia. Esta información se incorpora al PDF clínico como **prueba de asistencia del profesional** en el domicilio del paciente.

### 5.3 Privacidad en Renderizado de Mapas

La visualización de mapas está protegida por un **decorador de auditoría** que:

1. Verifica que el rol del usuario sea Coordinador o Admin.
2. Registra en el audit trail inmutable que el usuario `X` visualizó la ruta del profesional `Y`.
3. Solo descifra en memoria las coordenadas estrictamente necesarias para la sesión activa.

---

## 6. Seguridad a Nivel de Infraestructura, Aislamiento de Tenants y SRE

### 6.1 Aislamiento Multi-Inquilino (TenantManager)

Cada cliente (obra social, prepaga o empresa de ambulancias) se despliega como un **tenant aislado**. El `TenantManager` carga la configuración desde el directorio `tenants/{tenant_id}/`:

```
tenants/
├── default/
│   ├── config.json          # Branding, timeouts, colores
│   ├── offline_queue/       # Cola offline cifrada
│   ├── audit_logs/          # Audit trail inmutable
│   └── estudios/            # Uploads sanitizados
├── avalian/
│   └── config.json          # Configuración específica del cliente
└── sancor/
    └── config.json
```

**Aislamientos garantizados:**

| Capa | Mecanismo |
|------|-----------|
| **Datos** | Directorios separados por tenant en sistema de archivos |
| **Base de datos** | Sharding por `tenant_key` en Supabase (aislamiento lógico) |
| **Logs** | Audit trail segregado por tenant |
| **Uploads** | Almacenamiento de estudios en directorio del tenant |
| **Configuración** | Archivos de configuración independientes por tenant |

### 6.2 Endurecimiento Perimetral (Nginx)

La plataforma está desplegada detrás de **Nginx como proxy inverso** con las siguientes protecciones:

**Cabeceras de seguridad (CSP):**
```
Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline';
style-src 'self' 'unsafe-inline'; img-src 'self' data: https:;
```

**Medidas de protección:**

| Medida | Implementación |
|--------|---------------|
| Anti-direcotry listing | `deny all` en directorios `.git`, `.env`, `.streamlit` |
| Bloqueo de ejecución remota (RCE) | `AddType application/octet-stream` para archivos subidos |
| Protección XSS | `X-XSS-Protection: 1; mode=block` |
| Anti-clickjacking | `X-Frame-Options: DENY` |
| HSTS | `Strict-Transport-Security: max-age=31536000; includeSubDomains` |
| Límite de tamaño | `client_max_body_size 25M` (upload máximo 20 MB) |
| Timeout de proxy | `proxy_read_timeout 120s` (geofencing + PDF pesados) |

### 6.3 Observabilidad y Alertas (SRE)

El sistema expone métricas en **formato Prometheus** estándar a través del endpoint de salud, y cuenta con un **AlertManager** que dispara notificaciones inmediatas:

**Métricas expuestas:**

| Métrica | Tipo | Descripción |
|---------|------|-------------|
| `medicare_operaciones_offline` | Gauge | Operaciones pendientes en cola local |
| `medicare_operaciones_sincronizadas` | Counter | Total de operaciones sincronizadas exitosamente |
| `medicare_login_totp_fallidos` | Counter | Intentos fallidos de autenticación TOTP |
| `medicare_archivos_bloqueados` | Counter | Archivos rechazados por el Upload Sanitizer |
| `medicare_pdf_tiempo_ms` | Gauge | Tiempo promedio de generación de PDF clínico |
| `medicare_audit_traill_integridad` | Gauge | 1 si el audit trail está íntegro, 0 si se detectó alteración |
| `medicare_supabase_online` | Gauge | 1 si la base de datos central está accesible |

**Alertas automáticas:**

| Evento | Nivel | Tiempo de respuesta |
|--------|-------|---------------------|
| Alteración detectada en audit trail | 🔴 CRÍTICO | Inmediato (webhook) |
| Health check degradado | 🟡 WARNING | < 5 minutos |
| Intento de acceso no autorizado | 🟡 WARNING | Inmediato |
| Supabase fuera de línea | 🟡 WARNING | < 15 segundos |

### 6.4 Compliance y Estándares Aplicados

| Estándar | Alcance | Implementación |
|----------|---------|----------------|
| **HIPAA** (EE.UU.) | Protección de PHI | Cifrado AES-256, audit trail, controles de acceso |
| **GDPR** (UE) | Protección de datos personales | Cifrado por campo, derecho al olvido, portabilidad |
| **Ley 25.326** (Argentina) | Protección de datos personales | Consentimiento informado, registro de accesos |
| **FIPS 140-3** | Módulos criptográficos | AES-256-GCM, ECDSA P-256, SHA-256 |
| **NIST SP 800-53** | Controles de seguridad | AC-3 (RBAC), AU-3 (audit trail), SC-13 (cryptography) |
| **OWASP Top 10** | Seguridad web | CSP headers, input sanitization, rate limiting |

---

## Conclusión

MediCare Enterprise PRO constituye una plataforma de gestión sanitaria diseñada desde sus cimientos con un enfoque **Security-by-Design** y **Privacy-by-Design**. La combinación de cifrado AES-256-GCM por campo, firmas asimétricas ECDSA para No Repudio, audit trail inmutable estilo blockchain, arquitectura offline-first con resolución de conflictos, y aislamiento multi-inquilino, proporciona un nivel de garantía técnica y legal equiparable a sistemas financieros y gubernamentales de alto impacto.

La plataforma está preparada para someterse a auditorías de seguridad de terceros, certificaciones HIPAA/GDPR y procesos de debida diligencia por parte de instituciones de salud, obras sociales y empresas de medicina prepaga.

---

*Documento generado por el equipo de Ingeniería de MediCare Enterprise PRO.*  
*Para consultas técnicas, contactar a: soporte@medicare-pro.app*  
*Repositorio: https://github.com/enzogirardi84/medicare-pro-v2*
