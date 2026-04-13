# MediCare — Alerta paciente (Flutter)

App **a prueba de panico** para pacientes: boton **NECESITO AYUDA**, cuadricula de **sintomas con iconos** (sin teclado), **cuenta regresiva de 3 segundos** y envio con **GPS** a Supabase (**Edge Function** `submit-alerta-paciente` → tabla `alertas_pacientes`).

## Flujo UX

1. **Inicio**: circulo rojo gigante **NECESITO AYUDA**.
2. **Sintomas**: tarjetas por triage **Rojo / Amarillo / Verde** (riesgo de vida, urgencia, consulta).
3. **Confirmacion**: cuenta regresiva **configurable (2–8 s)** en Ajustes; cancelar con X o **Cancelar**.
4. **Envio**: GPS + clasificacion a MediCare PRO. Si falla la red o el servidor, la alerta queda en **cola local** (hasta 15) y se reenvia desde el inicio con **Enviar ahora**.

## Accesibilidad y lectura

- **Texto mas grande** y **alto contraste** en **Configuracion** (se aplican en toda la app).
- Cola offline y cuenta regresiva se guardan en preferencias locales.

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

## Textos y errores de red

Los mensajes que ve el paciente (sin conexion, 401, URL invalida, sintomas, etc.) estan centralizados en `lib/l10n/app_strings.dart`. Hay tests en `test/` para la cola offline, el procesador de cola, `app_settings`, `url_utils`, `format_utils`, triage, arranque de la app y la URL de Edge Function. Al enviar pendientes con exito, se actualiza **Ultima alerta** como en un envio en vivo. En inicio, el icono de ajustes muestra **badge** con la cantidad en cola. **Deslizar hacia abajo** en la pantalla principal actualiza pendientes y ultima alerta (`RefreshIndicator`). La version en ajustes se lee con **package_info_plus** desde `pubspec.yaml` al compilar (sin archivo duplicado). En escritorio/web el scroll de listas acepta arrastre con mouse gracias a `MedicareScrollBehavior`. En **Configuracion**, los campos van en un `AutofillGroup` (URL, clinica, DNI, nombre, telefono) y el teclado puede avanzar con **Siguiente** entre campos.

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
