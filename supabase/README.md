# Supabase Setup

## Objetivo

Esta carpeta prepara dos modos de trabajo:

1. Compatibilidad inmediata con la app actual
2. Migracion seria a estructura normalizada para escalar

## Archivos

- `schema.sql`: tabla compatible + tablas normalizadas
- `storage.sql`: buckets sugeridos para adjuntos, firmas y documentos legales

## Estrategia

### Fase 1

Ejecutar `schema.sql` y usar la tabla `medicare_db`.
Con esto la app actual puede funcionar con Supabase sin reescribir todo el backend.

### Fase 2

Migrar gradualmente a tablas:

- pacientes
- detalles_paciente
- indicaciones
- evoluciones
- estudios
- emergencias
- cuidados_enfermeria
- escalas_clinicas
- auditoria_legal
- consentimientos

## Storage

Usar buckets separados para:

- estudios e imagenes
- firmas
- pdfs y respaldos legales
