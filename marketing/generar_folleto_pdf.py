from pathlib import Path

from fpdf import FPDF


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
ASSETS_DIR = PROJECT_DIR / "assets"
OUTPUT_PATH = BASE_DIR / "Folleto_Comercial_MediCare_Enterprise_PRO.pdf"

BG = (6, 10, 24)
BG_SOFT = (11, 18, 37)
PANEL = (15, 24, 46)
PANEL_ALT = (20, 31, 58)
BORDER = (42, 75, 116)
SKY = (56, 189, 248)
BLUE = (59, 130, 246)
INDIGO = (99, 102, 241)
MINT = (45, 212, 191)
AMBER = (251, 146, 60)
WHITE = (255, 255, 255)
SLATE = (203, 213, 225)
SOFT = (148, 163, 184)


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
    steps = 72
    band_width = 210 / steps
    for idx in range(steps):
        ratio = idx / max(steps - 1, 1)
        color = (
            int(left[0] + (right[0] - left[0]) * ratio),
            int(left[1] + (right[1] - left[1]) * ratio),
            int(left[2] + (right[2] - left[2]) * ratio),
        )
        pdf.set_fill_color(*color)
        pdf.rect(idx * band_width, y, band_width + 1.5, h, style="F")


def draw_panel(
    pdf: FPDF,
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    fill: tuple[int, int, int] = PANEL,
    border: tuple[int, int, int] = BORDER,
    accent: tuple[int, int, int] | None = None,
) -> None:
    pdf.set_fill_color(*fill)
    pdf.set_draw_color(*border)
    pdf.rect(x, y, w, h, style="DF")
    if accent is not None:
        pdf.set_fill_color(*accent)
        pdf.rect(x, y, w, 4, style="F")


def add_page_shell(pdf: FPDF, page_label: str) -> None:
    pdf.add_page()
    pdf.set_fill_color(*BG)
    pdf.rect(0, 0, 210, 297, style="F")
    draw_gradient_band(pdf, 0, 14, SKY, INDIGO)
    draw_gradient_band(pdf, 284, 13, MINT, BLUE)
    draw_panel(pdf, 10, 20, 190, 258, fill=BG_SOFT, border=(28, 48, 82))
    pdf.set_xy(16, 282)
    pdf.set_text_color(*SOFT)
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(0, 4, f"MediCare Enterprise PRO  |  {page_label}", align="L")
    pdf.set_xy(174, 282)
    pdf.cell(20, 4, f"Pag. {pdf.page_no()}", align="R")


def add_logo(pdf: FPDF, logo_path: Path | None, *, x: float, y: float, w: float = 30) -> None:
    if not logo_path:
        return
    draw_panel(pdf, x - 6, y - 6, w + 12, w + 12, fill=WHITE, border=WHITE)
    pdf.image(str(logo_path), x=x, y=y, w=w)


def add_header(pdf: FPDF, kicker: str, title: str, body: str) -> None:
    pdf.set_text_color(*SKY)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(0, 5, kicker.upper(), ln=1)
    pdf.set_text_color(*WHITE)
    pdf.set_font("Helvetica", "B", 23)
    pdf.multi_cell(0, 10, title)
    pdf.ln(1)
    pdf.set_text_color(*SLATE)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 6, body)
    pdf.ln(5)


def add_pill(pdf: FPDF, x: float, y: float, text: str, fill: tuple[int, int, int]) -> float:
    width = max(32, len(text) * 2.2 + 10)
    draw_panel(pdf, x, y, width, 8.5, fill=fill, border=fill)
    pdf.set_xy(x, y + 2.1)
    pdf.set_text_color(*WHITE)
    pdf.set_font("Helvetica", "B", 8)
    pdf.cell(width, 4, text, align="C")
    return width


def add_cover(pdf: FPDF, logo_path: Path | None) -> None:
    add_page_shell(pdf, "Presentacion comercial")
    draw_panel(pdf, 18, 30, 174, 228, fill=PANEL, border=(44, 80, 124), accent=SKY)
    add_logo(pdf, logo_path, x=90, y=40, w=30)

    pdf.set_xy(28, 86)
    pdf.set_text_color(*WHITE)
    pdf.set_font("Helvetica", "B", 28)
    pdf.multi_cell(154, 12, "MediCare Enterprise PRO", align="C")

    pdf.set_xy(28, 121)
    pdf.set_text_color(*SKY)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(154, 6, "Software para gestion clinica, operativa y legal en salud", align="C", ln=1)

    pdf.set_xy(34, 140)
    pdf.set_text_color(*SLATE)
    pdf.set_font("Helvetica", "", 12)
    pdf.multi_cell(
        142,
        7,
        "Una sola plataforma para internacion domiciliaria, coordinacion, guardias, documentacion legal, control de personal, pacientes y trazabilidad completa.",
        align="C",
    )

    pills = [
        ("Historia clinica", SKY),
        ("Fichada GPS", BLUE),
        ("Recetas y firmas", INDIGO),
        ("Auditoria legal", MINT),
        ("Emergencias", AMBER),
    ]
    x = 34
    y = 184
    for text, fill in pills:
        width = add_pill(pdf, x, y, text, fill)
        x += width + 5
        if x > 152:
            x = 48
            y += 12

    draw_panel(pdf, 28, 222, 154, 24, fill=PANEL_ALT, border=(74, 126, 184), accent=INDIGO)
    pdf.set_xy(36, 232)
    pdf.set_text_color(*WHITE)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(138, 5, "Ideal para empresas, coordinacion y profesionales de salud", align="C")


def add_feature_box(pdf: FPDF, x: float, y: float, title: str, body: str, accent: tuple[int, int, int]) -> None:
    draw_panel(pdf, x, y, 84, 52, fill=PANEL_ALT, border=(44, 80, 124), accent=accent)
    pdf.set_xy(x + 6, y + 9)
    pdf.set_text_color(*WHITE)
    pdf.set_font("Helvetica", "B", 12)
    pdf.multi_cell(72, 5.5, title)
    pdf.set_x(x + 6)
    pdf.set_text_color(*SLATE)
    pdf.set_font("Helvetica", "", 9.2)
    pdf.multi_cell(72, 4.8, body)


def add_value_page(pdf: FPDF) -> None:
    add_page_shell(pdf, "Propuesta de valor")
    pdf.set_xy(16, 34)
    add_header(
        pdf,
        "Propuesta de valor",
        "Todo lo importante de una operacion de salud en una sola app",
        "La plataforma integra atencion del paciente, coordinacion diaria y respaldo legal para que el equipo trabaje con mas orden, menos errores y mejor imagen institucional.",
    )

    add_feature_box(pdf, 14, 72, "Atencion del paciente", "Historia clinica, evolucion, signos vitales, escalas y estudios en tiempo real.", SKY)
    add_feature_box(pdf, 112, 72, "Operacion diaria", "Agenda inteligente, fichada GPS, guardias y trabajo en calle sin perder trazabilidad.", BLUE)
    add_feature_box(pdf, 14, 136, "Respaldo legal", "Recetas, consentimientos, firmas, PDFs y auditoria lista para mostrar.", INDIGO)
    add_feature_box(pdf, 112, 136, "Control y gestion", "Dashboard, RRHH, cierres, inventario, caja y supervision operativa.", MINT)

    draw_panel(pdf, 14, 204, 182, 58, fill=PANEL, border=(52, 101, 153), accent=AMBER)
    pdf.set_xy(22, 216)
    pdf.set_text_color(*WHITE)
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 7, "Que gana el cliente con MediCare Enterprise PRO", ln=1)
    pdf.set_x(22)
    pdf.set_text_color(*SLATE)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(
        162,
        6.2,
        "Mas control, mejor coordinacion, menos dependencia de papel y WhatsApp, mas respaldo frente a auditorias y una plataforma preparada para crecer con la operacion.",
    )


def add_role_card(pdf: FPDF, x: float, y: float, title: str, items: list[str], accent: tuple[int, int, int]) -> None:
    draw_panel(pdf, x, y, 56, 108, fill=PANEL_ALT, border=(44, 80, 124), accent=accent)
    pdf.set_xy(x + 5, y + 9)
    pdf.set_text_color(*WHITE)
    pdf.set_font("Helvetica", "B", 11)
    pdf.multi_cell(46, 5.2, title)
    pdf.set_text_color(*SLATE)
    pdf.set_font("Helvetica", "", 8.9)
    for item in items:
        pdf.set_x(x + 5)
        pdf.multi_cell(46, 4.6, f"- {item}")


def add_roles_page(pdf: FPDF) -> None:
    add_page_shell(pdf, "Modulos y roles")
    pdf.set_xy(16, 34)
    add_header(
        pdf,
        "Modulos y roles",
        "Cada perfil ve lo que necesita para trabajar bien",
        "El profesional registra atencion del paciente. Coordinacion y administracion controlan agenda, personal, auditoria, indicadores y documentacion institucional.",
    )

    add_role_card(pdf, 14, 72, "Clinica y terreno", [
        "Visitas y agenda.",
        "Clinica.",
        "Evolucion.",
        "Estudios.",
        "Balance.",
        "Escalas clinicas.",
        "Telemedicina.",
    ], SKY)
    add_role_card(pdf, 77, 72, "Documentacion", [
        "Recetas.",
        "Consentimientos.",
        "Historia clinica.",
        "Respaldo PDF.",
        "Firmas digitales.",
        "Ordenes en papel.",
    ], INDIGO)
    add_role_card(pdf, 140, 72, "Control y gestion", [
        "Dashboard.",
        "Inventario.",
        "Caja.",
        "RRHH.",
        "Cierre diario.",
        "Auditoria legal.",
        "Red profesional.",
    ], MINT)

    draw_panel(pdf, 14, 194, 182, 66, fill=PANEL, border=(52, 101, 153), accent=BLUE)
    pdf.set_xy(22, 206)
    pdf.set_text_color(*WHITE)
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 7, "Seguridad funcional por rol", ln=1)
    pdf.set_x(22)
    pdf.set_text_color(*SLATE)
    pdf.set_font("Helvetica", "", 10.4)
    pdf.multi_cell(
        162,
        6,
        "Operativo, Enfermeria y Medico trabajan sobre la atencion del paciente. Administrativo gestiona admision y soporte interno. Coordinador y SuperAdmin visualizan la operacion completa.",
    )


def add_sales_block(pdf: FPDF, y: float, title: str, text: str, accent: tuple[int, int, int]) -> None:
    draw_panel(pdf, 14, y, 182, 35, fill=PANEL_ALT, border=(44, 80, 124), accent=accent)
    pdf.set_xy(22, y + 8)
    pdf.set_text_color(*WHITE)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 5, title, ln=1)
    pdf.set_x(22)
    pdf.set_text_color(*SLATE)
    pdf.set_font("Helvetica", "", 9.5)
    pdf.multi_cell(162, 4.7, text)


def add_sales_page(pdf: FPDF) -> None:
    add_page_shell(pdf, "Venta y demo")
    pdf.set_xy(16, 34)
    add_header(
        pdf,
        "Venta y demo",
        "Una presentacion clara para vender mejor",
        "MediCare Enterprise PRO puede mostrarse como solucion para empresas de salud, profesionales independientes, coordinacion, ambulancias y redes de atencion domiciliaria.",
    )

    blocks = [
        ("Empresas de internacion domiciliaria", "Pacientes, personal, visitas, fichadas, auditoria, RRHH y documentacion legal en un mismo sistema.", SKY),
        ("Profesionales independientes", "Visitas, historia clinica, recetas, firmas y respaldo PDF con uso simple desde el celular.", MINT),
        ("Ambulancias y emergencias", "Triage, traslados, tiempos de respuesta y registro legal del evento con enfoque operativo.", AMBER),
        ("Instituciones y redes de salud", "Coordinacion entre multiples perfiles, organizacion de roles, alertas y control institucional.", INDIGO),
    ]
    y = 72
    for title, text, accent in blocks:
        add_sales_block(pdf, y, title, text, accent)
        y += 43

    draw_panel(pdf, 14, 248, 182, 18, fill=SKY, border=SKY)
    pdf.set_xy(20, 254)
    pdf.set_text_color(*WHITE)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(170, 4, "Solicita demo, implementacion o propuesta comercial personalizada", align="C")


def build_pdf() -> bytes:
    pdf = BrochurePDF()
    pdf.set_auto_page_break(auto=True, margin=14)
    logo = pick_logo()
    add_cover(pdf, logo)
    add_value_page(pdf)
    add_roles_page(pdf)
    add_sales_page(pdf)
    return safe_pdf_bytes(pdf)


def main() -> None:
    OUTPUT_PATH.write_bytes(build_pdf())
    print(f"PDF_OK {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
