# Runbook de Incidentes — MediCare Enterprise PRO

## Alerta: `IntegrityFailureSpike` (CRÍTICA)

**Síntoma:** Prometheus alerta `rate(medicare_integrity_failures_total[5m]) > 0`

**Posibles causas:**
1. Bug en serialización canónica del cliente móvil (JSON keys en diferente orden)
2. Modificación manual de datos en PostgreSQL por fuera del `TenantRepository`
3. Corrupción de datos en tránsito (sincronización offline)
4. Ataque de alteración de datos (Data Tampering)

---

### Paso 1: Aislar el tenant afectado (2 minutos)

```bash
# Consultar que tenant tiene fallos
curl -s localhost:8000/metrics | grep medicare_integrity_failures

# O consultar directo a Prometheus
# sum(rate(medicare_integrity_failures_total[5m])) by (tenant)
```

Si el contador muestra `tenant="avalian"`, el problema está en ese tenant específico.

---

### Paso 2: Diagnosticar el registro fallido (5 minutos)

Conectar a PostgreSQL del tenant afectado y buscar registros con hash inválido:

```sql
-- 2a. Buscar evoluciones con hash de integridad invalido
SELECT id, paciente_id, created_at, hash_integridad
FROM evoluciones
WHERE tenant_id = (SELECT id FROM tenants WHERE slug = 'avalian')
  AND hash_integridad IS NOT NULL
  AND hash_integridad != (
      SELECT ENCODE(DIGEST(
          jsonb_build_object(
              'nota', nota,
              'diagnostico', diagnostico,
              'medicación', medicación
          )::TEXT,
          'sha256'
      ), 'hex')
  )
ORDER BY created_at DESC
LIMIT 10;

-- 2b. Buscar administracion_med con hash invalido
SELECT id, medicamento, created_at
FROM administracion_med
WHERE tenant_id = (SELECT id FROM tenants WHERE slug = 'avalian')
  AND hash_integridad != ENCODE(DIGEST(
      jsonb_build_object(
          'medicamento', medicamento,
          'dosis', dosis,
          'via', via,
          'estado', estado
      )::TEXT, 'sha256'
  ), 'hex')
LIMIT 10;
```

**Interpretación:**
- Si la query devuelve registros → hay discrepancias reales (posible tampering o corrupción)
- Si NO devuelve registros → el problema es en el formateo del JSON canónico del cliente

---

### Paso 3: Mitigación (3 minutos)

#### Caso A: Bug de serialización canónica en el cliente

```python
# El cliente movil debe usar sort_keys=True en json.dumps()
# Verificar que el firmware del dispositivo este actualizado a >= v2.1

# Fix inmediato: desactivar validación de hash para ese tenant
# (mientras se deploya el fix al dispositivo movil)
UPDATE tenants
SET config = jsonb_set(config, '{skip_hash_validation}', 'true')
WHERE slug = 'avalian';
```

#### Caso B: Data Tampering confirmado

```bash
# 1. Congelar el tenant: denegar nuevas operaciónes
# 2. Extraer respaldo inmediato del audit trail inmutable
cp -r .audit_logs/avalian /backup/forensics/$(date +%Y%m%d_%H%M)

# 3. Revisar audit trail en busca del responsable
python scripts/audit_integrity_check.py --tenant avalian

# 4. Notificar al equipo legal de la institucion
```

#### Caso C: Corrupción en tránsito (sync offline corrupto)

```python
# Recalcular hashes de los registros afectados
UPDATE evoluciones
SET hash_integridad = ENCODE(DIGEST(
    jsonb_build_object(
        'nota', nota,
        'diagnostico', diagnostico,
        'medicación', medicación
    )::TEXT, 'sha256'
), 'hex')
WHERE id IN (SELECT id FROM evoluciones WHERE hash_integridad IS NULL OR hash_integridad = '');
```

---

### Post-Incidente (dentro de 24h)

1. Agregar test unitario que reproduzca el bug de serialización
2. Actualizar firmware de dispositivos móviles
3. Revisar regla de Prometheus: ajustar threshold si hubo falso positivo
4. Documentar en `docs/POSTMORTEM.md`

---

### Contactos de escalada

| Rol | Nombre | Contacto |
|-----|--------|----------|
| SRE On-Call | Guardia SRE | sre@medicare-pro.app |
| DBA | DBA Team | dba@medicare-pro.app |
| Seguridad | CISO | ciso@medicare-pro.app |
