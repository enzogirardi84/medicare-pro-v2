# 🧾 Medicare Billing Pro

**Sistema de Facturación Médica Profesional** — parte de la suite Medicare Pro.

## Módulos

| Módulo | Descripción |
|---|---|
| 🏢 **Clientes Fiscales** | ABM de clientes con datos impositivos (CUIT, condición fiscal) |
| 📝 **Presupuestos** | Creación de presupuestos multi-ítem, envío y conversión a pre-factura |
| 🧾 **Pre-facturas** | Documentos pre-factura con estados (Pendiente, Cobrada, Anulada) |
| 💰 **Historial de Cobros** | Registro de pagos con métodos, vinculación a pre-facturas |
| 📊 **Reportes para Contador** | Resúmenes mensuales con exportación Excel + PDF |

## Requisitos

- Python 3.10+
- Supabase (misma instancia que Medicare Pro)
- Credenciales de Medicare Pro (comparte tabla `usuarios`)

## Instalación

```bash
cd medicare_billing_pro
pip install -r requirements.txt
```

## Configuración

1. Copiá `.env.example` a `.env`
2. Completá `SUPABASE_URL` y `SUPABASE_KEY` (los mismos de Medicare Pro)
3. Ejecutá `migracion_supabase.sql` en el SQL Editor de Supabase

## Ejecutar

```bash
streamlit run main.py
```

## Produccion en internet

Billing Pro esta preparado para correr como servicio web separado en Render usando el `render.yaml` del repo.

Variables obligatorias:

```text
SUPABASE_URL=https://TU-PROYECTO.supabase.co
SUPABASE_KEY=TU_CLAVE_PUBLICABLE_O_SERVICE
SUPABASE_SERVICE_ROLE_KEY=TU_SERVICE_ROLE_KEY
BILLING_ALLOW_LOCAL_FALLBACK=false
BILLING_SECRET=valor-seguro-generado-para-produccion
```

Con `BILLING_ALLOW_LOCAL_FALLBACK=false`, los datos se guardan exclusivamente en Supabase. Ejecuta `migracion_supabase.sql` en Supabase antes de usar la app publicada.
La `SUPABASE_SERVICE_ROLE_KEY` debe quedar solo como variable del servidor (Render/Streamlit secrets), nunca en el navegador ni en el repositorio.

## Arquitectura

```
medicare_billing_pro/
├── main.py              # Entry point + navegación
├── core/
│   ├── config.py        # Variables de entorno y constantes
│   ├── app_logging.py   # Logging estructurado JSON
│   ├── auth.py          # Autenticación (compartida con Medicare Pro)
│   ├── db_sql.py        # Capa de datos (Supabase)
│   ├── utils.py         # Utilidades (moneda, fechas, etc.)
│   ├── pdf_export.py    # Exportación PDF (fpdf2)
│   └── excel_export.py  # Exportación Excel (openpyxl)
├── views/
│   ├── clientes.py      # Clientes Fiscales
│   ├── presupuestos.py  # Presupuestos
│   ├── prefacturas.py   # Pre-facturas
│   ├── cobros.py        # Historial de Cobros
│   └── reportes.py      # Reportes para Contador
├── requirements.txt
├── .env.example
└── migracion_supabase.sql
```

## Licencia

Parte de Medicare Pro Suite © 2026
