"""
Parte un export monolítico (mismo esquema que medicare_db.datos) en archivos por clínica.

Salida: .streamlit/data_store/tenants/<clave_normalizada>.json
Uso (desde la raíz del repo):
  python scripts/split_monolith_json_by_empresa.py .streamlit/local_data.json

Luego podés subir cada JSON a Supabase como fila con columnas tenant_key + datos.
La clave debe coincidir con norm_empresa_key (minúsculas, trim).
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / ".streamlit" / "data_store" / "tenants"


def norm_empresa_key(nombre: str) -> str:
    return str(nombre or "").strip().lower()


def empresas_desde_usuarios(data: dict) -> set[str]:
    out = set()
    for u in (data.get("usuarios_db") or {}).values():
        if isinstance(u, dict):
            k = norm_empresa_key(u.get("empresa", ""))
            if k:
                out.add(k)
    return out


def filtrar_monolito_por_empresa(data: dict, emp_key: str) -> dict:
    """Copia estructura; solo incluye registros de la empresa (heurística por campo empresa / paciente)."""
    pacientes_ok = set()
    for pid, det in (data.get("detalles_pacientes_db") or {}).items():
        if isinstance(det, dict) and norm_empresa_key(det.get("empresa", "")) == emp_key:
            pacientes_ok.add(pid)

    def emp_campo(obj, default=""):
        if not isinstance(obj, dict):
            return default
        return norm_empresa_key(obj.get("empresa", default))

    out = {}
    for k, v in data.items():
        if k == "usuarios_db" and isinstance(v, dict):
            out[k] = {login: u for login, u in v.items() if isinstance(u, dict) and emp_campo(u) == emp_key}
        elif k == "pacientes_db" and isinstance(v, list):
            out[k] = [p for p in v if p in pacientes_ok]
        elif k == "detalles_pacientes_db" and isinstance(v, dict):
            out[k] = {pid: d for pid, d in v.items() if pid in pacientes_ok}
        elif k == "clinicas_db" and isinstance(v, dict):
            cd = data.get("clinicas_db") or {}
            out[k] = {emp_key: cd[emp_key]} if emp_key in cd else {}
        elif k == "plantillas_whatsapp_db" and isinstance(v, dict):
            pv = v.get(emp_key) or v.get("_default")
            out[k] = {emp_key: pv} if pv is not None else {}
        elif isinstance(v, list):
            out[k] = [
                x
                for x in v
                if isinstance(x, dict)
                and (
                    emp_campo(x, None) == emp_key
                    or norm_empresa_key(x.get("empresa", "")) == emp_key
                    or (x.get("paciente") in pacientes_ok)
                )
            ]
        elif isinstance(v, dict):
            out[k] = v
        else:
            out[k] = v
    return out


def main():
    if len(sys.argv) < 2:
        print("Uso: python scripts/split_monolith_json_by_empresa.py <archivo.json>")
        sys.exit(1)
    path = Path(sys.argv[1])
    if not path.is_file():
        print("No existe:", path)
        sys.exit(1)
    data = json.loads(path.read_text(encoding="utf-8"))
    empresas = empresas_desde_usuarios(data)
    if not empresas:
        print("No se encontraron empresas en usuarios_db.")
        sys.exit(1)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for emp in sorted(empresas):
        chunk = filtrar_monolito_por_empresa(data, emp)
        out_path = OUT_DIR / f"{emp}.json"
        out_path.write_text(json.dumps(chunk, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print("Escrito", out_path, "usuarios:", len(chunk.get("usuarios_db") or {}))
    print("Listo. Revisá manualmente clinicas_db / registros sin campo empresa antes de producción.")


if __name__ == "__main__":
    main()
