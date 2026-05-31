"""Batch optimization: cache queries, DataFrames, mobile columns."""
import re
from pathlib import Path


def add_mobile_grid_css():
    path = "assets/mobile.css"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    grid = """
/* stHorizontalBlock en mobile: grid 2 columnas en vez de apilar */
@media screen and (max-width: 768px) {
    section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"],
    [data-testid="stHorizontalBlock"] {
        flex-direction: row !important;
        flex-wrap: wrap !important;
    }
    [data-testid="stHorizontalBlock"] > div {
        min-width: 45% !important;
        flex: 1 1 45% !important;
    }
}
"""
    insert_pos = content.rfind("@media (pointer: coarse)")
    if insert_pos > 0:
        content = content[:insert_pos] + grid + content[insert_pos:]
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print("CSS grid added")
    else:
        print("Could not find insertion point")


def add_query_cache(filepath, line_num, query_regex, cache_fn_name, cache_code):
    """Add a @st.cache_data decorated function before the specified line."""
    path = Path(filepath)
    lines = path.read_text(encoding="utf-8").split("\n")

    # Check if cache function already exists
    if any(cache_fn_name in l for l in lines):
        print(f"  Already cached: {filepath}")
        return

    # Find the line
    for i, line in enumerate(lines):
        if query_regex in line and i >= line_num - 5:
            # Insert cache function before this function's definition
            insert_idx = i
            while insert_idx > 0 and not lines[insert_idx].strip().startswith("def "):
                insert_idx -= 1
            if insert_idx > 0:
                indent = " " * 4
                cache_block = (
                    f"\n{indent}@st.cache_data(ttl=300, show_spinner=False)\n"
                    f"{indent}def {cache_fn_name}(empresa_uuid: str) -> list:\n"
                    f'{indent}    """Cache de {cache_fn_name} con TTL 300s."""\n'
                    f"{indent}    from core.database import supabase\n"
                    f"{indent}    try:\n"
                    f'{indent}        res = supabase.table("usuarios").select("*").eq("empresa_id", empresa_uuid).execute()\n'
                    f"{indent}        return res.data or []\n"
                    f"{indent}    except Exception:\n"
                    f"{indent}        return []\n"
                )
                lines.insert(insert_idx, cache_block)
                path.write_text("\n".join(lines), encoding="utf-8")
                print(f"  Cache added: {filepath}")
                return

    print(f"  Query not found: {filepath}")


def main():
    print("Adding CSS grid for mobile columns...")
    add_mobile_grid_css()

    print("\nDone. Run 'git diff' to review changes.")


if __name__ == "__main__":
    main()
