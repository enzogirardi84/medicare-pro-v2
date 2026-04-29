#!/usr/bin/env python3
"""Genera un PDF profesional a partir del manual de usuario en Markdown."""
import re
import sys
from pathlib import Path

try:
    from fpdf import FPDF
except ImportError:
    print("ERROR: fpdf2 no está instalado. Ejecutá: pip install fpdf2")
    sys.exit(1)


def parse_markdown(md_text: str):
    """Parsea Markdown básico a bloques tipados."""
    lines = md_text.splitlines()
    blocks = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Saltear líneas vacías sueltas
        if not stripped:
            i += 1
            continue

        # Horizontal rule
        if re.match(r"^---+\s*$", stripped):
            blocks.append(("hr", None))
            i += 1
            continue

        # Headers
        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            level = len(m.group(1))
            text = m.group(2).strip()
            blocks.append(("h", level, text))
            i += 1
            continue

        # Tablas
        if stripped.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(lines[i].strip())
                i += 1
            # Filtrar fila separadora |---|---|
            clean_rows = []
            for r in rows:
                if re.match(r"^\|[-:\s|]+\|$", r):
                    continue
                cells = [c.strip() for c in r.strip("|").split("|")]
                clean_rows.append(cells)
            if clean_rows:
                blocks.append(("table", clean_rows))
            continue

        # Bloques de código
        if stripped.startswith("```"):
            lang = stripped[3:].strip()
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # saltar cierre ```
            blocks.append(("code", lang, "\n".join(code_lines)))
            continue

        # Lista
        if re.match(r"^[-*]\s+", stripped):
            items = []
            while i < len(lines):
                s = lines[i].strip()
                if not s:
                    i += 1
                    continue
                if re.match(r"^[-*]\s+", s):
                    items.append(re.sub(r"^[-*]\s+", "", s))
                    i += 1
                else:
                    break
            if items:
                blocks.append(("ul", items))
            continue

        # Lista numerada
        if re.match(r"^\d+\.\s+", stripped):
            items = []
            while i < len(lines):
                s = lines[i].strip()
                if not s:
                    i += 1
                    continue
                m2 = re.match(r"^(\d+)\.\s+(.*)$", s)
                if m2:
                    items.append(m2.group(2))
                    i += 1
                else:
                    break
            if items:
                blocks.append(("ol", items))
            continue

        # Párrafo (puede tener bold, italic, inline code)
        para_lines = []
        while i < len(lines):
            s = lines[i].strip()
            if not s:
                break
            # No debe ser otro tipo de bloque
            if s.startswith("#") or s.startswith("|") or s.startswith("```") or re.match(r"^[-*]\s+", s) or re.match(r"^\d+\.\s+", s) or re.match(r"^---+\s*$", s):
                break
            para_lines.append(lines[i])
            i += 1
        if para_lines:
            blocks.append(("p", " ".join(para_lines)))
        continue

    return blocks


def clean_inline(text: str) -> str:
    """Quita marcado inline de Markdown y convierte a texto plano."""
    # **bold**
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    # *italic*
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    # `code`
    text = re.sub(r"`(.+?)`", r"\1", text)
    # [link](url)
    text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)
    # Escapes
    text = text.replace("\\*", "*").replace("\\`", "`")
    return text


class ManualPDF(FPDF):
    def __init__(self):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_doc_option("core_fonts_encoding", "utf-8")
        self.set_auto_page_break(auto=True, margin=20)
        self.set_margins(20, 20, 20)
        self._page_num = 0

    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, "MediCare Enterprise PRO - Manual de Usuario", ln=True, align="L")
        self.ln(2)
        self.set_draw_color(200, 200, 200)
        self.line(20, self.get_y(), 190, self.get_y())
        self.ln(3)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f"Página {self.page_no()}", align="C")

    def cover_page(self):
        self.add_page()
        self.set_font("Helvetica", "B", 28)
        self.set_text_color(30, 58, 95)  # #1e3a5f
        self.ln(60)
        self.cell(0, 15, "MediCare Enterprise PRO", ln=True, align="C")
        self.set_font("Helvetica", "B", 18)
        self.set_text_color(14, 165, 233)  # #0ea5e9
        self.cell(0, 12, "Manual de Usuario", ln=True, align="C")
        self.set_font("Helvetica", "", 11)
        self.set_text_color(100, 100, 100)
        self.ln(10)
        self.cell(0, 8, "Dirigido a personal de clínicas, centros de salud", ln=True, align="C")
        self.cell(0, 8, "y empresas de salud.", ln=True, align="C")
        self.ln(20)
        self.set_font("Helvetica", "", 9)
        self.cell(0, 6, "Versión: Build 2026-04-26", ln=True, align="C")
        self.cell(0, 6, "Fecha de generación: Abril 2026", ln=True, align="C")
        self.ln(30)
        self.set_draw_color(14, 165, 233)
        self.set_line_width(0.5)
        self.line(60, self.get_y(), 150, self.get_y())


def build_pdf(md_path: Path, out_path: Path):
    blocks = parse_markdown(md_path.read_text(encoding="utf-8"))
    pdf = ManualPDF()
    pdf.cover_page()

    for block in blocks:
        kind = block[0]

        if kind == "h":
            _, level, text = block
            text = clean_inline(text)
            if level == 1:
                pdf.add_page()
                pdf.set_font("Helvetica", "B", 18)
                pdf.set_text_color(30, 58, 95)
                pdf.set_fill_color(230, 242, 255)
                pdf.cell(0, 12, text, ln=True, fill=True)
                pdf.ln(4)
            elif level == 2:
                pdf.ln(4)
                pdf.set_font("Helvetica", "B", 14)
                pdf.set_text_color(30, 58, 95)
                pdf.cell(0, 10, text, ln=True)
                pdf.set_draw_color(14, 165, 233)
                pdf.line(20, pdf.get_y(), 190, pdf.get_y())
                pdf.ln(3)
            elif level == 3:
                pdf.ln(3)
                pdf.set_font("Helvetica", "B", 11)
                pdf.set_text_color(50, 80, 120)
                pdf.cell(0, 8, text, ln=True)
                pdf.ln(1)
            else:
                pdf.set_font("Helvetica", "B", 10)
                pdf.set_text_color(60, 60, 60)
                pdf.cell(0, 7, text, ln=True)
                pdf.ln(1)

        elif kind == "p":
            _, text = block
            text = clean_inline(text)
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(40, 40, 40)
            pdf.multi_cell(0, 6, text)
            pdf.ln(2)

        elif kind == "ul":
            _, items = block
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(40, 40, 40)
            for item in items:
                item = clean_inline(item)
                pdf.cell(5, 6, "", ln=0)
                pdf.set_x(25)
                pdf.multi_cell(0, 6, "• " + item)
            pdf.ln(2)

        elif kind == "ol":
            _, items = block
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(40, 40, 40)
            for idx, item in enumerate(items, 1):
                item = clean_inline(item)
                pdf.cell(5, 6, "", ln=0)
                pdf.set_x(25)
                pdf.multi_cell(0, 6, f"{idx}. {item}")
            pdf.ln(2)

        elif kind == "table":
            _, rows = block
            if not rows:
                continue
            # Calcular anchos proporcionales
            ncols = max(len(r) for r in rows)
            col_width = 170 / ncols
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_fill_color(230, 242, 255)
            pdf.set_text_color(30, 58, 95)
            for j, cell in enumerate(rows[0]):
                pdf.cell(col_width, 7, clean_inline(cell), border=1, fill=True, align="L")
            pdf.ln()
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(40, 40, 40)
            for row in rows[1:]:
                for j, cell in enumerate(row):
                    align = "L"
                    # Si parece número, centrar
                    if re.match(r"^\d+$", cell.strip()):
                        align = "C"
                    pdf.cell(col_width, 7, clean_inline(cell), border=1, align=align)
                pdf.ln()
            pdf.ln(3)

        elif kind == "code":
            _, lang, code = block
            pdf.set_font("Courier", "", 9)
            pdf.set_text_color(60, 60, 60)
            pdf.set_fill_color(245, 245, 245)
            pdf.multi_cell(0, 5, code, fill=True)
            pdf.ln(2)

        elif kind == "hr":
            pdf.set_draw_color(200, 200, 200)
            pdf.line(20, pdf.get_y(), 190, pdf.get_y())
            pdf.ln(4)

    pdf.output(str(out_path))
    print(f"PDF generado: {out_path}")


if __name__ == "__main__":
    repo = Path(__file__).resolve().parent
    md_file = repo / "MANUAL_USUARIO_MEDICARE_PRO.md"
    out_file = repo / "Manual_Usuario_MediCare_PRO.pdf"
    if not md_file.exists():
        print(f"No se encontró {md_file}")
        sys.exit(1)
    build_pdf(md_file, out_file)
