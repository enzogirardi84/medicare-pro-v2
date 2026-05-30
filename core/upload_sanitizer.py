"""Sanitizacion estricta de archivos subidos (estudios, PDFs, imagenes).
Verifica Magic Numbers (bytes reales, no solo extension),
renombra archivos con hash seguro y mitiga RCE.
"""

from __future__ import annotations

import hashlib
import os
import re
import time
from pathlib import Path
from typing import Optional, Tuple

from core.app_logging import log_event

# Magic numbers: (extension, bytes_reales, mime_type)
MAGIC_NUMBERS: list[Tuple[str, bytes, str]] = [
    ("pdf", b"%PDF", "application/pdf"),
    ("jpg", b"\xff\xd8\xff", "image/jpeg"),
    ("jpeg", b"\xff\xd8\xff", "image/jpeg"),
    ("png", b"\x89PNG\r\n\x1a\n", "image/png"),
    ("gif", b"GIF87a", "image/gif"),
    ("gif", b"GIF89a", "image/gif"),
    ("webp", b"RIFF", "image/webp"),  # WEBP starts with RIFF....WEBP
    ("bmp", b"BM", "image/bmp"),
    ("svg", b"<svg", "image/svg+xml"),
    ("txt", None, "text/plain"),  # Sin magic number, solo texto
]

MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg", ".txt"}

# Extensiones peligrosas bloqueadas (RCE)
BLOCKED_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".sh", ".ps1", ".vbs", ".js", ".jar",
    ".py", ".php", ".asp", ".aspx", ".jsp", ".war", ".dll", ".so",
    ".dmg", ".pkg", ".app", ".msi", ".scr", ".com", ".pif", ".vb",
    ".wsf", ".hta", ".cpl", ".mst", ".msp", ".msu", ".psm1", ".psd1",
    ".reg", ".inf",
}


def detectar_mime_por_magic(content: bytes) -> Optional[str]:
    """Detecta el tipo MIME real del archivo por sus bytes iniciales."""
    for ext, magic, mime in MAGIC_NUMBERS:
        if magic is None:
            continue
        if content[:len(magic)] == magic:
            # Verificacion extra para webp (debe contener "WEBP" en los bytes 8-12)
            if mime == "image/webp" and content[8:12] != b"WEBP":
                continue
            return mime
    return None


def sanitizar_archivo(
    nombre_original: str,
    contenido: bytes,
    max_size: int = MAX_FILE_SIZE_BYTES,
) -> Tuple[bool, str, Optional[dict]]:
    """Valida y sanitiza un archivo subido.

    Args:
        nombre_original: Nombre original del archivo.
        contenido: Contenido del archivo en bytes.
        max_size: Tamano maximo permitido en bytes.

    Returns:
        (ok, mensaje, info) donde info contiene:
            - nombre_seguro: Nombre con hash para almacenar
            - extension: Extension validada
            - mime: Tipo MIME real
            - sha256: Hash del contenido
            - tamano: Tamano en bytes
    """
    # 1. Verificar tamano
    file_size = len(contenido)
    if file_size == 0:
        return False, "El archivo esta vacio.", None
    if file_size > max_size:
        return False, f"El archivo excede el tamano maximo de {max_size // (1024*1024)} MB.", None

    # 2. Verificar extension
    ext = os.path.splitext(nombre_original)[1].lower()
    if ext in BLOCKED_EXTENSIONS:
        return False, f"Extension bloqueada por seguridad: {ext}", None
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"Extension no permitida: {ext}. Permitidas: {', '.join(sorted(ALLOWED_EXTENSIONS))}", None

    # 3. Verificar magic numbers (excepto txt que no tiene)
    mime = detectar_mime_por_magic(contenido)
    if mime is None and ext != ".txt":
        return False, "No se pudo verificar el tipo de archivo. El archivo puede estar corrupto o no coincidir con la extension.", None
    if mime and ext == ".txt":
        return False, "El archivo parece binario, no un archivo de texto.", None

    # 4. Generar nombre seguro con hash
    sha256 = hashlib.sha256(contenido).hexdigest()
    timestamp = int(time.time())
    nombre_seguro = f"{sha256[:16]}_{timestamp}{ext}"

    return True, "Archivo validado correctamente.", {
        "nombre_seguro": nombre_seguro,
        "extension": ext,
        "mime": mime or "text/plain",
        "sha256": sha256,
        "tamano": file_size,
    }


def sanitizar_nombre_archivo(nombre: str) -> str:
    """Limpia el nombre de archivo eliminando caracteres peligrosos."""
    # Eliminar caracteres no ASCII y peligrosos
    nombre = re.sub(r'[^\w\s.-]', '', nombre)
    # Limitar a 100 caracteres
    return nombre[:100]


def validar_estudio_adjunto(
    archivo_subido,
) -> Tuple[bool, str, Optional[dict]]:
    """Valida un archivo subido desde st.file_uploader.

    Args:
        archivo_subido: Objeto UploadedFile de Streamlit.

    Returns:
        (ok, mensaje, info) compatible con sanitizar_archivo().
    """
    if archivo_subido is None:
        return False, "No se selecciono ningun archivo.", None

    nombre_original = sanitizar_nombre_archivo(str(getattr(archivo_subido, "name", "archivo")))
    contenido = archivo_subido.read()
    archivo_subido.seek(0)  # Reset para Streamlit

    return sanitizar_archivo(nombre_original, contenido)
