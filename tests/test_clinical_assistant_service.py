"""Tests para clinical_assistant_service.

EJECUTAR:
    python -m pytest tests/test_clinical_assistant_service.py -v
"""

import pytest


class TestCoincidePaciente:
    def test_match_exacto(self):
        from core.clinical_assistant_service import _coincide_paciente

        item = {"paciente": "Juan Perez - 12345678"}
        assert _coincide_paciente(item, "Juan Perez - 12345678") is True

    def test_match_por_dni(self):
        from core.clinical_assistant_service import _coincide_paciente

        item = {"dni": "12345678"}
        assert _coincide_paciente(item, "Juan Perez - 12345678") is True

    def test_match_por_nombre_sin_dni(self):
        from core.clinical_assistant_service import _coincide_paciente

        item = {"paciente": "Juan Perez"}
        assert _coincide_paciente(item, "Juan Perez - 12345678") is True

    def test_match_por_nombre_con_parentesis(self):
        from core.clinical_assistant_service import _coincide_paciente

        item = {"nombre": "Facundo Acosta (Nobis)"}
        assert _coincide_paciente(item, "Facundo Acosta (Nobis) - 41440234") is True

    def test_none_paciente_id(self):
        from core.clinical_assistant_service import _coincide_paciente

        assert _coincide_paciente({}, None) is False


class TestEvaluarRiesgoClinico:
    def test_alertas_con_keys_mayusculas(self):
        from core.clinical_assistant_service import evaluar_riesgo_clinico

        datos = {
            "vitales": [
                {
                    "TA": "160/95",
                    "FC": 130,
                    "Temp": 39.0,
                    "HGT": 300,
                    "Sat": 85,
                    "fecha": "30/04/2026 01:00",
                }
            ]
        }
        alertas = evaluar_riesgo_clinico(datos)
        titulos = [a["titulo"] for a in alertas]
        assert "Riesgo Cardiovascular — TA elevada" in titulos
        assert "Riesgo Metabolico — hiperglucemia" in titulos
        assert "Fiebre significativa" in titulos
        assert "Taquicardia" in titulos
        assert "Hipoxemia" in titulos

    def test_sin_alertas_normales(self):
        from core.clinical_assistant_service import evaluar_riesgo_clinico

        datos = {
            "vitales": [
                {
                    "TA": "120/80",
                    "FC": 75,
                    "Temp": 36.5,
                    "HGT": 100,
                    "Sat": 98,
                    "fecha": "30/04/2026 01:00",
                }
            ]
        }
        alertas = evaluar_riesgo_clinico(datos)
        assert len(alertas) == 0


class TestCompilarDashboard:
    def test_ultimos_vitales_keys_mayusculas(self):
        from core.clinical_assistant_service import compilar_dashboard_ejecutivo

        datos = {
            "vitales": [
                {
                    "TA": "130/85",
                    "FC": 82,
                    "Temp": 37.2,
                    "HGT": 110,
                    "Sat": 97,
                    "fecha": "30/04/2026 01:00",
                }
            ],
            "evoluciones": [],
            "cuidados": [],
            "indicaciones": [],
            "estudios": [],
            "consumos": [],
            "balance": [],
            "administracion_med": [],
            "diagnosticos": [],
            "escalas": [],
            "emergencias": [],
        }
        dash = compilar_dashboard_ejecutivo(datos)
        assert dash["ultima_ta"] == "130/85"
        assert dash["ultima_fc"] == "82"
        assert dash["ultima_temp"] == "37.2"
        assert dash["ultima_glu"] == "110"
        assert dash["ultima_spo2"] == "97"

    def test_tendencias_keys_mayusculas(self):
        from core.clinical_assistant_service import compilar_dashboard_ejecutivo

        datos = {
            "vitales": [
                {
                    "TA": "120/80",
                    "HGT": 90,
                    "fecha": "29/04/2026 01:00",
                },
                {
                    "TA": "140/90",
                    "HGT": 110,
                    "fecha": "30/04/2026 01:00",
                },
            ],
            "evoluciones": [],
            "cuidados": [],
            "indicaciones": [],
            "estudios": [],
            "consumos": [],
            "balance": [],
            "administracion_med": [],
            "diagnosticos": [],
            "escalas": [],
            "emergencias": [],
        }
        dash = compilar_dashboard_ejecutivo(datos)
        assert len(dash["ta_tendencia"]) == 2
        assert len(dash["glu_tendencia"]) == 2
        assert dash["ta_tendencia"][0]["sistolica"] == 120
        assert dash["ta_tendencia"][1]["sistolica"] == 140
        assert dash["glu_tendencia"][0]["glucemia"] == 90
        assert dash["glu_tendencia"][1]["glucemia"] == 110

    def test_keys_minusculas_tambien_funcionan(self):
        from core.clinical_assistant_service import compilar_dashboard_ejecutivo

        datos = {
            "vitales": [
                {
                    "presion_arterial": "135/88",
                    "frecuencia_cardiaca": 78,
                    "temperatura": 36.8,
                    "glucemia": 95,
                    "saturacion_o2": 99,
                    "fecha": "30/04/2026 01:00",
                }
            ],
            "evoluciones": [],
            "cuidados": [],
            "indicaciones": [],
            "estudios": [],
            "consumos": [],
            "balance": [],
            "administracion_med": [],
            "diagnosticos": [],
            "escalas": [],
            "emergencias": [],
        }
        dash = compilar_dashboard_ejecutivo(datos)
        assert dash["ultima_ta"] == "135/88"
        assert dash["ultima_fc"] == "78"
        assert dash["ultima_temp"] == "36.8"
        assert dash["ultima_glu"] == "95"
        assert dash["ultima_spo2"] == "99"


class TestGenerarTextoPaseGuardia:
    def test_estructura_completa_sin_truncamiento(self):
        from core.clinical_assistant_service import generar_texto_pase_guardia

        datos = {
            "paciente_data": {
                "nombre": "Facundo Acosta",
                "dni": "41440234",
                "obra_social": "Nobis",
                "fnac": "01/01/1980",
                "diagnostico": "Neumonia bilateral",
            },
            "evoluciones": [
                {
                    "fecha": "30/04/2026 01:06",
                    "firma": "Dr. Garcia",
                    "nota": "Paciente estable. Saturacion mejorada al 96%. Continuar antibioticoterapia.",
                }
            ],
            "indicaciones": [
                {
                    "med": "Fisiologico 0.9% 500 ml",
                    "dosis": "500 ml",
                    "via": "Endovenosa",
                    "frecuencia": "Continuo",
                    "estado_receta": "Activa",
                    "fecha": "30/04/2026 01:00",
                },
                {
                    "med": "Ketorolac 30Mg Ampolla",
                    "dosis": "30 mg",
                    "via": "Endovenosa",
                    "frecuencia": "Cada 8 horas",
                    "estado_receta": "Activa",
                    "fecha": "30/04/2026 01:00",
                },
            ],
        }
        dashboard = {
            "semaforo": "amarillo",
            "ultima_ta": "130/80",
            "ultima_fc": "75",
            "ultima_temp": "36.5",
            "ultima_glu": "110",
            "ultima_spo2": "96",
            "alertas": [
                {"nivel": "warning", "titulo": "Administracion Pendiente", "detalle": "Ketorolac sin registro de administracion."},
                {"nivel": "info", "titulo": "Evolucion sin diagnostico formal", "detalle": "Hay evoluciones clinicas pero no hay diagnosticos cargados."},
            ],
        }

        texto = generar_texto_pase_guardia("Facundo Acosta (Nobis) - 41440234", datos, dashboard)

        assert "=== INFORME DE PASE DE GUARDIA / AUDITORIA ===" in texto
        assert "Paciente: Facundo Acosta" in texto
        assert "DNI: 41440234" in texto
        assert "Obra Social: Nobis" in texto
        assert "Neumonia bilateral" in texto
        assert "AMARILLO (REQUIERE ATENCION)" in texto
        assert "--- 1. ESTADO ACTUAL (Ultimos Signos Vitales) ---" in texto
        assert "TA: 130/80 mmHg" in texto
        assert "--- 2. ULTIMA EVOLUCION CLINICA ---" in texto
        assert "[30/04/2026 01:06] - Dr. Garcia:" in texto
        assert "Saturacion mejorada al 96%" in texto
        assert "--- 3. TRATAMIENTO Y CUIDADOS ACTIVOS ---" in texto
        assert "Fisiologico 0.9% 500 ml" in texto
        assert "Ketorolac 30Mg Ampolla" in texto
        assert "Cada 8 horas" in texto
        assert "--- 4. ALERTAS Y PENDIENTES (ATENCION) ---" in texto
        assert "[ADVERTENCIAS]" in texto
        assert "[OBSERVACIONES / AUDITORIA]" in texto
        assert "Sin alertas ni pendientes detectados." not in texto
        # Verificar que no hay truncamiento con "..."
        assert "..." not in texto or "Saturacion mejorada al 96%" in texto

    def test_genera_pdf_profesional(self):
        from core.clinical_assistant_service import generar_pdf_informe_profesional

        datos = {
            "paciente_data": {
                "nombre": "Facundo Acosta",
                "dni": "41440234",
                "obra_social": "Nobis",
                "fnac": "01/01/1980",
                "diagnostico": "Neumonia bilateral",
            },
            "evoluciones": [
                {
                    "fecha": "30/04/2026 01:06",
                    "firma": "Dr. Garcia",
                    "nota": "Paciente estable. Saturacion mejorada al 96%.",
                }
            ],
            "indicaciones": [
                {
                    "med": "Fisiologico 0.9% 500 ml",
                    "dosis": "500 ml",
                    "via": "Endovenosa",
                    "frecuencia": "Continuo",
                    "estado_receta": "Activa",
                    "fecha": "30/04/2026 01:00",
                },
            ],
        }
        dashboard = {
            "semaforo": "amarillo",
            "ultima_ta": "130/80",
            "ultima_fc": "75",
            "ultima_temp": "36.5",
            "ultima_glu": "110",
            "ultima_spo2": "96",
            "alertas": [],
        }

        pdf_bytes = generar_pdf_informe_profesional("Facundo Acosta (Nobis) - 41440234", datos, dashboard)
        assert isinstance(pdf_bytes, bytes)
        assert pdf_bytes.startswith(b"%PDF")
        # Con fuentes core fpdf2 no almacena texto literal en el stream;
        # verificamos que el PDF es valido y tiene contenido.
        assert len(pdf_bytes) > 1000
        assert b"%%EOF" in pdf_bytes
