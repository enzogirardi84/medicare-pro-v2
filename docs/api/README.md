# Medicare Pro API Documentation

## Descripción

API REST para Medicare Pro - Sistema de Gestión Clínica.

- **Versión actual:** v1.0.0
- **Base URL:** `https://api.medicare.local/v1`
- **Formato:** JSON
- **Autenticación:** JWT Bearer Token

---

## Índice

1. [Autenticación](#autenticación)
2. [Endpoints](#endpoints)
3. [Paginación](#paginación)
4. [Rate Limiting](#rate-limiting)
5. [Manejo de Errores](#manejo-de-errores)
6. [Webhooks](#webhooks)
7. [Ejemplos](#ejemplos)
8. [SDKs](#sdks)

---

## Autenticación

### JWT Bearer Token

Todas las peticiones (excepto login) requieren autenticación:

```http
Authorization: Bearer <token_jwt>
```

### Login

```http
POST /auth/login
Content-Type: application/json

{
  "username": "dr.perez",
  "password": "SecurePass123!",
  "pin": "1234"
}
```

**Respuesta exitosa:**

```json
{
  "success": true,
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "doctor@clinica.com",
    "nombre": "Dr. Juan Pérez",
    "rol": "medico"
  },
  "expires_at": "2024-12-31T23:59:59Z"
}
```

---

## Endpoints

### Pacientes

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/pacientes` | Listar pacientes |
| POST | `/pacientes` | Crear paciente |
| GET | `/pacientes/{id}` | Obtener paciente |
| PUT | `/pacientes/{id}` | Actualizar paciente |
| DELETE | `/pacientes/{id}` | Eliminar paciente |

### Evoluciones

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/pacientes/{id}/evoluciones` | Listar evoluciones |
| POST | `/pacientes/{id}/evoluciones` | Crear evolución |

### Signos Vitales

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/pacientes/{id}/vitales` | Obtener últimos signos vitales |
| POST | `/pacientes/{id}/vitales` | Registrar signos vitales |

### Recetas

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/pacientes/{id}/recetas` | Listar recetas |
| POST | `/pacientes/{id}/recetas` | Crear receta |

### Usuarios

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/users` | Listar usuarios |
| POST | `/users` | Crear usuario (admin) |
| GET | `/users/{id}` | Obtener usuario |
| PUT | `/users/{id}` | Actualizar usuario |
| DELETE | `/users/{id}` | Desactivar usuario |

---

## Paginación

Las listas están paginadas por defecto:

```http
GET /pacientes?page=2&per_page=50
```

**Respuesta:**

```json
{
  "data": [...],
  "pagination": {
    "page": 2,
    "per_page": 50,
    "total": 150,
    "total_pages": 3,
    "has_next": true,
    "has_prev": true
  }
}
```

---

## Rate Limiting

Límites por tipo de endpoint:

| Tipo | Límite | Ventana |
|------|--------|---------|
| Auth | 10 requests | 1 minuto |
| CRUD | 100 requests | 1 minuto |
| Reportes | 20 requests | 1 minuto |

**Headers de respuesta:**

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640995200
```

---

## Manejo de Errores

### Códigos de Error

| Código | HTTP | Descripción |
|--------|------|-------------|
| `VALIDATION_ERROR` | 400 | Datos inválidos |
| `UNAUTHORIZED` | 401 | Token inválido/expirado |
| `FORBIDDEN` | 403 | Sin permisos |
| `NOT_FOUND` | 404 | Recurso no existe |
| `RATE_LIMIT_EXCEEDED` | 429 | Límite excedido |
| `INTERNAL_ERROR` | 500 | Error interno |

### Formato de Error

```json
{
  "error_code": "VALIDATION_ERROR",
  "message": "Datos de entrada inválidos",
  "details": {
    "field": "email",
    "reason": "Formato inválido"
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

---

## Webhooks

### Eventos Soportados

- `paciente.created`
- `paciente.updated`
- `evolucion.created`
- `receta.created`

### Registrar Webhook

```http
POST /webhooks
Content-Type: application/json

{
  "url": "https://mi-sistema.com/webhook",
  "events": ["paciente.created", "evolucion.created"],
  "secret": "mi-secreto-webhook"
}
```

### Payload de Webhook

```json
{
  "event_type": "paciente.created",
  "timestamp": "2024-01-15T10:30:00Z",
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "dni": "12345678",
    "nombre": "María González"
  }
}
```

### Verificación de Firma

Los webhooks incluyen firma HMAC-SHA256:

```http
X-Webhook-Signature: sha256=abc123...
```

Verificar en tu servidor:

```python
import hmac
import hashlib

expected = hmac.new(
    secret.encode(),
    payload.encode(),
    hashlib.sha256
).hexdigest()

if f"sha256={expected}" == signature:
    # Webhook válido
```

---

## Ejemplos

### Crear Paciente

```bash
curl -X POST https://api.medicare.local/v1/pacientes \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "dni": "12345678",
    "nombre": "María",
    "apellido": "González",
    "fecha_nacimiento": "1985-06-15",
    "sexo": "F",
    "telefono": "+54 11 5555-1234",
    "obra_social": "OSDE"
  }'
```

### Buscar Pacientes

```bash
curl "https://api.medicare.local/v1/pacientes?q=gonzalez&obra_social=OSDE" \
  -H "Authorization: Bearer <token>"
```

### Crear Evolución

```bash
curl -X POST https://api.medicare.local/v1/pacientes/{id}/evoluciones \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "nota": "Paciente refiere dolor leve...",
    "diagnostico": "Lumbalgia",
    "tratamiento": "Reposo y analgésicos"
  }'
```

### Obtener Estadísticas

```bash
curl "https://api.medicare.local/v1/reportes/estadisticas?desde=2024-01-01&hasta=2024-01-31" \
  -H "Authorization: Bearer <token>"
```

---

## SDKs

### Python

```bash
pip install medicare-api-client
```

```python
from medicare_api import Client

client = Client(api_key="your-api-key")

# Crear paciente
paciente = client.pacientes.create({
    "dni": "12345678",
    "nombre": "María",
    "apellido": "González"
})

# Listar evoluciones
evoluciones = client.pacientes.evoluciones.list(paciente.id)
```

### JavaScript/TypeScript

```bash
npm install @medicare/api-client
```

```typescript
import { MedicareClient } from '@medicare/api-client';

const client = new MedicareClient({ apiKey: 'your-api-key' });

// Crear paciente
const paciente = await client.pacientes.create({
  dni: '12345678',
  nombre: 'María',
  apellido: 'González'
});

// Webhook handler
app.post('/webhook', (req, res) => {
  const event = req.body;
  
  switch (event.event_type) {
    case 'paciente.created':
      console.log('Nuevo paciente:', event.data);
      break;
  }
  
  res.sendStatus(200);
});
```

---

## Changelog

### v1.0.0 (2024-01-15)

- Lanzamiento inicial
- Autenticación JWT
- CRUD de pacientes, evoluciones, recetas
- Signos vitales
- Webhooks
- Reportes básicos

### v1.1.0 (Próximo)

- Filtros avanzados de búsqueda
- Exportación a Excel/PDF
- Notificaciones push
- Integraciones con laboratorios

---

## Soporte

- **Email:** soporte@medicare.local
- **Documentación:** https://docs.medicare.local
- **Status Page:** https://status.medicare.local

---

## Licencia

Esta API es propietaria. El uso está sujeto a los términos de servicio de Medicare Pro.
