# Arquitectura objetivo

## Capas

1. Cliente (backoffice/web/mobile)
2. API de negocio (FastAPI)
3. Servicios de dominio
4. Persistencia (PostgreSQL + Redis + Object Storage)
5. Observabilidad y seguridad

## Principios

- API-first
- Multi-tenant por `tenant_id`
- RLS en datos clinicos
- Colas para tareas pesadas
- Escalado horizontal stateless

## Modulos principales

- Auth y permisos
- Pacientes
- Visitas/evolucion
- Indicaciones/recetas
- Auditoria legal
- Reportes y exportaciones
