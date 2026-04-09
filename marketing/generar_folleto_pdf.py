from pathlib import Path

from fpdf import FPDF


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
ASSETS_DIR = PROJECT_DIR / "assets"
OUTPUT_PATH = BASE_DIR / "Folleto_Comercial_MediCare_Enterprise_PRO.pdf"

NAVY = (7, 15, 32)
NAVY_SOFT = (18, 31, 55)
SKY = (56, 189, 248)
BLUE = (59, 130, 246)
INDIGO = (99, 102, 241)
MINT = (45, 212, 191)
WHITE = (255, 255, 255)
SLATE = (203, 213, 225)
PALE = (226, 232, 240)


class BrochurePDF(FPDF):
    pass


def pick_logo() -> Path | None:
    for name in ("logo_medicare_pro.jpeg", "logo_medicare_pro.jpg", "logo_medicare_pro.png"):
        path = ASSETS_DIR / name
        if path.exists():
            return path
    return None


def safe_pdf_bytes(pdf: FPDF) -> bytes:
    payload = pdf.output(dest="S")
    if isinstance(payload, (bytes, bytearray)):
        return bytes(payload)
    return str(payload).encode("latin-1", errors="replace")


def draw_gradient_band(pdf: FPDF, y: float, h: float, left: tuple[int, int, int], right: tuple[int, int, int]) -> None:
    steps = 52
    width = 210 / steps
    for idx in range(steps):
        ratio = idx / max(steps - 1, 1)
        r = int(left[0] + (right[0] - left[0]) * ratio)
        g = int(left[1] + (right[1] - left[1]) * ratio)
        b = int(left[2] + (right[2] - left[2]) * ratio)
        pdf.set_fill_color(r, g, b)
        pdf.rect(idx * width, y, width + 1, h, style="F")


def draw_card(pdf: FPDF, x: float, y: float, w: float, h: float, fill: tuple[int, int, int], border: tuple[int, int, int]) -> None:
    pdf.set_fill_color(*fill)
    pdf.set_draw_color(*border)
    pdf.rect(x, y, w, h, style="DF")


def add_page_shell(pdf: FPDF) -> None:
    pdf.set_fill_color(*NAVY)
    pdf.rect(0, 0, 210, 297, style="F")
    draw_gradient_band(pdf, 0, 16, SKY, INDIGO)
    pdf.set_draw_color(22, 163, 208)
    pdf.rect(10, 24, 190, 258, style="D")


def add_cover(pdf: FPDF, logo_path: Path | None) -> None:
    pdf.add_page()
    add_page_shell(pdf)

    draw_card(pdf, 20, 38, 170, 196, NAVY_SOFT, SKY)

    if logo_path:
        draw_card(pdf, 74, 50, 62, 50, WHITE, WHITE)
        pdf.image(str(logo_path), x=80, y=56, w=50)

    pdf.set_xy(24, 116)
    pdf.set_text_color(*WHITE)
    pdf.set_font("Helvetica", "B", 25)
    pdf.multi_cell(162, 12, "MediCare Enterprise PRO", align="C")

    pdf.ln(4)
    pdf.set_text_color(*SKY)
    pdf.set_font("Helvetica", "B", 14)
    pdf.multi_cell(162, 8, "Software para gestion clinica, operativa y legal en salud", align="C")

    pdf.ln(6)
    pdf.set_text_color(*SLATE)
    pdf.set_font("Helvetica", "", 12)
    pdf.multi_cell(
        162,
        7,
        "Una plataforma creada para empresas, coordinacion y profesionales de salud que necesitan ordenar pacientes, visitas, documentacion legal y supervision operativa en un solo lugar.",
        align="C",
    )

    pills = [
        "Historia clinica",
        "Recetas y firmas",
        "Fichada GPS",
        "Auditoria legal",
        "Emergencias",
    ]
    x = 31
    y = 188
    for pill in pills:
        width = max(26, len(pill) * 2.45)
        if x + width > 174:
            x = 45
            y += 15
        draw_card(pdf, x, y, width, 10, NAVY, (71, 85, 105))
        pdf.set_xy(x, y + 2.1)
        pdf.set_text_color(*WHITE)
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(width, 5, pill, align="C")
        x += width + 4

    pdf.set_xy(26, 236)
    pdf.set_text_color(*WHITE)
    pdf.set_font("Helvetica", "B", 16)
    pdf.multi_cell(158, 8, "Ideal para internacion domiciliaria, coordinacion, auditoria y equipos en calle.", align="C")

    pdf.set_xy(26, 258)
    pdf.set_text_color(*SLATE)
    pdf.set_font("Helvetica", "", 10.5)
    pdf.multi_cell(158, 6, "Preparado para demo comercial, propuestas institucionales y envio por WhatsApp o correo.", align="C")


def add_section_title(pdf: FPDF, kicker: str, title: str, text: str) -> None:
    pdf.set_text_color(*SKY)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, kicker.upper(), ln=1)
    pdf.set_text_color(*WHITE)
    pdf.set_font("Helvetica", "B", 21)
    pdf.multi_cell(0, 10, title)
    pdf.set_text_color(*SLATE)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 6, text)
    pdf.ln(4)


def add_feature_card(pdf: FPDF, x: float, y: float, title: str, items: list[str], accent: tuple[int, int, int]) -> None:
    draw_card(pdf, x, y, 86, 62, NAVY_SOFT, (46, 64, 95))
    pdf.set_fill_color(*accent)
    pdf.rect(x, y, 86, 6, style="F")
    pdf.set_xy(x + 6, y + 10)
    pdf.set_text_color(*WHITE)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(74, 6, title, ln=1)
    pdf.set_text_color(*SLATE)
    pdf.set_font("Helvetica", "", 9.5)
    for item in items[:4]:
        pdf.set_x(x + 6)
        pdf.multi_cell(72, 5, f"- {item}")


def add_value_page(pdf: FPDF) -> None:
    pdf.add_page()
    add_page_shell(pdf)
    pdf.set_xy(16, 32)
    add_section_title(
        pdf,
        "Propuesta de valor",
        "Todo lo que necesita una operacion de salud en una sola app",
        "La misma experiencia visual, clinica y operativa de la plataforma, llevada a una presentacion comercial clara y lista para vender.",
    )

    add_feature_card(pdf, 14, 64, "Atencion del paciente", [
        "Historia clinica y evolucion.",
        "Signos vitales y escalas.",
        "Estudios y adjuntos.",
        "Balance y pediatria.",
    ], SKY)
    add_feature_card(pdf, 110, 64, "Operacion diaria", [
        "Agenda y visitas.",
        "Fichada GPS real.",
        "Carga por profesional.",
        "Acciones rapidas en calle.",
    ], MINT)
    add_feature_card(pdf, 14, 134, "Respaldo legal", [
        "Recetas con firma.",
        "Consentimientos.",
        "PDF legal descargable.",
        "Auditoria de cambios.",
    ], (249, 115, 22))
    add_feature_card(pdf, 110, 134, "Gestion y control", [
        "RRHH y asistencia.",
        "Cierre diario.",
        "Auditoria operativa.",
        "Dashboard ejecutivo.",
    ], INDIGO)

    draw_card(pdf, 14, 208, 182, 56, (11, 23, 44), SKY)
    pdf.set_xy(22, 220)
    pdf.set_text_color(*WHITE)
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 8, "Que gana el cliente con MediCare Enterprise PRO", ln=1)
    pdf.set_x(22)
    pdf.set_text_color(*SLATE)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(
        162,
        7,
        "Menos errores, mas orden, mejor imagen institucional, trazabilidad completa y una plataforma preparada para PC y celular con foco en salud real.",
    )


def add_sales_block(pdf: FPDF, y: float, title: str, text: str, accent: tuple[int, int, int]) -> None:
    draw_card(pdf, 14, y, 182, 42, NAVY_SOFT, (46, 64, 95))
    pdf.set_fill_color(*accent)
    pdf.rect(14, y, 8, 42, style="F")
    pdf.set_xy(28, y + 7)
    pdf.set_text_color(*WHITE)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(158, 6, title, ln=1)
    pdf.set_x(28)
    pdf.set_text_color(*SLATE)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(156, 5, text)


def add_sales_page(pdf: FPDF) -> None:
    pdf.add_page()
    add_page_shell(pdf)
    pdf.set_xy(16, 32)
    add_section_title(
        pdf,
        "Venta y demo",
        "Como presentar la plataforma segun el tipo de cliente",
        "Muestra el sistema de acuerdo con el perfil del comprador para que el valor sea inmediato en la reunion.",
    )

    blocks = [
        ("Empresas de internacion domiciliaria", "Control de pacientes, coordinacion, RRHH, auditoria, cierres y documentacion legal lista para descargar.", SKY),
        ("Profesionales independientes", "Visitas, historia clinica, recetas, firmas y respaldo PDF con uso simple desde el celular.", MINT),
        ("Ambulancias y emergencias", "Triage, traslados, tiempos de respuesta y parte legal del evento en un mismo entorno.", (249, 115, 22)),
        ("Instituciones y redes de salud", "Perfiles profesionales, zonas, disponibilidad y coordinacion entre multiples actores de la atencion.", INDIGO),
    ]

    y = 70
    for title, text, accent in blocks:
        add_sales_block(pdf, y, title, text, accent)
        y += 50

    draw_card(pdf, 14, 244, 182, 30, SKY, SKY)
    pdf.set_xy(22, 253)
    pdf.set_text_color(*WHITE)
    pdf.set_font("Helvetica", "B", 15)
    pdf.cell(0, 7, "Solicita demo, implementacion o propuesta comercial personalizada", ln=1)


def build_pdf() -> bytes:
    pdf = BrochurePDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    logo = pick_logo()
    add_cover(pdf, logo)
    add_value_page(pdf)
    add_sales_page(pdf)
    return safe_pdf_bytes(pdf)


def main() -> None:
    OUTPUT_PATH.write_bytes(build_pdf())
    print(f"PDF_OK {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
