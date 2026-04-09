from pathlib import Path

from fpdf import FPDF


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
ASSETS_DIR = PROJECT_DIR / "assets"
OUTPUT_PATH = BASE_DIR / "Folleto_Comercial_MediCare_Enterprise_PRO.pdf"

NAVY = (7, 15, 32)
NAVY_SOFT = (14, 26, 47)
CARD = (17, 31, 56)
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
    steps = 64
    width = 210 / steps
    for idx in range(steps):
        ratio = idx / max(steps - 1, 1)
        r = int(left[0] + (right[0] - left[0]) * ratio)
        g = int(left[1] + (right[1] - left[1]) * ratio)
        b = int(left[2] + (right[2] - left[2]) * ratio)
        pdf.set_fill_color(r, g, b)
        pdf.rect(idx * width, y, width + 1.5, h, style="F")


def draw_panel(
    pdf: FPDF,
    x: float,
    y: float,
    w: float,
    h: float,
    fill: tuple[int, int, int] = CARD,
    border: tuple[int, int, int] = (45, 88, 127),
    accent: tuple[int, int, int] | None = None,
) -> None:
    pdf.set_fill_color(*fill)
    pdf.set_draw_color(*border)
    pdf.rect(x, y, w, h, style="DF")
    if accent is not None:
        pdf.set_fill_color(*accent)
        pdf.rect(x, y, w, 5, style="F")


def add_page_shell(pdf: FPDF) -> None:
    pdf.set_fill_color(*NAVY)
    pdf.rect(0, 0, 210, 297, style="F")
    draw_gradient_band(pdf, 0, 16, SKY, INDIGO)
    draw_gradient_band(pdf, 284, 13, MINT, SKY)
    pdf.set_draw_color(26, 48, 78)
    pdf.rect(10, 22, 190, 258, style="D")


def add_header(pdf: FPDF, kicker: str, title: str, body: str) -> None:
    pdf.set_text_color(*SKY)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(0, 5, kicker.upper(), ln=1)
    pdf.set_text_color(*WHITE)
    pdf.set_font("Helvetica", "B", 22)
    pdf.multi_cell(0, 10, title)
    pdf.ln(1)
    pdf.set_text_color(*SLATE)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 6, body)
    pdf.ln(5)


def add_logo_lockup(pdf: FPDF, logo_path: Path | None, x: float, y: float, w: float = 48) -> None:
    if logo_path:
        draw_panel(pdf, x - 6, y - 6, w + 12, w + 12, fill=WHITE, border=WHITE)
        pdf.image(str(logo_path), x=x, y=y, w=w)


def add_pill(pdf: FPDF, x: float, y: float, text: str, fill: tuple[int, int, int]) -> float:
    width = max(32, len(text) * 2.2 + 10)
    draw_panel(pdf, x, y, width, 9, fill=fill, border=fill)
    pdf.set_xy(x, y + 2.1)
    pdf.set_text_color(*WHITE)
    pdf.set_font("Helvetica", "B", 8)
    pdf.cell(width, 4, text, align="C")
    return width


def add_cover(pdf: FPDF, logo_path: Path | None) -> None:
    pdf.add_page()
    add_page_shell(pdf)

    draw_panel(pdf, 18, 32, 174, 232, fill=NAVY_SOFT, border=(46, 84, 128), accent=SKY)
    add_logo_lockup(pdf, logo_path, 81, 46, 42)

    pdf.set_xy(30, 104)
    pdf.set_text_color(*SKY)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(150, 6, "SOFTWARE PARA SALUD REAL", align="C", ln=1)

    pdf.set_xy(30, 116)
    pdf.set_text_color(*WHITE)
    pdf.set_font("Helvetica", "B", 28)
    pdf.multi_cell(150, 12, "MediCare Enterprise PRO", align="C")

    pdf.set_xy(34, 150)
    pdf.set_text_color(*SLATE)
    pdf.set_font("Helvetica", "", 12)
    pdf.multi_cell(
        142,
        7,
        "Gestiona pacientes, visitas, recetas, consentimientos, emergencias, personal y auditoria desde una sola plataforma pensada para PC y celular.",
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
    y = 186
    for text, fill in pills:
        width = add_pill(pdf, x, y, text, fill)
        x += width + 5
        if x > 152:
            x = 52
            y += 13

    draw_panel(pdf, 30, 228, 150, 22, fill=(9, 22, 41), border=(70, 119, 171))
    pdf.set_xy(36, 234)
    pdf.set_text_color(*WHITE)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(138, 5, "Ideal para internacion domiciliaria, coordinacion y equipos en calle.", align="C")


def add_feature_box(pdf: FPDF, x: float, y: float, title: str, lines: list[str], accent: tuple[int, int, int]) -> None:
    draw_panel(pdf, x, y, 84, 56, fill=CARD, border=(46, 78, 114), accent=accent)
    pdf.set_xy(x + 6, y + 10)
    pdf.set_text_color(*WHITE)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(72, 5, title, ln=1)
    pdf.set_text_color(*SLATE)
    pdf.set_font("Helvetica", "", 9.2)
    for line in lines:
        pdf.set_x(x + 6)
        pdf.multi_cell(72, 4.8, f"- {line}")


def add_value_page(pdf: FPDF) -> None:
    pdf.add_page()
    add_page_shell(pdf)
    pdf.set_xy(16, 34)
    add_header(
        pdf,
        "Propuesta de valor",
        "Todo lo importante de una operacion de salud en una sola app",
        "La plataforma integra el trabajo clinico, la coordinacion diaria y el respaldo legal para que el equipo trabaje con mas orden, menos errores y mejor imagen institucional.",
    )

    add_feature_box(pdf, 14, 68, "Atencion del paciente", [
        "Historia clinica y evolucion.",
        "Signos vitales y escalas.",
        "Estudios y adjuntos.",
        "Balance y pediatria.",
    ], SKY)
    add_feature_box(pdf, 112, 68, "Operacion diaria", [
        "Agenda inteligente.",
        "Fichada GPS real.",
        "Acciones rapidas en calle.",
        "Carga por profesional.",
    ], BLUE)
    add_feature_box(pdf, 14, 134, "Respaldo legal", [
        "Recetas con firma.",
        "Consentimientos.",
        "PDF institucional.",
        "Auditoria de cambios.",
    ], INDIGO)
    add_feature_box(pdf, 112, 134, "Gestion y control", [
        "RRHH y asistencia.",
        "Cierre diario.",
        "Dashboard ejecutivo.",
        "Auditoria operativa.",
    ], MINT)

    draw_panel(pdf, 14, 206, 182, 58, fill=(10, 23, 43), border=(56, 113, 167), accent=AMBER)
    pdf.set_xy(22, 218)
    pdf.set_text_color(*WHITE)
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 7, "Que gana el cliente con MediCare Enterprise PRO", ln=1)
    pdf.set_x(22)
    pdf.set_text_color(*SLATE)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(
        162,
        6.5,
        "Mas control, mejor coordinacion, menos dependencia de papel y WhatsApp, mas trazabilidad legal y una plataforma preparada para crecer con la operacion.",
    )


def add_module_column(pdf: FPDF, x: float, y: float, title: str, items: list[str], accent: tuple[int, int, int]) -> None:
    draw_panel(pdf, x, y, 56, 106, fill=CARD, border=(46, 78, 114), accent=accent)
    pdf.set_xy(x + 5, y + 10)
    pdf.set_text_color(*WHITE)
    pdf.set_font("Helvetica", "B", 11)
    pdf.multi_cell(46, 5, title, align="L")
    pdf.set_text_color(*SLATE)
    pdf.set_font("Helvetica", "", 8.9)
    for item in items:
        pdf.set_x(x + 5)
        pdf.multi_cell(46, 4.7, f"- {item}")


def add_modules_page(pdf: FPDF) -> None:
    pdf.add_page()
    add_page_shell(pdf)
    pdf.set_xy(16, 34)
    add_header(
        pdf,
        "Modulos",
        "Una plataforma pensada para roles clinicos, operativos y de coordinacion",
        "Cada usuario ve lo que necesita para trabajar. El profesional registra la atencion; coordinacion y administracion controlan agenda, auditoria, personal y documentacion.",
    )

    add_module_column(pdf, 14, 68, "Clinica y terreno", [
        "Visitas y agenda.",
        "Clinica.",
        "Evolucion.",
        "Estudios.",
        "Balance.",
        "Escalas clinicas.",
        "Telemedicina.",
    ], SKY)
    add_module_column(pdf, 77, 68, "Documentacion", [
        "Recetas.",
        "Consentimientos.",
        "Historia clinica.",
        "Respaldo PDF.",
        "Firmas digitales.",
        "Carga de orden en papel.",
    ], INDIGO)
    add_module_column(pdf, 140, 68, "Control y gestion", [
        "Dashboard.",
        "Inventario.",
        "Caja.",
        "RRHH.",
        "Cierre diario.",
        "Auditoria legal.",
        "Red profesional.",
    ], MINT)

    draw_panel(pdf, 14, 188, 182, 76, fill=(10, 23, 43), border=(56, 113, 167), accent=BLUE)
    pdf.set_xy(22, 198)
    pdf.set_text_color(*WHITE)
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 7, "Roles por usuario y control real", ln=1)
    pdf.set_x(22)
    pdf.set_text_color(*SLATE)
    pdf.set_font("Helvetica", "", 10.4)
    pdf.multi_cell(
        162,
        6,
        "Operativo, Enfermeria y Medico acceden al registro clinico del paciente. Administrativo trabaja con admision y gestion. Coordinador y SuperAdmin ven toda la operacion completa.",
    )
    pdf.ln(2)
    pdf.set_x(22)
    pdf.set_text_color(*WHITE)
    pdf.set_font("Helvetica", "B", 10)
    pdf.multi_cell(
        162,
        5.5,
        "Esto mejora seguridad, orden interno, trazabilidad y evita que cada perfil vea mas de lo necesario.",
    )


def add_sales_block(pdf: FPDF, y: float, title: str, text: str, accent: tuple[int, int, int]) -> None:
    draw_panel(pdf, 14, y, 182, 36, fill=CARD, border=(46, 78, 114), accent=accent)
    pdf.set_xy(24, y + 8)
    pdf.set_text_color(*WHITE)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 5, title, ln=1)
    pdf.set_x(24)
    pdf.set_text_color(*SLATE)
    pdf.set_font("Helvetica", "", 9.4)
    pdf.multi_cell(160, 4.8, text)


def add_sales_page(pdf: FPDF) -> None:
    pdf.add_page()
    add_page_shell(pdf)
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

    y = 70
    for title, text, accent in blocks:
        add_sales_block(pdf, y, title, text, accent)
        y += 46

    draw_panel(pdf, 14, 258, 182, 16, fill=SKY, border=SKY)
    pdf.set_xy(20, 263)
    pdf.set_text_color(*WHITE)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(170, 4, "Solicita demo, implementacion o propuesta comercial personalizada", align="C")


def build_pdf() -> bytes:
    pdf = BrochurePDF()
    pdf.set_auto_page_break(auto=True, margin=14)
    logo = pick_logo()
    add_cover(pdf, logo)
    add_value_page(pdf)
    add_modules_page(pdf)
    add_sales_page(pdf)
    return safe_pdf_bytes(pdf)


def main() -> None:
    OUTPUT_PATH.write_bytes(build_pdf())
    print(f"PDF_OK {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
