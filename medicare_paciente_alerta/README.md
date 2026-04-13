# MediCare — Alerta paciente (Flutter)

App **a prueba de panico** para pacientes: boton **NECESITO AYUDA**, cuadricula de **sintomas con iconos** (sin teclado), **cuenta regresiva de 3 segundos** y envio con **GPS** a Supabase (**Edge Function** `submit-alerta-paciente` → tabla `alertas_pacientes`).

## Flujo UX

1. **Inicio**: circulo rojo gigante **NECESITO AYUDA**.
2. **Sintomas**: tarjetas por triage **Rojo / Amarillo / Verde** (riesgo de vida, urgencia, consulta).
3. **Confirmacion**: 3…2…1…; cancelar con X o **Cancelar**.
4. **Envio**: GPS + clasificacion a MediCare PRO.

## Supabase

1. SQL: `../supabase/alertas_pacientes.sql`
2. Secreto: `PATIENT_ALERT_INGEST_SECRET` (Edge Functions → Secrets)
3. Deploy: `supabase functions deploy submit-alerta-paciente --no-verify-jwt`

En la app (**Configuracion**): URL proyecto, clave **anon**, **secreto**, **clinica** (minusculas = empresa en MediCare), **DNI o codigo paciente**.

## JSON que envia la Edge Function

```json
{
  "paciente_id": "12345678",
  "sintoma": "Dolor de pecho",
  "nivel_urgencia": "Rojo",
  "empresa_clave": "clinica girardi",
  "latitud": -34.6,
  "longitud": -58.4,
  "precision_m": 12,
  "fecha_hora": "2026-04-10T18:00:00.000Z"
}
```

## MediCare web

- **Sidebar**: bloque pulsante rojo si hay **Rojo + Pendiente** para tu clinica.
- **Banner** debajo del panel de bienvenida con el mismo aviso.
- Modulo **Alertas app paciente**: tabla, filtros, mapa, CSV, estados **Pendiente / En camino / Resuelto**.

## PIN / login

La identificacion es el **paciente_id** configurado (DNI o codigo de legajo). Un **PIN local** reforzado contra servidor puede agregarse en una siguiente iteracion.

## Requisitos

- Flutter 3.24+ recomendado.
- `flutter create . --org com.medicare` si faltan carpetas `android/` / `ios/`.

## GPS y telefono

- Permisos segun [geolocator](https://pub.dev/packages/geolocator).
- iOS: `LSApplicationQueriesSchemes` con `tel` si falla el marcador.

## Notas

- **Sonido** en navegador para coordinadores: muchos bloquean autoplay; hoy el aviso es **visual** (sidebar + banner).
- **WhatsApp** para triage Amarillo: no incluido; se puede enlazar a tu API de mensajeria despues.
- **Asignacion por GPS al enfermero mas cercano**: requiere cruzar alertas con fichajes; no esta en este commit.
