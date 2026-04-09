from pathlib import Path

from fpdf import FPDF


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
ASSETS_DIR = PROJECT_DIR / "assets"
OUTPUT_PATH = BASE_DIR / "Folleto_Comercial_MediCare_Enterprise_PRO.pdf"


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
    steps = 42
    width = 210 / steps
    for idx in range(steps):
        ratio = idx / max(steps - 1, 1)
        r = int(left[0] + (right[0] - left[0]) * ratio)
        g = int(left[1] + (right[1] - left[1]) * ratio)
        b = int(left[2] + (right[2] - left[2]) * ratio)
        pdf.set_fill_color(r, g, b)
        pdf.rect(idx * width, y, width + 1, h, style="F")


def draw_soft_card(pdf: FPDF, x: float, y: float, w: float, h: float, fill: tuple[int, int, int], border: tuple[int, int, int]) -> None:
    pdf.set_draw_color(*border)
    pdf.set_fill_color(*fill)
    pdf.rect(x, y, w, h, style="DF")


def add_cover(pdf: FPDF, logo_path: Path | None) -> None:
    pdf.add_page()
    pdf.set_fill_color(5, 12, 28)
    pdf.rect(0, 0, 210, 297, style="F")
    draw_gradient_band(pdf, 0, 22, (14, 165, 233), (79, 70, 229))
    draw_gradient_band(pdf, 230, 67, (15, 23, 42), (9, 14, 28))

    pdf.set_fill_color(17, 24, 39)
    pdf.rect(14, 32, 182, 176, style="F")
    pdf.set_draw_color(56, 189, 248)
    pdf.rect(14, 32, 182, 176, style="D")

    if logo_path:
        pdf.set_fill_color(255, 255, 255)
        pdf.rect(73, 44, 64, 46, style="F")
        pdf.image(str(logo_path), x=81, y=49, w=48)

    pdf.set_xy(18, 104)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 28)
    pdf.multi_cell(174, 13, "MediCare Enterprise PRO", align="C")

    pdf.ln(3)
    pdf.set_text_color(110, 231, 255)
    pdf.set_font("Helvetica", "B", 14)
    pdf.multi_cell(174, 8, "Software para gestion clinica, operativa y legal en salud", align="C")

    pdf.ln(7)
    pdf.set_text_color(210, 223, 241)
    pdf.set_font("Helvetica", "", 12)
    pdf.multi_cell(
        174,
        7,
        "Una sola plataforma para internacion domiciliaria, coordinacion, guardias, documentacion legal, control de personal, pacientes y trazabilidad completa.",
        align="C",
    )

    ribbons = [
        "Historia clinica digital",
        "Fichada GPS",
        "Recetas y firmas",
        "Auditoria legal",
        "Emergencias",
    ]
    x = 22
    y = 176
    for ribbon in ribbons:
        width = max(28, len(ribbon) * 2.35)
        if x + width > 188:
            x = 22
            y += 16
        pdf.set_fill_color(15, 23, 42)
        pdf.set_draw_color(71, 85, 105)
        pdf.rect(x, y, width, 11, style="DF")
        pdf.set_xy(x, y + 2.4)
        pdf.set_text_color(232, 240, 255)
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(width, 5, ribbon, align="C")
        x += width + 5

    pdf.set_xy(22, 241)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 8, "Ideal para empresas, coordinacion y profesionales de salud", ln=1)
    pdf.set_x(22)
    pdf.set_text_color(196, 208, 227)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(
        164,
        6,
        "Presenta una plataforma moderna, usable en PC y celular, con respaldo legal, control clinico y vision operativa lista para vender o implementar.",
    )


def add_section_title(pdf: FPDF, kicker: str, title: str, text: str) -> None:
    pdf.set_text_color(14, 165, 233)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, kicker.upper(), ln=1)
    pdf.set_text_color(10, 16, 36)
    pdf.set_font("Helvetica", "B", 22)
    pdf.multi_cell(0, 10, title)
    pdf.set_text_color(71, 85, 105)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 6, text)
    pdf.ln(3)


def add_feature_card(pdf: FPDF, x: float, y: float, title: str, items: list[str], accent: tuple[int, int, int]) -> None:
    draw_soft_card(pdf, x, y, 86, 58, (247, 250, 252), (226, 232, 240))
    pdf.set_fill_color(*accent)
    pdf.rect(x, y, 86, 7, style="F")
    pdf.set_xy(x + 5, y + 10)
    pdf.set_text_color(10, 16, 36)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(76, 6, title, ln=1)
    pdf.set_font("Helvetica", "", 9.5)
    pdf.set_text_color(71, 85, 105)
    for item in items[:4]:
        pdf.set_x(x + 5)
        pdf.multi_cell(74, 5, f"- {item}")


def add_value_page(pdf: FPDF) -> None:
    pdf.add_page()
    pdf.set_fill_color(245, 248, 252)
    pdf.rect(0, 0, 210, 297, style="F")
    draw_gradient_band(pdf, 0, 14, (14, 165, 233), (99, 102, 241))

    add_section_title(
        pdf,
        "Propuesta de valor",
        "Todo lo que necesita una operacion de salud en una sola app",
        "La plataforma ordena la atencion del paciente, la documentacion legal, la coordinacion operativa y la supervision del equipo en tiempo real.",
    )

    add_feature_card(
        pdf,
        14,
        52,
        "Atencion del paciente",
        [
            "Historia clinica y evolucion.",
            "Signos vitales y escalas.",
            "Estudios y adjuntos.",
            "Balance y pediatria.",
        ],
        (56, 189, 248),
    )
    add_feature_card(
        pdf,
        110,
        52,
        "Operacion diaria",
        [
            "Agenda y visitas.",
            "Fichada GPS real.",
            "Carga por profesional.",
            "Acciones rapidas en calle.",
        ],
        (34, 197, 94),
    )
    add_feature_card(
        pdf,
        14,
        118,
        "Respaldo legal",
        [
            "Recetas con firma.",
            "Consentimientos.",
            "PDF legal descargable.",
            "Auditoria de cambios.",
        ],
        (249, 115, 22),
    )
    add_feature_card(
        pdf,
        110,
        118,
        "Gestion y control",
        [
            "RRHH y asistencia.",
            "Cierre diario.",
            "Auditoria operativa.",
            "Dashboard ejecutivo.",
        ],
        (99, 102, 241),
    )

    draw_soft_card(pdf, 14, 190, 182, 74, (13, 21, 44), (56, 189, 248))
    pdf.set_xy(24, 203)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 8, "Que gana el cliente con MediCare Enterprise PRO", ln=1)
    pdf.set_x(24)
    pdf.set_text_color(203, 213, 225)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(
        160,
        7,
        "Menos papel, menos errores, mejor coordinacion, mas control del personal, mejor imagen frente al paciente y documentacion lista para auditorias, familiares o instituciones.",
    )
    pdf.set_xy(24, 238)
    pdf.set_text_color(110, 231, 255)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 6, "Usable desde celular o PC, con enfoque real para salud domiciliaria.", ln=1)


def add_sales_page(pdf: FPDF) -> None:
    pdf.add_page()
    pdf.set_fill_color(251, 252, 254)
    pdf.rect(0, 0, 210, 297, style="F")
    draw_gradient_band(pdf, 0, 14, (15, 23, 42), (30, 41, 59))

    add_section_title(
        pdf,
        "Venta y demo",
        "Como presentar la plataforma segun el tipo de cliente",
        "Muestra el sistema segun el perfil comercial para que el valor sea inmediato en la reunion.",
    )

    blocks = [
        (
            "Empresas de internacion domiciliaria",
            [
                "Control de pacientes, visitas y coordinacion.",
                "RRHH, auditoria, cierres y supervision.",
                "Documentacion legal lista para descargar.",
            ],
        ),
        (
            "Profesionales independientes",
            [
                "Visitas, historia clinica y contacto directo.",
                "Recetas, firmas y respaldo PDF.",
                "Uso simple desde el celular.",
            ],
        ),
        (
            "Ambulancias y emergencias",
            [
                "Triage por colores.",
                "Traslados, tiempos y parte legal.",
                "Seguimiento del evento y del paciente.",
            ],
        ),
        (
            "Instituciones y redes de salud",
            [
                "Perfiles por profesional o empresa.",
                "Servicios, zonas y disponibilidad.",
                "Coordinacion entre multiples actores.",
            ],
        ),
    ]

    y = 52
    accents = [(56, 189, 248), (34, 197, 94), (249, 115, 22), (99, 102, 241)]
    for idx, (title, items) in enumerate(blocks):
        draw_soft_card(pdf, 14, y, 182, 40, (255, 255, 255), (226, 232, 240))
        pdf.set_fill_color(*accents[idx % len(accents)])
        pdf.rect(14, y, 7, 40, style="F")
        pdf.set_xy(27, y + 7)
        pdf.set_text_color(10, 16, 36)
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(160, 6, title, ln=1)
        pdf.set_text_color(71, 85, 105)
        pdf.set_font("Helvetica", "", 10)
        for item in items:
            pdf.set_x(27)
            pdf.multi_cell(156, 5, f"- {item}")
        y += 48

    draw_soft_card(pdf, 14, 246, 182, 34, (14, 165, 233), (14, 165, 233))
    pdf.set_xy(20, 255)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 7, "Solicita demo, implementacion o propuesta comercial personalizada", ln=1)
    pdf.set_x(20)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 6, "Ideal para presentar por WhatsApp, mail o reuniones con clientes.", ln=1)


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
