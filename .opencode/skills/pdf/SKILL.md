---
name: pdf
description: Generación de PDFs con fpdf2 y reportlab.
---

# PDF generation

## fpdf2 rules
- Siempre usar `pdf.output(dest="S")` que retorna `bytearray`
- Para descarga Streamlit: `st.download_button(..., data=bytes(pdf_bytes))`
- `.encode("latin-1")` SOLO en strings, nunca en bytes
- Pattern seguro:
  ```python
  pdf_bytes = pdf.output(dest="S")
  if isinstance(pdf_bytes, str):
      pdf_bytes = pdf_bytes.encode("latin-1")
  ```

## reportlab rules
- Usar `canvas.Canvas(buf, pagesize=...).` con `BytesIO` buffer
- Fuente: Helvetica por defecto (no requiere licencia)
- Encoding: `latin-1` para caracteres especiales

## Errores comunes
- `AttributeError: 'bytearray' object has no attribute 'encode'` → quitar `.encode()` o agregar type-check
- Fuentes TTF pueden no estar disponibles en Streamlit Cloud → evitar `add_font` con rutas locales
