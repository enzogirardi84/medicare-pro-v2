from pathlib import Path

from fpdf import FPDF


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
ASSETS_DIR = PROJECT_DIR / "assets"
OUTPUT_PATH = BASE_DIR / "Folleto_Comercial_MediCare_Enterprise_PRO.pdf"


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


def add_cover(pdf: FPDF, logo_path: Path | None) -> None:
    pdf.add_page()
    pdf.set_fill_color(8, 15, 34)
    pdf.rect(0, 0, 210, 297, style="F")
    pdf.set_fill_color(14, 165, 233)
    pdf.rect(0, 0, 210, 16, style="F")

    if logo_path:
        pdf.set_fill_color(255, 255, 255)
        pdf.rect(72, 32, 66, 48, style="F")
        pdf.image(str(logo_path), x=80, y=38, w=50)

    pdf.set_xy(18, 92)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 26)
    pdf.multi_cell(174, 12, "MediCare Enterprise PRO", align="C")

    pdf.set_text_color(110, 231, 255)
    pdf.set_font("Helvetica", "B", 15)
    pdf.ln(4)
    pdf.multi_cell(174, 8, "Gestion clinica, operativa y legal para empresas y profesionales de salud", align="C")

    pdf.ln(8)
    pdf.set_text_color(210, 223, 241)
    pdf.set_font("Helvetica", "", 12)
    pdf.multi_cell(
        174,
        7,
        "Control clinico, operativo y legal en una sola plataforma. Pensada para internacion domiciliaria, coordinacion, equipos en calle, emergencias y documentacion con respaldo.",
        align="C",
    )

    cards = [
        ("Pacientes y visitas", "Historia clinica, agenda, GPS, evoluciones, signos vitales y estudios."),
        ("Recetas y PDF legal", "Consentimientos, recetas, respaldo clinico y firmas trazables."),
        ("Coordinacion y RRHH", "Equipo, asistencia, auditoria, cierres y supervision operativa."),
        ("Emergencias", "Triage, traslados, tiempos y respaldo legal del evento."),
    ]
    x_positions = [18, 108]
    y_positions = [156, 218]
    idx = 0
    for y in y_positions:
        for x in x_positions:
            title, text = cards[idx]
            pdf.set_fill_color(17, 24, 39)
            pdf.set_draw_color(56, 189, 248)
            pdf.rect(x, y, 84, 46, style="DF")
            pdf.set_xy(x + 6, y + 6)
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("Helvetica", "B", 12)
            pdf.multi_cell(72, 6, title)
            pdf.set_x(x + 6)
            pdf.set_text_color(203, 213, 225)
            pdf.set_font("Helvetica", "", 9)
            pdf.multi_cell(72, 5, text)
            idx += 1


def add_section_title(pdf: FPDF, title: str, subtitle: str | None = None) -> None:
    pdf.set_text_color(10, 16, 36)
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, title, ln=1)
    if subtitle:
        pdf.set_text_color(71, 85, 105)
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(0, 6, subtitle)
    pdf.ln(2)


def add_bullet_card(pdf: FPDF, title: str, items: list[str], fill: tuple[int, int, int]) -> None:
    pdf.set_fill_color(*fill)
    pdf.set_draw_color(220, 229, 239)
    start_y = pdf.get_y()
    height = 12 + max(1, len(items)) * 9
    pdf.rect(14, start_y, 182, height, style="DF")
    pdf.set_xy(20, start_y + 6)
    pdf.set_text_color(15, 23, 42)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 6, title, ln=1)
    pdf.set_x(22)
    pdf.set_font("Helvetica", "", 10.5)
    for item in items:
        pdf.set_x(22)
        pdf.multi_cell(168, 6, f"- {item}")
    pdf.ln(2)


def add_inner_pages(pdf: FPDF) -> None:
    pdf.add_page()
    pdf.set_fill_color(245, 248, 252)
    pdf.rect(0, 0, 210, 297, style="F")

    add_section_title(
        pdf,
        "Que incluye la plataforma",
        "Una base comun para empresas, coordinacion, profesionales y servicios de emergencia.",
    )
    add_bullet_card(
        pdf,
        "Modulos principales",
        [
            "Historia clinica digital y evolucion medica.",
            "Visitas con agenda, estados y fichada GPS.",
            "Recetas, consentimientos y PDF legal.",
            "Estudios, adjuntos y escalas clinicas.",
            "Balance hidrico, pediatria y alertas clinicas.",
            "Emergencias, triage, traslados y ambulancia.",
            "RRHH, asistencia, auditoria y cierre diario.",
            "Red profesional y servicios domiciliarios.",
        ],
        (233, 246, 255),
    )
    add_bullet_card(
        pdf,
        "Beneficios para la empresa",
        [
            "Menor uso de papel y menos errores de carga.",
            "Mayor control sobre horarios, visitas y equipo.",
            "Informacion centralizada y ordenada.",
            "Respaldo legal frente a auditorias y reclamos.",
            "Una imagen mas profesional frente al paciente y la familia.",
        ],
        (236, 253, 245),
    )
    add_bullet_card(
        pdf,
        "Beneficios para el profesional",
        [
            "Trabajo desde el celular o la PC.",
            "Carga rapida de signos, evoluciones e indicaciones.",
            "Acceso a la historia del paciente al momento de atender.",
            "Menos tareas repetitivas y mejor seguimiento.",
        ],
        (240, 249, 255),
    )

    add_section_title(
        pdf,
        "Como vender la solucion",
        "Presentala segun el tipo de cliente para que vea rapido el valor.",
    )
    add_bullet_card(
        pdf,
        "Perfiles ideales",
        [
            "Empresas de internacion domiciliaria.",
            "Profesionales independientes de salud.",
            "Coordinacion operativa y administrativa.",
            "Ambulancias y servicios de emergencia.",
            "Instituciones o redes interdisciplinarias.",
        ],
        (249, 250, 251),
    )

    pdf.set_fill_color(14, 165, 233)
    pdf.rect(14, 248, 182, 34, style="F")
    pdf.set_xy(22, 257)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 7, "Solicita una demo personalizada", ln=1)
    pdf.set_x(22)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 6, "Presentacion comercial, demo funcional y propuesta adaptada a tu servicio.", ln=1)


def build_pdf() -> bytes:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    logo = pick_logo()
    add_cover(pdf, logo)
    add_inner_pages(pdf)
    return safe_pdf_bytes(pdf)


def main() -> None:
    OUTPUT_PATH.write_bytes(build_pdf())
    print(f"PDF_OK {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
