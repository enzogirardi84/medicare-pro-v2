from pathlib import Path

from fpdf import FPDF


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
ASSETS_DIR = PROJECT_DIR / "assets"
OUTPUT_PATH = BASE_DIR / "Folleto_Comercial_MediCare_Enterprise_PRO.pdf"

BG = (7, 12, 28)
BG_PANEL = (12, 21, 40)
BG_PANEL_SOFT = (18, 30, 54)
BORDER = (46, 82, 129)
SKY = (56, 189, 248)
BLUE = (59, 130, 246)
INDIGO = (99, 102, 241)
TEXT = (255, 255, 255)
TEXT_SOFT = (205, 216, 232)
TEXT_DIM = (148, 163, 184)


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


def gradient_band(pdf: FPDF, y: float, height: float, start: tuple[int, int, int], end: tuple[int, int, int]) -> None:
    steps = 80
    band_width = 210 / steps
    for idx in range(steps):
        ratio = idx / max(steps - 1, 1)
        color = (
            int(start[0] + (end[0] - start[0]) * ratio),
            int(start[1] + (end[1] - start[1]) * ratio),
            int(start[2] + (end[2] - start[2]) * ratio),
        )
        pdf.set_fill_color(*color)
        pdf.rect(idx * band_width, y, band_width + 1.2, height, style="F")


def panel(
    pdf: FPDF,
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    fill: tuple[int, int, int] = BG_PANEL,
    border: tuple[int, int, int] = BORDER,
    accent: tuple[int, int, int] | None = None,
) -> None:
    pdf.set_fill_color(*fill)
    pdf.set_draw_color(*border)
    pdf.rect(x, y, w, h, style="DF")
    if accent is not None:
        pdf.set_fill_color(*accent)
        pdf.rect(x, y, w, 4, style="F")


def add_page_shell(pdf: FPDF, label: str) -> None:
    pdf.add_page()
    pdf.set_fill_color(*BG)
    pdf.rect(0, 0, 210, 297, style="F")
    gradient_band(pdf, 0, 14, SKY, INDIGO)
    gradient_band(pdf, 283, 14, BLUE, SKY)
    panel(pdf, 10, 18, 190, 262, fill=(10, 18, 35), border=(32, 54, 88))
    pdf.set_xy(16, 283)
    pdf.set_text_color(*TEXT_DIM)
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(0, 4, f"MediCare Enterprise PRO | {label}", align="L")
    pdf.set_xy(174, 283)
    pdf.cell(18, 4, f"Pag. {pdf.page_no()}", align="R")


def add_logo(pdf: FPDF, logo_path: Path | None, *, x: float, y: float, w: float = 24) -> None:
    if not logo_path:
        return
    panel(pdf, x - 5, y - 5, w + 10, w + 10, fill=(250, 252, 255), border=(250, 252, 255))
    pdf.image(str(logo_path), x=x, y=y, w=w)


def add_header(pdf: FPDF, kicker: str, title: str, body: str) -> None:
    pdf.set_text_color(*SKY)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(0, 5, kicker.upper(), ln=1)
    pdf.set_text_color(*TEXT)
    pdf.set_font("Helvetica", "B", 23)
    pdf.multi_cell(0, 10, title)
    pdf.ln(1)
    pdf.set_text_color(*TEXT_SOFT)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 6, body)
    pdf.ln(4)


def add_badge(pdf: FPDF, x: float, y: float, text: str) -> float:
    width = max(38, len(text) * 2.15 + 12)
    panel(pdf, x, y, width, 8.5, fill=BG_PANEL_SOFT, border=(60, 97, 147), accent=SKY)
    pdf.set_xy(x, y + 2.1)
    pdf.set_text_color(*TEXT)
    pdf.set_font("Helvetica", "B", 8)
    pdf.cell(width, 4, text, align="C")
    return width


def add_cover(pdf: FPDF, logo_path: Path | None) -> None:
    add_page_shell(pdf, "Presentacion comercial")
    panel(pdf, 18, 28, 174, 230, fill=BG_PANEL, border=(40, 73, 118), accent=SKY)
    add_logo(pdf, logo_path, x=92, y=38, w=26)

    pdf.set_xy(28, 82)
    pdf.set_text_color(*TEXT)
    pdf.set_font("Helvetica", "B", 28)
    pdf.multi_cell(154, 11, "MediCare Enterprise PRO", align="C")

    pdf.set_xy(30, 116)
    pdf.set_text_color(*SKY)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(150, 6, "Gestion clinica, operativa y legal para salud real", align="C", ln=1)

    pdf.set_xy(34, 134)
    pdf.set_text_color(*TEXT_SOFT)
    pdf.set_font("Helvetica", "", 11.5)
    pdf.multi_cell(
        142,
        6.3,
        "Una sola plataforma para internacion domiciliaria, coordinacion diaria, visitas en calle, documentacion legal, control de personal, emergencias y trazabilidad completa.",
        align="C",
    )

    badges = ["Visitas con GPS", "Historia clinica", "Recetas y firmas", "Auditoria legal"]
    x = 30
    y = 176
    for text in badges:
        width = add_badge(pdf, x, y, text)
        x += width + 5
        if x > 154:
            x = 54
            y += 11

    panel(pdf, 28, 214, 154, 28, fill=BG_PANEL_SOFT, border=(56, 96, 148), accent=INDIGO)
    pdf.set_xy(36, 224)
    pdf.set_text_color(*TEXT)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(138, 5, "Ideal para empresas, coordinacion y profesionales de salud", align="C")


def add_info_card(pdf: FPDF, x: float, y: float, w: float, h: float, title: str, text: str) -> None:
    panel(pdf, x, y, w, h, fill=BG_PANEL_SOFT, border=(44, 80, 124), accent=BLUE)
    pdf.set_xy(x + 7, y + 10)
    pdf.set_text_color(*TEXT)
    pdf.set_font("Helvetica", "B", 12)
    pdf.multi_cell(w - 14, 5.5, title)
    pdf.set_x(x + 7)
    pdf.set_text_color(*TEXT_SOFT)
    pdf.set_font("Helvetica", "", 9.4)
    pdf.multi_cell(w - 14, 5, text)


def add_value_page(pdf: FPDF) -> None:
    add_page_shell(pdf, "Propuesta de valor")
    pdf.set_xy(16, 34)
    add_header(
        pdf,
        "Propuesta de valor",
        "Todo lo importante de una operacion de salud en una sola app",
        "MediCare Enterprise PRO integra atencion del paciente, coordinacion diaria y respaldo documental para que el equipo trabaje con mas orden, menos errores y mejor imagen institucional.",
    )

    add_info_card(pdf, 14, 74, 84, 56, "Atencion del paciente", "Historia clinica, evolucion, signos vitales, escalas, estudios y control clinico sin depender de papel o planillas sueltas.")
    add_info_card(pdf, 112, 74, 84, 56, "Operacion diaria", "Agenda inteligente, fichada GPS, guardias, control de visitas y trabajo en calle con trazabilidad real.")
    add_info_card(pdf, 14, 144, 84, 56, "Respaldo legal", "Recetas, consentimientos, firmas digitales y PDFs preparados para mostrar frente a auditorias o instituciones.")
    add_info_card(pdf, 112, 144, 84, 56, "Gestion y control", "Dashboard, RRHH, cierres, inventario, caja y supervision operativa desde una sola plataforma.")

    panel(pdf, 14, 214, 182, 48, fill=BG_PANEL, border=(56, 96, 148), accent=SKY)
    pdf.set_xy(22, 226)
    pdf.set_text_color(*TEXT)
    pdf.set_font("Helvetica", "B", 17)
    pdf.cell(0, 7, "Que gana tu equipo con MediCare Enterprise PRO", ln=1)
    pdf.set_x(22)
    pdf.set_text_color(*TEXT_SOFT)
    pdf.set_font("Helvetica", "", 10.2)
    pdf.multi_cell(
        162,
        5.8,
        "Mas control, mejor coordinacion, menos dependencia de WhatsApp y papel, mas respaldo frente a auditorias y una base preparada para crecer con la operacion.",
    )


def add_role_card(pdf: FPDF, x: float, y: float, title: str, subtitle: str, items: list[str]) -> None:
    panel(pdf, x, y, 56, 118, fill=BG_PANEL_SOFT, border=(44, 80, 124), accent=INDIGO)
    pdf.set_xy(x + 6, y + 10)
    pdf.set_text_color(*TEXT)
    pdf.set_font("Helvetica", "B", 11.5)
    pdf.multi_cell(44, 5.2, title)
    pdf.set_x(x + 6)
    pdf.set_text_color(*SKY)
    pdf.set_font("Helvetica", "B", 8.4)
    pdf.multi_cell(44, 4.2, subtitle)
    pdf.set_x(x + 6)
    pdf.set_text_color(*TEXT_SOFT)
    pdf.set_font("Helvetica", "", 8.7)
    for item in items:
        pdf.set_x(x + 6)
        pdf.multi_cell(44, 4.5, f"- {item}")


def add_roles_page(pdf: FPDF) -> None:
    add_page_shell(pdf, "Roles y modulos")
    pdf.set_xy(16, 34)
    add_header(
        pdf,
        "Roles y modulos",
        "Cada perfil ve lo que necesita para trabajar bien",
        "El profesional registra la atencion del paciente. Administracion, coordinacion y control institucional visualizan la operacion completa segun el rol asignado.",
    )

    add_role_card(
        pdf,
        14,
        76,
        "Profesional asistencial",
        "Trabajo clinico y en calle",
        [
            "Visitas y agenda.",
            "Clinica.",
            "Evolucion.",
            "Estudios.",
            "Balance.",
            "Escalas.",
            "Telemedicina.",
            "Recetas para ver indicaciones.",
        ],
    )
    add_role_card(
        pdf,
        77,
        76,
        "Coordinacion y gestion",
        "Operacion y supervision",
        [
            "Dashboard.",
            "Cierre diario.",
            "Mi equipo.",
            "Asistencia en vivo.",
            "RRHH.",
            "Auditoria.",
            "Inventario.",
            "Caja.",
        ],
    )
    add_role_card(
        pdf,
        140,
        76,
        "Empresa o red de salud",
        "Control integral",
        [
            "Auditoria legal.",
            "Red profesional.",
            "Emergencias.",
            "Documentacion PDF.",
            "Trazabilidad completa.",
            "Soporte para celular y PC.",
        ],
    )

    panel(pdf, 14, 214, 182, 48, fill=BG_PANEL, border=(56, 96, 148), accent=BLUE)
    pdf.set_xy(22, 226)
    pdf.set_text_color(*TEXT)
    pdf.set_font("Helvetica", "B", 17)
    pdf.cell(0, 7, "Seguridad funcional por rol", ln=1)
    pdf.set_x(22)
    pdf.set_text_color(*TEXT_SOFT)
    pdf.set_font("Helvetica", "", 10.1)
    pdf.multi_cell(
        162,
        5.8,
        "Admin y Coordinador visualizan el sistema completo. El profesional de salud accede al circuito asistencial del paciente sin cargarlo con tareas administrativas o de control interno.",
    )


def add_sales_card(pdf: FPDF, y: float, title: str, text: str) -> None:
    panel(pdf, 14, y, 182, 34, fill=BG_PANEL_SOFT, border=(44, 80, 124), accent=SKY)
    pdf.set_xy(22, y + 8)
    pdf.set_text_color(*TEXT)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 5, title, ln=1)
    pdf.set_x(22)
    pdf.set_text_color(*TEXT_SOFT)
    pdf.set_font("Helvetica", "", 9.4)
    pdf.multi_cell(162, 4.8, text)


def add_contact_box(pdf: FPDF, x: float, y: float, title: str, role: str, whatsapp: str, email: str) -> None:
    panel(pdf, x, y, 84, 46, fill=BG_PANEL_SOFT, border=(44, 80, 124), accent=INDIGO)
    pdf.set_xy(x + 7, y + 8)
    pdf.set_text_color(*TEXT)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(70, 5, title, ln=1)
    pdf.set_x(x + 7)
    pdf.set_text_color(*SKY)
    pdf.set_font("Helvetica", "B", 8.4)
    pdf.cell(70, 4, role, ln=1)
    pdf.set_x(x + 7)
    pdf.set_text_color(*TEXT_SOFT)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(70, 5, f"WhatsApp: {whatsapp}", ln=1)
    pdf.set_x(x + 7)
    pdf.cell(70, 5, email, ln=1)


def add_sales_page(pdf: FPDF) -> None:
    add_page_shell(pdf, "Venta y demo")
    pdf.set_xy(16, 34)
    add_header(
        pdf,
        "Venta y demo",
        "Una presentacion clara para vender mejor",
        "MediCare Enterprise PRO puede mostrarse como solucion para internacion domiciliaria, coordinacion, ambulancias, profesionales independientes y redes de atencion en salud.",
    )

    blocks = [
        ("Empresas de internacion domiciliaria", "Pacientes, personal, visitas, fichadas, auditoria, RRHH y documentacion legal en un mismo sistema."),
        ("Profesionales independientes", "Visitas, historia clinica, recetas, firmas y respaldo PDF con uso simple desde el celular."),
        ("Ambulancias y emergencias", "Triage, traslados, tiempos de respuesta y registro legal del evento con enfoque operativo."),
        ("Instituciones y redes de salud", "Coordinacion entre multiples perfiles, organizacion de roles, alertas y control institucional."),
    ]
    y = 74
    for title, text in blocks:
        add_sales_card(pdf, y, title, text)
        y += 40

    add_contact_box(pdf, 14, 236, "Enzo N. Girardi", "Desarrollo y soporte tecnico", "3584302024", "enzonicolasgirardi@gmail.com")
    add_contact_box(pdf, 112, 236, "Dario Lanfranco", "Implementacion y contratos", "3584201263", "dariolanfrancoruffener@gmail.com")


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
