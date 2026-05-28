"""Fix all copy-paste bugs from AutoHeal v1 across the codebase."""
import re

FIXES = [
    ("core/ai_features.py",
     'prompt += f"\\nÚltima evolución: {e(prompt += f"\\nÚltima evolución: {e.get(\'texto\') or \'\')[:300]}\\n"',
     'prompt += f"\\nÚltima evolución: {(e.get(\'texto\') or \'\')[:300]}\\n"'),
    ("core/connection_status.py",
     'with st.expander(f"\U0001f4cb {op.get(\'type\', \'Operación\')} - {op(with st.expander(f"\U0001f4cb {op.get(\'timestamp\') or \'Sin fecha\')[:10]}", expanded=False):',
     'with st.expander(f"\U0001f4cb {op.get(\'type\', \'Operación\')} - {(op.get(\'timestamp\') or \'Sin fecha\')[:10]}", expanded=False):'),
    ("core/guardado_emergencia.py",
     '"fecha": r("fecha": r.get(\'fecha_registro\') or \'\')[:16].replace(\'T\', \' \'),',
     '"fecha": (r.get(\'fecha_registro\') or \'\')[:16].replace(\'T\', \' \'),'),
    ("views/estudios.py",
     "label += f\" | {est(label += f\" | {est.get('detalle') or '')[:50]}...\"",
     "label += f\" | {(est.get('detalle') or '')[:50]}...\""),
    ("views/legal_docs.py",
     "rev_opts = {f\"{c(rev_opts = {f\"{c.get('fecha') or '')[:10]} - {c.get('firmante', '')}\": c for c in cons_pac_rev}",
     'rev_opts = {f"{(c.get(\'fecha\') or \'\')[:10]} - {c.get(\'firmante\', \'\')}": c for c in cons_pac_rev}'),
    ("views/self_healing_admin.py",
     'st.caption(f"**{e.get(\'level\', \'?\')}** \u2014 {e(st.caption(f"**{e.get(\'message\') or \'\')[:200]}")',
     'st.caption(f"**{e.get(\'level\', \'?\')}** \u2014 {(e.get(\'message\') or \'\')[:200]}")'),
    ("views/_evolucion_panel.py",
     'st.success(f"\u2705 Firma digital RSA {firma_digital.get(\'signature_algorithm\', \'\')} válida \u2014 {firma_digital.get(\'signer_name\', \'\')} ({firma_digital(st.success(f"\u2705 Firma digital RSA {firma_digital.get(\'signed_at\') or \'\')[:10]})")',
     'st.success(f"\u2705 Firma digital RSA {firma_digital.get(\'signature_algorithm\', \'\')} válida \u2014 {firma_digital.get(\'signer_name\', \'\')} ({(firma_digital.get(\'signed_at\') or \'\')[:10]})")'),
    ("views/_recetas_turno.py",
     'f"{r(f"{r.get(\'fecha\') or \'\')[:10].replace(\'/\',\'\')}_{ estado_arch}.pdf"',
     'f"{(r.get(\'fecha\') or \'\')[:10].replace(\'/\',\'\')}_{ estado_arch}.pdf"'),
]


def main():
    fixed = 0
    not_found = 0
    for relpath, search, replace in FIXES:
        with open(relpath, "r", encoding="utf-8") as f:
            content = f.read()

        if search in content:
            content = content.replace(search, replace)
            fixed += 1
            print(f"  ✅ {relpath}")
        else:
            not_found += 1
            print(f"  ❌ Not found in {relpath}")
            # Debug: show surrounding context
            idx = content.find(search[:30])
            if idx >= 0:
                print(f"     Found partial match at position {idx}")

        with open(relpath, "w", encoding="utf-8") as f:
            f.write(content)

    print(f"\n{'-' * 40}")
    print(f"  Fixes applied: {fixed}")
    print(f"  Not found: {not_found}")


if __name__ == "__main__":
    main()
