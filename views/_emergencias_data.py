"""Datos y helpers de emergencias. Extraído de views/emergencias.py."""
import base64
import io

from PIL import Image


EVENTO_CATEGORIAS = {
    "Cardiovascular": [
        "IAM / Infarto agudo de miocardio",
        "Dolor toracico de probable origen cardiaco",
        "Arritmia / palpitaciones",
        "Paro cardiorrespiratorio",
        "Insuficiencia cardiaca aguda / edema agudo de pulmon",
        "Crisis hipertensiva",
        "Sindrome coronario agudo",
    ],
    "Neurologico": [
        "ACV / Stroke",
        "Convulsion",
        "TEC grave",
        "TEC moderado",
        "TEC leve",
        "Perdida de conocimiento / sincope",
        "Deficit neurologico agudo",
        "Cefalea intensa / alarma neurologica",
    ],
    "Respiratorio": [
        "Dificultad respiratoria",
        "Insuficiencia respiratoria aguda",
        "Broncoespasmo / crisis asmatica",
        "EPOC reagudizado",
        "Neumonia / foco respiratorio",
        "Paro respiratorio",
        "Saturacion critica",
    ],
    "Trauma": [
        "Caida de propia altura",
        "Politrauma",
        "Trauma de craneo",
        "Trauma de torax",
        "Trauma abdominal",
        "Fractura cerrada",
        "Fractura expuesta",
        "Herida cortante / sangrado activo",
        "Quemadura",
    ],
    "Metabolico y toxico": [
        "Hipoglucemia",
        "Hiperglucemia",
        "Cetoacidosis / descompensacion diabetica",
        "Intoxicacion medicamentosa",
        "Intoxicacion alcoholica",
        "Intoxicacion alimentaria / toxica",
        "Alteracion hidroelectrolitica",
    ],
    "Infeccioso / sepsis": [
        "Fiebre de origen desconocido",
        "Sepsis sospechada",
        "Shock septico",
        "Infeccion urinaria complicada",
        "Celulitis / infeccion de piel",
        "Infeccion respiratoria aguda",
    ],
    "Obstetrico": [
        "Trabajo de parto",
        "Metrorragia / sangrado obstetrico",
        "Dolor abdominal en embarazo",
        "Preeclampsia / eclampsia",
        "Control obstetrico urgente",
    ],
    "Pediatria": [
        "Fiebre alta en nino",
        "Convulsion febril",
        "Dificultad respiratoria pediatrica",
        "Trauma pediatrico",
        "Deshidratacion",
        "Reaccion alergica",
    ],
    "Psiquiatrico y conducta": [
        "Agitacion psicomotriz",
        "Intento de suicidio",
        "Crisis de angustia / panico",
        "Riesgo para si o terceros",
        "Desorientacion / alteracion conductual",
    ],
    "Traslados": [
        "Traslado asistencial",
        "Derivacion cronica",
        "Traslado programado",
        "Traslado interhospitalario",
        "Alta complejidad / UTI movil",
        "Derivacion a guardia",
        "Derivacion a internacion",
        "Retorno a domicilio",
    ],
    "General": [
        "Descompensacion general",
        "Dolor abdominal",
        "Hemorragia",
        "Reaccion alergica",
        "Deshidratacion",
        "Consulta clinica urgente",
    ],
}


def _firma_a_b64(canvas_result):
    if not canvas_result or canvas_result.image_data is None:
        return ""
    img = Image.fromarray(canvas_result.image_data.astype("uint8"), "RGBA")
    fondo = Image.new("RGB", img.size, (255, 255, 255))
    fondo.paste(img, mask=img.split()[-1])
    buf = io.BytesIO()
    fondo.save(buf, format="JPEG", optimize=True, quality=65)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _badge_html(texto, clase):
    return f"<span class='mc-chip {clase}'>{texto}</span>"


def _triage_meta(grado):
    mapping = {
        "Grado 1 - Rojo": {"prioridad": "Critica", "codigo": "Rojo", "clase": "mc-chip-danger"},
        "Grado 2 - Amarillo": {"prioridad": "Alta", "codigo": "Amarillo", "clase": "mc-chip-warning"},
        "Grado 3 - Verde": {"prioridad": "Media", "codigo": "Verde", "clase": "mc-chip-success"},
    }
    return mapping.get(grado, {"prioridad": "Media", "codigo": "Verde", "clase": ""})
