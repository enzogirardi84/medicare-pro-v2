from views._recetas_utils import (
    detalle_horario_infusion,
    normalizar_plan_hidratacion,
    ritmo_infusion_ml_h,
    resumen_plan_hidratacion,
    texto_indicacion_visible,
    velocidad_ml_h_desde_texto,
)
from views._recetas_indicaciones import construir_texto_indicacion
from views._recetas_mar import construir_matriz_registro_24h, tabla_guardia_operativa
from views._recetas_turno import _frecuencia_visible_con_ritmo


def test_normalizar_plan_hidratacion_expone_ml_h_legacy():
    plan = [{"Hora sugerida": "08:00", "Velocidad (ml/h)": 21.0, "Solucion": "Fisiologico"}]

    filas = normalizar_plan_hidratacion(plan)

    assert filas[0]["ML/h"] == "21"
    assert resumen_plan_hidratacion(plan) == "08:00: 21 ml/h"


def test_normalizar_plan_hidratacion_crea_fila_desde_infusion_simple():
    registro = {
        "tipo_indicacion": "Infusion / hidratacion",
        "med": "Fisiologico 0.9% 500 ml",
        "hora_inicio": "10:00",
        "solucion": "Fisiologico 0.9%",
        "volumen_ml": 500,
        "velocidad_ml_h": 42,
    }

    filas = normalizar_plan_hidratacion(registro=registro)

    assert filas == [
        {
            "Medicacion": "Fisiologico 0.9% 500 ml",
            "Hora sugerida": "10:00",
            "Solucion": "Fisiologico 0.9%",
            "Volumen (ml)": 500,
            "ML/h": "42",
            "Detalle": "",
        }
    ]
    assert detalle_horario_infusion(registro, "10:00") == "42 ml/h"


def test_texto_indicacion_de_infusion_muestra_ml_h():
    texto = construir_texto_indicacion(
        tipo_indicacion="Infusion / hidratacion",
        via="Via Endovenosa",
        frecuencia="Infusion continua",
        solucion="Dextrosa 5%",
        volumen_ml=500,
        velocidad_ml_h=63.0,
    )

    assert texto.startswith("Velocidad: 63 ml/h")
    assert "Dextrosa 5% 500 ml" in texto


def test_texto_indicacion_visible_repara_infusion_sql_sin_unidad():
    registro = {
        "tipo_indicacion": "Infusion / hidratacion",
        "med": "Dextrosa 5% 500 ml | Via: Via Endovenosa | Velocidad: 63",
        "velocidad_ml_h": 63,
    }

    texto = texto_indicacion_visible(registro)
    assert texto.startswith("Velocidad: 63 ml/h")
    assert "Velocidad: 63 |" not in texto


def test_ritmo_infusion_se_muestra_al_inicio_de_frecuencia():
    registro = {
        "tipo_indicacion": "Infusion / hidratacion",
        "hora_inicio": "08:00",
        "velocidad_ml_h": 2,
    }

    ritmo = ritmo_infusion_ml_h(registro, "08:00")

    assert ritmo == "2 ml/h"
    assert _frecuencia_visible_con_ritmo("Infusion continua", ritmo) == "Infusion continua a 2 ml/h"


def test_velocidad_se_extrae_desde_texto_crudo_de_supabase():
    registro = {
        "tipo_indicacion": "Infusion / hidratacion",
        "med": "Fisiologico 0.9% 500 ml | Via: Via Endovenosa | Velocidad: 2",
        "frecuencia": "Infusion continua",
    }

    assert velocidad_ml_h_desde_texto(registro["med"]) == "2"
    assert ritmo_infusion_ml_h(registro) == "2 ml/h"
    assert texto_indicacion_visible(registro).startswith("Velocidad: 2 ml/h")


def test_matriz_cortina_expone_columna_ml_h():
    import pandas as pd

    plan_df = pd.DataFrame([
        {
            "Hora programada": "08:00",
            "Medicamento": "Dextrosa 5% 500 ml",
            "Via": "Via Endovenosa",
            "Frecuencia": "Infusion continua",
            "Detalle / velocidad": "63 ml/h",
            "ML/h": "63",
            "Estado": "Pendiente",
        }
    ])

    rows, _, _ = construir_matriz_registro_24h(plan_df)

    assert rows[0]["ML/h"] == "63"


def test_tabla_guardia_no_trunca_frecuencia_con_ml_h():
    import pandas as pd

    plan_df = pd.DataFrame([
        {
            "Hora programada": "08:00",
            "Medicamento": "Fisiologico 0.9% 500 ml",
            "Via": "Via Endovenosa",
            "Frecuencia": "Infusion continua a 2 ml/h",
            "Detalle / velocidad": "2 ml/h",
            "ML/h": "2",
            "Estado": "Pendiente",
            "Hora realizada": "",
            "Observacion": "",
            "Registrado por": "",
        }
    ])

    tabla = tabla_guardia_operativa(plan_df)

    assert "Infusion continua a 2 ml/h" in tabla.iloc[0]["Indicacion"]
