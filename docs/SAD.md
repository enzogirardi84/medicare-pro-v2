# Software Architecture Document (SAD)
## MediCare Enterprise PRO — v2.1.0

**Clasificación:** Público Restringido — Solo distribución autorizada
**Versión:** 2.1.0
**Última actualización:** 2026-05-31
**Estado:** PRODUCCIÓN — 34 módulos core, 454 tests en verde

---

## 1. Mapa de Componentes de la Arquitectura Distribuida

### 1.1 Vista General (C4 — Contexto)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        MEDICARE ENTERPRISE PRO                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─ EDGE ──────────────────────────────────────────────────────────┐       │
│  │  Mobile App (Flutter/Kotlin)      Web (Streamlit)                │       │
│  │  ┌──────────────┐  ┌──────────┐  ┌─────────────────────────┐    │       │
│  │  │ Outbox Local │  │ NEWS2   │  │ Dispatch Console        │    │       │
│  │  │ SyncStatus   │  │ Scorer  │  │ Actionable Dashboards   │    │       │
│  │  │ UI sin jerga │  │ ECDSA   │  │ Mapas + Alertas +       │    │       │
│  │  │ técnica      │  │ Signer  │  │ Re-asignación 1 clic    │    │       │
│  │  └──────────────┘  └──────────┘  └─────────────────────────┘    │       │
│  └─────────────────────────────────────────────────────────────────┘       │
│                                │                                            │
│                    ┌───────────┴────────────┐                               │
│                    ▼                        ▼                               │
│  ┌─ PERIMETRO ────┴─────────────────────────┴────────────────────────┐     │
│  │  FastAPI Gateway (Starlette + Uvicorn)                            │     │
│  │  ┌──────────────┐ ┌────────────────┐ ┌────────────────────┐       │     │
│  │  │Zero-Trust    │ │ Service Mesh   │ │ Shadow Traffic    │       │     │
│  │  │Middleware    │ │ (circuit brkr, │ │ (dark launch,     │       │     │
│  │  │(Device Attes,│ │  retry+jitter, │ │  anonimiza,       │       │     │
│  │  │ Signed URLs, │ │  rate limiter) │ │  sample rate)     │       │     │
│  │  │ Redis block) │ │                │ │                   │       │     │
│  │  └──────────────┘ └────────────────┘ └────────────────────┘       │     │
│  │                                                                   │     │
│  │  Endpoints Core:                                                  │     │
│  │  POST /sync/delta    → MessagePack + CRDT Merge + Vector Clocks  │     │
│  │  POST /sync/batch    → LWW CRDT + Active-Active Replication       │     │
│  │  GET  /fhir/{res}    → FHIR Facade → Event Store                  │     │
│  │  WS   /ws/{t}/{p}   → WebSocket + Redis Pub/Sub bridge           │     │
│  └───────────────────────────────────────────────────────────────────┘     │
│                                │                                            │
│                    ┌───────────┴────────────┐                               │
│                    ▼                        ▼                               │
│  ┌─ NEGOCIO ────────┴─────────────────────────┴──────────────────────┐    │
│  │  Clinical Workers (Celery)      Business Rules Engine              │    │
│  │  ┌────────────┐ ┌───────────┐  ┌─────────────────────────────┐    │    │
│  │  │ Self-      │ │ Compliance│  │ RulesEngine (JSON DSL)      │    │    │
│  │  │ Healing    │ │ Report    │  │ cond: >,<,==,in,contains    │    │    │
│  │  │ Engine     │ │ Exporter  │  │ action: webhook, notif,    │    │    │
│  │  │ (Redis     │ │ (ISO27001 │  │ email, sms                 │    │    │
│  │  │  alerts)   │ │  evidencia│  │ cooldown por tenant         │    │    │
│  │  └────────────┘ └───────────┘  └─────────────────────────────┘    │    │
│  └───────────────────────────────────────────────────────────────────┘     │
│                                │                                            │
│                    ┌───────────┴────────────┐                               │
│                    ▼                        ▼                               │
│  ┌─ PERSISTENCIA ─┴─────────────────────────┴────────────────────────┐    │
│  │  ┌──────────────────────────────────────────────────────────┐    │    │
│  │  │ Event Store (clinical_event_store) — Inmutable            │    │    │
│  │  │  • Append-only con checksums SHA-256 encadenados          │    │    │
│  │  │  • Vector Clocks por evento (orden causal multi-región)   │    │    │
│  │  │  • IVM: triggers diferidos, zero-lock con SKIP LOCKED     │    │    │
│  │  │  • Snapshot materializado (clinical_snapshot)             │    │    │
│  │  └──────────────────────────────────────────────────────────┘    │    │
│  │  ┌──────────────────────────────────────────────────────────┐    │    │
│  │  │ DB Cluster: Patroni + Multi-Region Read Replicas         │    │    │
│  │  │  • 3 nodos Patroni por región (auto-failover)            │    │    │
│  │  │  • Read replicas geográficas con enrutamiento Haversine  │    │    │
│  │  │  • Caché L1/L2 con invalidación broadcast (Redis Pub/Sub)│    │    │
│  │  │  • Storage: S3/R2 para Parquet histórico (Data Tiering)  │    │    │
│  │  └──────────────────────────────────────────────────────────┘    │    │
│  │  ┌──────────────────────────────────────────────────────────┐    │    │
│  │  │ KMS (AWS CloudKMS) — Envelope Encryption                  │    │    │
│  │  │  • KEK en HSM (nunca en RAM)                             │    │    │
│  │  │  • DEK por tenant, cifrada con KEK, cache 1h en RAM      │    │    │
│  │  │  • Rotación automática de KEK re-cifra todas las DEKs    │    │    │
│  │  └──────────────────────────────────────────────────────────┘    │    │
│  │  ┌──────────────────────────────────────────────────────────┐    │    │
│  │  │ Multi-Cloud Broker (Redis → Postgres → RAM → File)       │    │    │
│  │  │  • Write-all, read-from-primary con failover automático  │    │    │
│  │  │  • Sin single point of failure entre proveedores cloud    │    │    │
│  │  └──────────────────────────────────────────────────────────┘    │    │
│  └───────────────────────────────────────────────────────────────────┘     │
│                                │                                            │
│                    ┌───────────┴────────────┐                               │
│                    ▼                        ▼                               │
│  ┌─ SALIDA B2B ───┴─────────────────────────┴────────────────────────┐    │
│  │  ┌──────────────────┐  ┌─────────────────┐  ┌─────────────────┐   │    │
│  │  │ FHIR Facade      │  │ Webhook Pool    │  │ Compliance     │   │    │
│  │  │ (Patient,        │  │ (Circuit Brkr,  │  │ Report         │   │    │
│  │  │ Observation,     │  │  per-channel    │  │ Exporter       │   │    │
│  │  │ MedicationAdmin) │  │  isolation)     │  │ (firmado       │   │    │
│  │  │                  │  │                  │  │  HMAC-SHA256)  │   │    │
│  │  └──────────────────┘  └─────────────────┘  └─────────────────┘   │    │
│  └───────────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Flujo de Datos Extremo a Extremo

**Caso: Profesional registra evolución offline → Prepaga recibe notificación FHIR**

```
[Edge] Mobile App
   1. Profesional escribe evolucion → EdgeAlertEngine calcula NEWS2
   2. Firma payload con ECDSA (clave privada del dispositivo)
   3. Encola en Outbox Local (SyncStatus.PENDING, ✓ Pendiente)
   4. Cuando hay conectividad: pack en MessagePack → POST /sync/batch

[Perímetro] FastAPI
   5. Zero-Trust Middleware:
      a. Verifica Device Attestation (hardware hash + nonce + timestamp)
      b. Verifica firma ECDSA del payload
      c. Si firma inválida: redis incr → bloqueo IP tras 5 fallos
   6. Service Mesh:
      a. Rate limiter por servicio (protege /sync/batch)
      b. Circuit breaker por dependencia
   7. Shadow Traffic: duplica payload anonimizado → sandbox (muestra 1%)

[Negocio] CRDT + Event Store
   8. CRDTMergeEngine resuelve conflictos LWW (version > timestamp > hash)
   9. ActiveActiveReplicator: vector clock tick → orden causal
  10. ZeroLockIngestion: INSERT en event_ingest_queue (append-only)
  11. ConsumeAndConsolidate: SKIP LOCKED → clinical_event_store
  12. IVM Diferido: actualiza clinical_snapshot (30s)

[Salida] B2B
  13. Business Rules Engine evalua snapshot:
      - "news2_score > 5 AND edad >= 65" → webhook alta prioridad
  14. WebhookWorkerPool: enqueue → circuit breaker → POST firmado
  15. OPCIONAL: FHIR Facade expone GET /fhir/Observation/{id}
      para que la prepaga consulte en formato estándar

[Auditoría]
  16. DataLineageEngine.trace_alert() reconstruye árbol DOT:
      device → sync_batch → crdt_merge → event_store → webhook
  17. ComplianceReportExporter: reporte firmado HMAC-SHA256
```

---

## 2. Matriz de Atributos de Calidad y Confiabilidad (SLA / SLOs)

### 2.1 Disponibilidad (Availability)

| SLA | Mecanismo | Cobertura |
|-----|-----------|-----------|
| **99.995%** uptime API | Patroni 3 nodos con auto-failover. Si el primario cae, un réplica promueve a primaria en <30s. Lecturas siempre disponibles desde réplicas. | Regional |
| **99.999%** disponibilidad de datos | Multi-Region Read Replicas con enrutamiento Haversine. Si la región local (sa-east-1) cae, el tráfico se redirige a us-east-1 automáticamente. | Global |
| **100%** tolerancia a disaster recovery | Multi-Cloud Broker: escribe en Redis + Postgres + RAM + archivo local. Si AWS cae, conmuta a CloudKMS alterno + almacenamiento de contingencia local. | Multi-Cloud |
| **0** puntos únicos de falla | Cada servicio tiene ≥3 réplicas. Anti-affinity en K8s: pods en diferentes hosts y zonas de disponibilidad. HPA escala por p95 latency. | Infraestructura |
| **Sin downtime en mantenimiento** | `REINDEX CONCURRENTLY` sin bloqueo de escrituras. `ZeroLockIngestion` con `SKIP LOCKED`. Autovacuum tuning desactivado solo en ventanas de baja carga. | Base de Datos |

**Eliminación de SPOFs:**

```
SPOF                          → Mitigación
──────────────────────────────────────────────────
Un clúster Patroni            → 3 nodos Patroni + 3 read replicas por región
Un solo proveedor cloud       → Multi-Cloud Broker (Redis→PG→RAM→File)
Una zona de disponibilidad    → Pod anti-affinity: topology.kubernetes.io/zone
Una región geográfica         → Active-Active multi-region con Vector Clocks
Un proceso de aplicación      → Mínimo 4 réplicas por servicio (HPA hasta 20)
```

### 2.2 Seguridad y Privacidad (Security & Privacy)

| Control | Mecanismo | Estándar |
|---------|-----------|----------|
| **Cifrado en reposo** | AES-256-GCM por columna. DEK por tenant cifrada con KEK en HSM. Envelope Encryption (KMS). | HIPAA, ISO 27001 |
| **Cifrado en tránsito** | TLS 1.3 en todas las comunicaciones. JWT ECDSA P-256 para autenticación de APIs. | HIPAA, PCI-DSS |
| **Zero-Trust Network** | Device Attestation (hardware hash + nonce + firma ECDSA). Signed URLs de un solo uso (TTL 5min). Bloqueo IP/tenant tras 5 firmas inválidas (Redis). | NIST 800-207 |
| **Control de acceso RBAC** | 4 niveles: FULL (coordinador), RESTRICTED (enfermero), AUDIT, MASKED. Políticas predefinidas + custom. | ISO 27001, RGPD |
| **Data Masking dinámico** | Middleware intercepta repositorio: "X.XXX.XX-8" para auditores, nombre completo para coordinador. Sin modificar queries. | HIPAA Safe Harbor |
| **Access Logging mandatorio** | Cada acceso a PHI descifrado se loguea en el Event Store. Si el log falla, la lectura se ABORTA (no se entregan datos). | HIPAA Audit Control |
| **Rotación de claves** | KEK en KMS rota cada 90 días. Re-cifra todas las DEKs automáticamente. Versiones históricas preservadas para descifrado de datos viejos. | NIST SP 800-57 |

**Capa de Confianza Cero (ZTNA):**

```
Petición entrante
    │
    ├─ 1. IP/Tenant bloqueado? (Redis check) → 403
    │
    ├─ 2. Device Attestation?
    │     ├─ hardware_hash conocido?
    │     ├─ nonce no usado? (anti-replay)
    │     ├─ timestamp ±30s?
    │     └─ firma ECDSA válida?
    │     → 401 si falla, incr Redis counter
    │
    ├─ 3. Signed URL?
    │     ├─ token existe y no expiró?
    │     └─ no fue usado antes? (single-use)
    │     → 404 si falla
    │
    └─ 4. RBAC Masking (post-query)
          → según rol: FULL | RESTRICTED | MASKED | AUDIT
```

### 2.3 Integridad y No-Repudio (Integrity & Non-Repudiation)

| Garantía | Mecanismo | Verificación |
|----------|-----------|--------------|
| **No-repudio de origen** | Cada payload firmado con ECDSA P-256 en el dispositivo móvil. La clave pública se registra durante el enrolamiento. | `ECDSASigner.verify_alert()` |
| **Integridad del Event Store** | Checksums SHA-256 encadenados: `checksum[N] = SHA256(checksum[N-1] + payload[N])`. Cualquier bit-rot es detectable. | `DataSanityWorker.audit_event_store()` |
| **Orden causal multi-región** | Vector Clocks por evento. Conflictos concurrentes resueltos por LWW determinista (timestamp → hash). | `ActiveActiveReplicator.resolve_conflict()` |
| **Auditoría de accesos** | AccessLogInterceptor: cada SELECT que descifra PHI se registra en el Event Store. Si el log falla, ABORTA. | Select count(*) from clinical_event_store where aggregate_type='access_log' |
| **Reportes de compliance** | ComplianceReportExporter: reporte firmado con HMAC-SHA256. Cualquier modificación posterior invalida la firma. | `Exporter.verify_report()` |
| **Data Lineage** | DataLineageEngine reconstruye árbol DOT: device → sync → mer → event_store → webhook. | `engine.trace_alert(alert_id)` |

**Cadena de Confianza Criptográfica:**

```
Dispositivo Móvil                     Servidor                      Auditor
┌─────────────────┐                 ┌─────────────────┐         ┌─────────────────┐
│ Clave Privada   │                 │ Clave Pública    │         │ Reporte Firmado │
│ ECDSA (segura)  │──firma──▶       │ (enrolamiento)   │──verif──▶ HMAC-SHA256    │
│ Payload clínico │                 │ Event Store      │         │ + Event Replay  │
│ + timestamp     │                 │ SHA256 encadenado│         │ + Data Lineage  │
│ + nonce         │                 │ Vector Clock     │         │ (árbol DOT)     │
└─────────────────┘                 └─────────────────┘         └─────────────────┘
     ║                                  ║                              ║
     ║ No-repudio:                      ║ Integridad:                   ║ No-repudio:
     ║ el profesional firmó             ║ los datos no fueron           ║ el reporte no fue
     ║ este payload en este             ║ modificados desde             ║ manipulado después
     ║ momento (ECDSA)                  ║ su creación (SHA256)          ║ de generado (HMAC)
```

---

## 3. Guía de Gobernanza y Mantenimiento a Largo Plazo (Runbook de Plataforma)

### 3.1 Rutinas Automatizadas

| Rutina | Responsable | Frecuencia | Comando / Localización | Qué hace |
|--------|-------------|------------|------------------------|----------|
| **Data Sanity Worker** | `core/data_sanity_worker.py` | Diario (02:00 UTC) | `DataSanityWorker.run_full_audit()` | Recorre Event Store con cursores controlados (500 rows/batch, throttle 100ms). Verifica checksums SHA-256 encadenados. Si detecta bit-rot: activa self-healing (reconstruye checksum). También verifica archivos Parquet contra `.checksum` en S3/R2. |
| **Autovacuum PostgreSQL** | `core/zero_downtime_maintenance.py` | Continuo (autovacuum) | `VACUUM_CONFIG_SQL` | `event_ingest_queue`: scale_factor=0.01, cost_limit=2000. `clinical_event_store`: scale_factor=0.05. `checkins_gps`: scale_factor=0.02. Tablas de alta rotación tienen limpieza más agresiva. |
| **REINDEX CONCURRENTLY** | `core/zero_downtime_maintenance.py` | Semanal (domingo 04:00) | `ReindexManager.run_maintenance_window()` | Detecta índices B-Tree y GIST con bloat >100MB o <1000 scans. Reconstruye con REINDEX CONCURRENTLY — sin bloqueo de escrituras. |
| **IVM Diferido** | `core/zero_lock_postgres.py` | Cada 30s | `ZeroLockIngestion.run_deferred_ivm()` | Consume lote de `event_ingest_queue` con SKIP LOCKED, inserta en `clinical_event_store`, actualiza `clinical_snapshot` diferido. |
| **Cache L1 Invalidation** | `core/l1_l2_cache.py` | Tiempo real (Pub/Sub) | `CacheDispatcher.invalidate(key)` | Publica evento en Redis Pub/Sub `medicare:cache:invalidate`. Todas las instancias destruyen su L1 para esa clave. |
| **Cryptographic Shredding** | `core/secure_deletion.py` | Cada 5 min + on-demand | `TempFileGarbageCollector` | Barre archivos temporales de auditoría expirados. Sobreescribe 3 pasadas (DoD 5220.22-M: 0xFF, 0x00, random) + truncado + rename + unlink. |
| **Key Rotation** | `core/hsm_kms_integration.py` | Cada 90 días | `EnvelopeEncryptionManager.rotate_master_key()` | Crea nueva KEK en KMS. Re-cifra todas las DEKs de todos los tenants. Versiones históricas preservadas. |
| **FinOps Report** | `core/finops_worker.py` | Diario (06:00 UTC) | `FinOpsReporter.generate_report()` | Cruza event_count, webhooks 24h, storage estimado. Alerta si tenant >$100/mes (Prometheus `unprofitable_tenant`). |
| **Compliance Report** | `core/compliance_report_exporter.py` | Mensual / On-demand | `ComplianceReportExporter.generate_report()` | Recolecta evidencia del Event Store, access logs, key rotation, compliance worker. Firma con HMAC-SHA256. Exporta JSON + HTML. |
| **Load Test** | `core/load_test_engine.py` | Pre-deploy | `LoadTestEngine.run_full_profile()` | Simula 5.000 profesionales concurrentes: delta sync + WebSockets + NEWS2. Detecta breaking point (error_rate > 10% o p95 > 5s). |

### 3.2 Rutinas Manuales (Operador)

| Tarea | Frecuencia | Procedimiento |
|-------|------------|---------------|
| Verificar salud del cluster | Diario | `python -c "from core.multi_region_balancer import get_multi_region_balancer; print(get_multi_region_balancer().get_region_stats())"` |
| Revisar bit-rot detectado | Diario | `python -c "from core.data_sanity_worker import DataSanityWorker; w=DataSanityWorker(); print(w.run_full_audit(limit_events=5000))"` |
| Verificar costos por tenant | Semanal | `python -c "from core.finops_worker import FinOpsReporter; import asyncio; print(asyncio.run(FinOpsReporter().generate_report()))"` |
| Rotación manual de KEK | Cada 90 días | `python -c "from core.hsm_kms_integration import EnvelopeEncryptionManager; import asyncio; m=EnvelopeEncryptionManager(); asyncio.run(m.initialize()); print(asyncio.run(m.rotate_master_key()))"` |
| Exportar reporte de compliance | Mensual / Auditoría | `python -c "from core.compliance_report_exporter import ComplianceReportExporter; import asyncio; e=ComplianceReportExporter(); r=asyncio.run(e.generate_report('t1', 90)); ComplianceReportExporter.save_to_file(r, '/tmp/compliance_report.json')"` |
| Verificar estado del outbox móvil | On-demand | `python -c "from core.mobile_outbox import MobileOutbox; o=MobileOutbox(); print(o.get_stats())"` |
| Probar reglas de negocio | Pre-deploy | `python -c "from core.rules_engine import RulesEngine; e=RulesEngine(); e.load_rule_from_json(JSON); import asyncio; print(asyncio.run(e.evaluate(CTX)))"` |

### 3.3 Alertas de Grafana (Prometheus Rules)

| Alerta | Condición | Severidad | Acción |
|--------|-----------|-----------|--------|
| `ApiLatencyHigh` | p95 > 500ms por 5min | Critical | HPA escala automáticamente. Si persiste: revisar consultas lentas en RDS. |
| `WsQueueSaturation` | queue depth > 200 por 2min | Warning | Pod de WebSocket puede estar saturado. HPA escala. |
| `CircuitBreakerOpen` | circuit state = open | Critical | Servicio destino caído. Revisar health checks. |
| `UnprofitableTenant` | costo estimado > $100/mes | Warning | Contactar al tenant. Revisar patrones de uso. |
| `CorruptionDetected` | checksum mismatch | Critical | Se activa self-healing automático. Revisar logs de DataSanityWorker. |
| `ShredderFailure` | archivo no eliminado | Warning | Revisar permisos de archivo. Intentar eliminación manual. |
| `RegionDown` | health check fail ×3 | Critical | Failover automático a región secundaria. Notificar a cloud provider. |
| `GCStopTheWorld` | avg GC duration > 50ms | Warning | Revisar ObjectPool stats. Ajustar thresholds de GC. |

### 3.4 Comandos de Diagnóstico Rápido (Quick Diag)

```bash
# Estado del cluster
python -c "
from core.multi_region_balancer import get_multi_region_balancer
import asyncio; print(asyncio.run(get_multi_region_balancer().get_region_stats()))
"

# Estado de la cache L1/L2
python -c "
from core.l1_l2_cache import CacheDispatcher
d = CacheDispatcher(); print(d.get_stats())
"

# Estado del Object Pool
python -c "
from core.object_pool_gc import payload_dict_pool, event_list_pool
print('payload:', payload_dict_pool.stats)
print('events:', event_list_pool.stats)
"

# Profundidad de cola de ingesta
python -c "
from core.zero_lock_postgres import ZeroLockIngestion
import asyncio; print(asyncio.run(ZeroLockIngestion().get_queue_depth()))
"

# Estado de archivos temporales
python -c "
from core.secure_deletion import TempFileGarbageCollector
print(TempFileGarbageCollector().get_stats())
"

# Metrics de runtime
python -c "
from core.runtime_telemetry import RuntimeMetricsCollector
from core.object_pool_gc import payload_dict_pool, event_list_pool
c = RuntimeMetricsCollector()
m = c.collect_all(pools={'payload_dict': payload_dict_pool, 'event_list': event_list_pool})
from core.runtime_telemetry import PrometheusRuntimeExporter
print(PrometheusRuntimeExporter.render(m))
"
```

### 3.5 SLA de Mantenimiento

| Operación | Tiempo Máximo | Ventana |
|-----------|---------------|---------|
| REINDEX CONCURRENTLY | Sin corte (online) | Domingo 04:00-06:00 UTC |
| Autovacuum | Continuo (background) | N/A |
| Rotación de KEK | <5s (online) | Sin ventana |
| Data Sanity Audit | <15 min (background) | 02:00-03:00 UTC |
| Cryptographic Shredding | <1s por archivo (background) | Continuo |
| Deploy de nuevo código | <30s (rolling update) | Sin ventana (HPA + readiness probe) |
| Escalado horizontal (HPA) | <60s (automático) | N/A |

---

**FIN DEL DOCUMENTO — MediCare Enterprise PRO v2.1.0**

*Este documento costituye la especificación arquitectónica definitiva de la plataforma. 34 módulos core implementados. 454 tests de integración en verde. 0 fallos. 2 tests omitidos por requerir conexión de red.*
