"""
Corrector ortogr�fico integral para MediCare PRO.
Corrige:
1. Doble codificaci�n UTF-8 (mojibake): bytes Latin-1 re-codificados como UTF-8
2. Faltas de acentuaci�n en espa�ol
3. Errores ortogr�ficos comunes

Uso: python scripts/corrector_ortografico.py
"""

import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# ??? 1. Correcci�n de doble codificaci�n (mojibake) ????????????????????
# Texto que pas� por: original UTF-8 ? (le�do como Latin-1) ? re-codificado como UTF-8
# 
# Ejemplo: � (C3 B3 en UTF-8) le�do como Latin-1 da ó (C3 83 C2 B3 en UTF-8)
# Fix: encode('latin-1') recupera C3 B3, luego decode('utf-8') da '�'

def _fix_mojibake(text: str) -> str:
    """Corrige doble-codificaci�n UTF-8 ? Latin-1 ? UTF-8."""
    try:
        if '�' not in text and '�' not in text:
            return text, 0
        corrupted_bytes = text.encode('iso-8859-1', errors='replace')
        fixed = corrupted_bytes.decode('utf-8', errors='replace')
        diffs = sum(1 for a, b in zip(fixed, text) if a != b)
        return fixed, diffs
    except Exception:
        return text, 0


# ??? 2. Correcci�n de acentos comunes en espa�ol ?????????????????????

ACCENT_FIXES = {
    # Palabras agudas terminadas en -�n
    r'\b([Ii])nformacion\b': r'\1nformaci�n',
    r'\b([Cc])oordinacion\b': r'\1oordinaci�n',
    r'\b([Oo])peracion(es)?\b': r'\1peraci�n\2',
    r'\b([Aa])tencion(es)?\b': r'\1tenci�n\2',
    r'\b([Ss])olucion(es)?\b': r'\1oluci�n\2',
    r'\b([Oo])rganizacion(es)?\b': r'\1rganizaci�n\2',
    r'\b([Aa])plicacion(es)?\b': r'\1plicaci�n\2',
    r'\b([Dd])ocumentacion\b': r'\1ocumentaci�n',
    r'\b([Pp])resentacion(es)?\b': r'\1resentaci�n\2',
    r'\b([Ss])eccion(es)?\b': r'\1ecci�n\2',
    r'\b([Gg])estion\b': r'\1esti�n',
    r'\b([Rr])esolucion(es)?\b': r'\1esoluci�n\2',
    r'\b([Ss])incronizacion\b': r'\1incronizaci�n',
    r'\b([Vv])alidacion(es)?\b': r'\1alidaci�n\2',
    r'\b([Cc])onfiguracion(es)?\b': r'\1onfiguraci�n\2',
    r'\b([Vv])erificacion(es)?\b': r'\1erificaci�n\2',
    r'\b([Rr])epresentacion(es)?\b': r'\1epresentaci�n\2',
    r'\b([Vv])ariacion(es)?\b': r'\1ariaci�n\2',
    r'\b([Ii])ntegracion(es)?\b': r'\1ntegraci�n\2',
    r'\b([Ii])mplementacion(es)?\b': r'\1mplementaci�n\2',
    r'\b([Cc])omunicacion(es)?\b': r'\1omunicaci�n\2',
    r'\b([Pp])rogramacion\b': r'\1rogramaci�n',
    r'\b([Cc])ertificacion(es)?\b': r'\1ertificaci�n\2',
    r'\b([Aa])uditoria\b': r'\1uditor�a',
    r'\b([Ff])acturacion\b': r'\1acturaci�n',
    r'\b([Mm])edicacion\b': r'\1edicaci�n',
    r'\b([Aa])dmision\b': r'\1dmisi�n',
    r'\b([Ee])xportacion(es)?\b': r'\1xportaci�n\2',

    # Otras palabras con acento com�nmente omitido
    r'\btambien\b': 'tambi�n',
    r'\bTambien\b': 'Tambi�n',
    r'\b([Dd])ia\b': r'\1�a',
    r'\b([Mm])as\b': r'\1�s',  # adverbio de cantidad (contextual ? puede ser falso positivo)
    r'\b([Ee])sta\b(?=\s+[a�e�i�o�u�]\w*|\s+(?:en|por|para|con|sin|bajo|sobre|tras|ante))': r'\1st�',
    r'\b([Ee])sta\b(?=\s+(?:lista|preparado|configurado|disponible|activo|en|llegando|usando))': r'\1st�',
    r'\b([Cc])omo\b(?=[\s,;:]*(?:est[�a]|es[�a]|son|est�n|hacer|se|lo|la|los|las)\b)': r'\1�mo',
    r'\b([Dd])onde\b(?=[\s,;:]*(?:est[�a]|es|son)\b)': r'\1�nde',
    r'\b([Cc])ual\b(?=[\s,;:]*(?:es|son|fue|ser[�a])\b)': r'\1u�l',
    r'\b([Pp])odes\b': r'\1od�s',
    r'\b([Qq])ueres\b': r'\1uer�s',
    r'\b([Tt])enes\b': r'\1en�s',
    r'\brapidamente\b': 'r�pidamente',
    r'\b([Ee])specifico\b': r'\1spec�fico',
    r'\b([Pp])ractica\b(?=\s*(?:cl�nica|m�dica|profesional|\w*a\b))': r'\1r�ctica',
    r'\b([Tt])ecnica(s)?\b(?=\s*(?:de|del|en|y|,|\.|;))': r'\1�cnica\2',
    r'\b([Mm])edica(s)?\b(?=\s*(?:de|del|en|y|,|\.|;|(?!\w)))': r'\1�dica\2',
    r'\b([Pp])ublica\b(?=\s+\w)': r'\1�blica',
    r'\b([Ee])lectronico(s)?\b': r'\1lectr�nico\2',
    r'\b([Nn])umerico(s)?\b': r'\1um�rico\2',
    r'\b([Tt])elefono(s)?\b': r'\1el�fono\2',
    r'\b([Ss])olo\b(?!\s+(?:se|lo|la|los|las)\b)(?=\s+(?:con|por|en|para|un|una|el|la))': r'\1�lo',
}


def _fix_accents(text: str) -> str:
    """Corrige faltas de acentuaci�n comunes."""
    for pattern, replacement in ACCENT_FIXES.items():
        text = re.sub(pattern, replacement, text)
    return text


# ??? 3. Archivos a procesar ??????????????????????????????????????????

EXTENSIONES_INTERES = {'.py', '.md', '.html', '.txt', '.rst', '.yaml', '.yml', '.json', '.cfg', '.ini'}

EXCLUIR = {
    '.git',
    '__pycache__',
    '.venv',
    'node_modules',
    '.eggs',
    '*.pyc',
    '*.pyo',
    '.streamlit/secrets.toml',
    '.env*',
    'venv',
    '.audit_logs',
    '.opencode',
}


def _debe_excluir(path: Path) -> bool:
    """Verifica si el archivo o directorio debe ser excluido."""
    for excl in EXCLUIR:
        if excl.startswith('*'):
            if path.name.endswith(excl[1:]):
                return True
        elif excl.startswith('.'):
            if excl in str(path).replace('\\', '/'):
                return True
            if excl in path.name:
                return True
        elif excl in str(path):
            return True
    return False


# ??? 4. Procesamiento ????????????????????????????????????????????????

def _stats_text(text: str) -> dict:
    """Retorna estad�sticas de caracteres espa�oles."""
    es_chars = sum(1 for c in text if c in '�������������ܿ�')
    mojibake = sum(1 for c in text if c in '��')
    return {
        'length': len(text),
        'es_chars': es_chars,
        'mojibake': mojibake,
    }


def procesar_archivo(path: Path) -> dict:
    """Procesa un archivo: corrige mojibake y acentos."""
    try:
        original = path.read_bytes()
    except (OSError, PermissionError):
        return {'status': 'error', 'path': str(path), 'detail': 'no se pudo leer'}

    # Intentar detectar encoding
    for encoding in ['utf-8', 'latin-1', 'cp1252']:
        try:
            text = original.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        return {'status': 'error', 'path': str(path), 'detail': 'encoding no detectable'}

    stats_before = _stats_text(text)

    cambios = 0

    # 1. Corregir mojibake
    fixed, diffs = _fix_mojibake(text)
    cambios += diffs
    text = fixed

    # 2. Corregir acentos (solo en archivos que no son c�digo Python)
    # Python files: solo corregir si hay mojibake (que ya se corrigi� arriba)
    if path.suffix.lower() != '.py':
        fixed = _fix_accents(text)
        if fixed != text:
            diffs = sum(1 for a, b in zip(fixed, text) if a != b)
            cambios += diffs
            text = fixed

    if cambios == 0:
        return {'status': 'sin_cambios', 'path': str(path)}

    # Escribir
    try:
        path.write_bytes(text.encode('utf-8'))
    except (OSError, PermissionError) as e:
        return {'status': 'error', 'path': str(path), 'detail': str(e)}

    stats_after = _stats_text(text)

    return {
        'status': 'corregido',
        'path': str(path),
        'cambios': cambios,
        'es_chars_before': stats_before['es_chars'],
        'es_chars_after': stats_after['es_chars'],
        'mojibake_before': stats_before['mojibake'],
        'mojibake_after': stats_after['mojibake'],
    }


def main():
    archivos_procesados = 0
    corregidos = 0
    errores = 0
    total_cambios = 0

    for root, dirs, files in os.walk(REPO):
        root_path = Path(root)

        # Excluir directorios en el lugar
        dirs[:] = [d for d in dirs if not _debe_excluir(root_path / d)]

        for file in files:
            path = root_path / file
            if _debe_excluir(path):
                continue
            if path.suffix.lower() not in EXTENSIONES_INTERES:
                continue
            if path.stat().st_size > 5 * 1024 * 1024:  # > 5MB
                continue

            archivos_procesados += 1
            result = procesar_archivo(path)

            if result['status'] == 'corregido':
                corregidos += 1
                total_cambios += result.get('cambios', 0)
                es_after = result.get('es_chars_after', 0)
                mj_after = result.get('mojibake_after', 0)
                print(f"  OK {path.relative_to(REPO)} -- {result['cambios']} cambios, {es_after} acentos, {mj_after} mojibake")

            elif result['status'] == 'error':
                errores += 1
                print(f"  ERR {path.relative_to(REPO)} -- {result.get('detail', 'error')}")

    print()
    print("=" * 60)
    print(f"Archivos procesados: {archivos_procesados}")
    print(f"Archivos corregidos: {corregidos}")
    print(f"Total de cambios:   {total_cambios}")
    print(f"Errores:            {errores}")
    print("=" * 60)


if __name__ == '__main__':
    main()
