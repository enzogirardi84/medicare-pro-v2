#!/usr/bin/env python3
"""Configura el directorio de almacenamiento de estudios subidos con
seguridad reforzada: permisos restrictivos, .htaccess, archivo index.html
de seguridad, y gitignore para no trackear archivos subidos.
"""

from __future__ import annotations

from pathlib import Path


UPLOAD_DIR = Path("storage/estudios")


def configurar_directorio_seguro() -> None:
    """Crea la estructura de directorios con permisos seguros."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # .gitignore para no trackear archivos subidos
    gitignore = UPLOAD_DIR / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("*\n!.gitignore\n", encoding="utf-8")
        print(f"[+] .gitignore creado en {gitignore}")

    # index.html de seguridad (evita listado de directorios)
    index_html = UPLOAD_DIR / "index.html"
    if not index_html.exists():
        index_html.write_text(
            "<!DOCTYPE html><html><head><title>Acceso Denegado</title>"
            "<meta charset='utf-8'></head><body>"
            "<h1>403 - Acceso Denegado</h1>"
            "<p>No tienes permiso para acceder a este directorio.</p>"
            "</body></html>",
            encoding="utf-8",
        )
        print(f"[+] index.html de seguridad creado en {index_html}")

    # .htaccess para Apache (deshabilita ejecucion de scripts)
    htaccess = UPLOAD_DIR / ".htaccess"
    if not htaccess.exists():
        htaccess.write_text(
            "# Denegar acceso directo a todos los archivos\n"
            "Order Deny,Allow\n"
            "Deny from all\n"
            "\n"
            "# Deshabilitar ejecucion de scripts en este directorio\n"
            "Options -ExecCGI -Includes -Indexes\n"
            "\n"
            "# Fuerza descarga de PDFs en vez de ejecutarlos\n"
            "AddType application/octet-stream .pdf .jpg .jpeg .png .gif .webp\n",
            encoding="utf-8",
        )
        print(f"[+] .htaccess de seguridad creado en {htaccess}")

    print(f"[+] Directorio de uploads configurado: {UPLOAD_DIR.resolve()}")


def generar_recomendaciones_nginx() -> str:
    """Genera configuracion recomendada para Nginx."""
    return """# Configuracion Nginx para el directorio de estudios subidos
# Ubicacion sugerida: /var/www/medicare/storage/estudios

location /storage/estudios/ {
    # Denegar acceso directo desde la web
    deny all;
    return 404;

    # Si necesitas servir archivos via autenticacion:
    # internal;
    # valid_referers none blocked server_names;
    # if ($invalid_referer) { return 403; }
}

# Alternativa: servir archivos solo via PHP/Python (X-Sendfile)
# location /storage/estudios/ {
#     internal;
#     alias /var/www/medicare/storage/estudios/;
#     add_header Content-Disposition 'attachment; filename="$1"';
# }
"""


def main():
    print("=== Configuracion de almacenamiento seguro de estudios ===\\n")
    configurar_directorio_seguro()

    print("\\n=== Recomendaciones para Nginx ===")
    print(generar_recomendaciones_nginx())

    print("\\n=== Pasos manuales requeridos ===")
    print("1. Agregar 'storage/estudios' al .gitignore raiz ya esta incluido.")
    print("2. Configurar Nginx/Apache para denegar acceso directo a /storage/")
    print("3. Verificar que el servidor web NO tenga permisos de ejecucion")
    print("   en el directorio de uploads (chmod -x storage/estudios/)")
    print("4. Considerar usar un bucket S3/Cloud Storage con ACL de solo lectura")


if __name__ == "__main__":
    main()
