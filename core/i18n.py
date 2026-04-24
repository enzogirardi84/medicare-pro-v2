"""
Sistema de Internacionalización (i18n) para Medicare Pro.

Soporta:
- Español (es) - default
- Portugués (pt)
- Inglés (en)
- Fechas y formatos localizados
- Números y monedas localizados
- Traducción dinámica
"""

from __future__ import annotations

import json
import locale
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st


# Locale por defecto
DEFAULT_LOCALE = "es"
SUPPORTED_LOCALES = ["es", "pt", "en"]

# Diccionario de traducciones
TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "es": {
        # General
        "app_name": "Medicare Pro",
        "app_subtitle": "Sistema de Gestión Clínica",
        "welcome": "Bienvenido",
        "loading": "Cargando...",
        "save": "Guardar",
        "cancel": "Cancelar",
        "delete": "Eliminar",
        "edit": "Editar",
        "search": "Buscar",
        "filter": "Filtrar",
        "close": "Cerrar",
        "back": "Volver",
        "next": "Siguiente",
        "previous": "Anterior",
        "submit": "Enviar",
        "confirm": "Confirmar",
        "yes": "Sí",
        "no": "No",
        
        # Navegación
        "nav_dashboard": "Dashboard",
        "nav_patients": "Pacientes",
        "nav_evolution": "Evolución",
        "nav_vitals": "Signos Vitales",
        "nav_prescriptions": "Recetas",
        "nav_studies": "Estudios",
        "nav_reports": "Reportes",
        "nav_admin": "Administración",
        "nav_settings": "Configuración",
        "nav_logout": "Cerrar Sesión",
        
        # Pacientes
        "patient_new": "Nuevo Paciente",
        "patient_edit": "Editar Paciente",
        "patient_search": "Buscar Paciente",
        "patient_name": "Nombre",
        "patient_lastname": "Apellido",
        "patient_dni": "DNI",
        "patient_birthdate": "Fecha de Nacimiento",
        "patient_age": "Edad",
        "patient_gender": "Sexo",
        "patient_phone": "Teléfono",
        "patient_email": "Email",
        "patient_address": "Dirección",
        "patient_insurance": "Obra Social",
        "patient_allergies": "Alergias",
        "patient_medications": "Medicamentos Actuales",
        "patient_history": "Historial Médico",
        
        # Signos Vitales
        "vital_blood_pressure": "Presión Arterial",
        "vital_heart_rate": "Frecuencia Cardíaca",
        "vital_respiratory_rate": "Frecuencia Respiratoria",
        "vital_temperature": "Temperatura",
        "vital_oxygen_saturation": "Saturación de O2",
        "vital_weight": "Peso",
        "vital_height": "Altura",
        "vital_bmi": "IMC",
        "vital_glucose": "Glucemia",
        
        # Evolución
        "evolution_new": "Nueva Evolución",
        "evolution_note": "Nota de Evolución",
        "evolution_diagnosis": "Diagnóstico",
        "evolution_treatment": "Tratamiento",
        "evolution_next_visit": "Próxima Visita",
        "evolution_date": "Fecha",
        "evolution_doctor": "Médico",
        
        # Mensajes
        "msg_saved": "Guardado exitosamente",
        "msg_error": "Ocurrió un error",
        "msg_confirm_delete": "¿Está seguro de eliminar?",
        "msg_no_data": "No hay datos disponibles",
        "msg_loading": "Cargando datos...",
        "msg_success": "Operación exitosa",
        "msg_warning": "Advertencia",
        "msg_info": "Información",
        
        # Errores
        "error_required": "Campo requerido",
        "error_invalid_email": "Email inválido",
        "error_invalid_dni": "DNI inválido",
        "error_patient_exists": "El paciente ya existe",
        "error_unauthorized": "No autorizado",
        "error_server": "Error del servidor",
        
        # Fechas
        "date_today": "Hoy",
        "date_yesterday": "Ayer",
        "date_days_ago": "hace {days} días",
        "date_weeks_ago": "hace {weeks} semanas",
        "date_months_ago": "hace {months} meses",
    },
    
    "pt": {
        # General
        "app_name": "Medicare Pro",
        "app_subtitle": "Sistema de Gestão Clínica",
        "welcome": "Bem-vindo",
        "loading": "Carregando...",
        "save": "Salvar",
        "cancel": "Cancelar",
        "delete": "Excluir",
        "edit": "Editar",
        "search": "Buscar",
        "filter": "Filtrar",
        "close": "Fechar",
        "back": "Voltar",
        "next": "Próximo",
        "previous": "Anterior",
        "submit": "Enviar",
        "confirm": "Confirmar",
        "yes": "Sim",
        "no": "Não",
        
        # Navegación
        "nav_dashboard": "Painel",
        "nav_patients": "Pacientes",
        "nav_evolution": "Evolução",
        "nav_vitals": "Sinais Vitais",
        "nav_prescriptions": "Receitas",
        "nav_studies": "Exames",
        "nav_reports": "Relatórios",
        "nav_admin": "Administração",
        "nav_settings": "Configurações",
        "nav_logout": "Sair",
        
        # Pacientes
        "patient_new": "Novo Paciente",
        "patient_edit": "Editar Paciente",
        "patient_search": "Buscar Paciente",
        "patient_name": "Nome",
        "patient_lastname": "Sobrenome",
        "patient_dni": "CPF",
        "patient_birthdate": "Data de Nascimento",
        "patient_age": "Idade",
        "patient_gender": "Sexo",
        "patient_phone": "Telefone",
        "patient_email": "Email",
        "patient_address": "Endereço",
        "patient_insurance": "Convênio",
        "patient_allergies": "Alergias",
        "patient_medications": "Medicamentos Atuais",
        "patient_history": "Histórico Médico",
        
        # Signos Vitales
        "vital_blood_pressure": "Pressão Arterial",
        "vital_heart_rate": "Frequência Cardíaca",
        "vital_respiratory_rate": "Frequência Respiratória",
        "vital_temperature": "Temperatura",
        "vital_oxygen_saturation": "Saturação de O2",
        "vital_weight": "Peso",
        "vital_height": "Altura",
        "vital_bmi": "IMC",
        "vital_glucose": "Glicemia",
        
        # Evolução
        "evolution_new": "Nova Evolução",
        "evolution_note": "Nota de Evolução",
        "evolution_diagnosis": "Diagnóstico",
        "evolution_treatment": "Tratamento",
        "evolution_next_visit": "Próxima Visita",
        "evolution_date": "Data",
        "evolution_doctor": "Médico",
        
        # Mensagens
        "msg_saved": "Salvo com sucesso",
        "msg_error": "Ocorreu um erro",
        "msg_confirm_delete": "Tem certeza que deseja excluir?",
        "msg_no_data": "Não há dados disponíveis",
        "msg_loading": "Carregando dados...",
        "msg_success": "Operação bem-sucedida",
        "msg_warning": "Aviso",
        "msg_info": "Informação",
        
        # Erros
        "error_required": "Campo obrigatório",
        "error_invalid_email": "Email inválido",
        "error_invalid_dni": "CPF inválido",
        "error_patient_exists": "O paciente já existe",
        "error_unauthorized": "Não autorizado",
        "error_server": "Erro do servidor",
        
        # Datas
        "date_today": "Hoje",
        "date_yesterday": "Ontem",
        "date_days_ago": "há {days} dias",
        "date_weeks_ago": "há {weeks} semanas",
        "date_months_ago": "há {months} meses",
    },
    
    "en": {
        # General
        "app_name": "Medicare Pro",
        "app_subtitle": "Clinical Management System",
        "welcome": "Welcome",
        "loading": "Loading...",
        "save": "Save",
        "cancel": "Cancel",
        "delete": "Delete",
        "edit": "Edit",
        "search": "Search",
        "filter": "Filter",
        "close": "Close",
        "back": "Back",
        "next": "Next",
        "previous": "Previous",
        "submit": "Submit",
        "confirm": "Confirm",
        "yes": "Yes",
        "no": "No",
        
        # Navigation
        "nav_dashboard": "Dashboard",
        "nav_patients": "Patients",
        "nav_evolution": "Evolution",
        "nav_vitals": "Vital Signs",
        "nav_prescriptions": "Prescriptions",
        "nav_studies": "Studies",
        "nav_reports": "Reports",
        "nav_admin": "Administration",
        "nav_settings": "Settings",
        "nav_logout": "Logout",
        
        # Patients
        "patient_new": "New Patient",
        "patient_edit": "Edit Patient",
        "patient_search": "Search Patient",
        "patient_name": "First Name",
        "patient_lastname": "Last Name",
        "patient_dni": "ID Number",
        "patient_birthdate": "Birth Date",
        "patient_age": "Age",
        "patient_gender": "Gender",
        "patient_phone": "Phone",
        "patient_email": "Email",
        "patient_address": "Address",
        "patient_insurance": "Insurance",
        "patient_allergies": "Allergies",
        "patient_medications": "Current Medications",
        "patient_history": "Medical History",
        
        # Vital Signs
        "vital_blood_pressure": "Blood Pressure",
        "vital_heart_rate": "Heart Rate",
        "vital_respiratory_rate": "Respiratory Rate",
        "vital_temperature": "Temperature",
        "vital_oxygen_saturation": "Oxygen Saturation",
        "vital_weight": "Weight",
        "vital_height": "Height",
        "vital_bmi": "BMI",
        "vital_glucose": "Glucose",
        
        # Evolution
        "evolution_new": "New Evolution",
        "evolution_note": "Evolution Note",
        "evolution_diagnosis": "Diagnosis",
        "evolution_treatment": "Treatment",
        "evolution_next_visit": "Next Visit",
        "evolution_date": "Date",
        "evolution_doctor": "Doctor",
        
        # Messages
        "msg_saved": "Saved successfully",
        "msg_error": "An error occurred",
        "msg_confirm_delete": "Are you sure you want to delete?",
        "msg_no_data": "No data available",
        "msg_loading": "Loading data...",
        "msg_success": "Operation successful",
        "msg_warning": "Warning",
        "msg_info": "Information",
        
        # Errors
        "error_required": "Required field",
        "error_invalid_email": "Invalid email",
        "error_invalid_dni": "Invalid ID",
        "error_patient_exists": "Patient already exists",
        "error_unauthorized": "Unauthorized",
        "error_server": "Server error",
        
        # Dates
        "date_today": "Today",
        "date_yesterday": "Yesterday",
        "date_days_ago": "{days} days ago",
        "date_weeks_ago": "{weeks} weeks ago",
        "date_months_ago": "{months} months ago",
    }
}


class I18nManager:
    """Manager de internacionalización."""
    
    def __init__(self, default_locale: str = DEFAULT_LOCALE):
        self.default_locale = default_locale
        self._current_locale = default_locale
        self._translations = TRANSLATIONS
    
    @property
    def current_locale(self) -> str:
        """Obtiene locale actual."""
        return self._current_locale
    
    def set_locale(self, locale: str) -> bool:
        """
        Cambia el locale actual.
        
        Args:
            locale: Código de locale (es, pt, en)
        
        Returns:
            True si el cambio fue exitoso
        """
        if locale not in SUPPORTED_LOCALES:
            log_event("i18n", f"Unsupported locale: {locale}")
            return False
        
        self._current_locale = locale
        
        # Guardar en session_state de Streamlit
        if 'i18n_locale' in st.session_state:
            st.session_state['i18n_locale'] = locale
        
        log_event("i18n", f"Locale changed to: {locale}")
        return True
    
    def get_locale_from_session(self) -> str:
        """Obtiene locale desde session_state."""
        if 'i18n_locale' in st.session_state:
            return st.session_state['i18n_locale']
        
        # Detectar del browser
        return self.detect_browser_locale()
    
    def detect_browser_locale(self) -> str:
        """Detecta locale preferido del browser."""
        # En producción, esto vendría del request HTTP
        # Por ahora, default
        return self.default_locale
    
    def _(self, key: str, **kwargs) -> str:
        """
        Traduce una clave al locale actual.
        
        Args:
            key: Clave de traducción
            **kwargs: Variables para interpolación
        
        Returns:
            Texto traducido
        """
        # Buscar en locale actual
        translation = self._translations.get(self._current_locale, {}).get(key)
        
        # Fallback a default
        if translation is None:
            translation = self._translations.get(self.default_locale, {}).get(key, key)
        
        # Interpolar variables
        if kwargs:
            try:
                translation = translation.format(**kwargs)
            except KeyError:
                pass  # Mantener {variable} si no se proporciona
        
        return translation
    
    def translate(self, key: str, locale: Optional[str] = None, **kwargs) -> str:
        """
        Traduce a un locale específico.
        
        Args:
            key: Clave de traducción
            locale: Locale específico (opcional)
            **kwargs: Variables para interpolación
        """
        target_locale = locale or self._current_locale
        
        translation = self._translations.get(target_locale, {}).get(key)
        if translation is None:
            translation = self._translations.get(self.default_locale, {}).get(key, key)
        
        if kwargs:
            try:
                translation = translation.format(**kwargs)
            except KeyError:
                pass
        
        return translation
    
    def get_available_locales(self) -> List[Dict[str, str]]:
        """Retorna lista de locales disponibles."""
        locale_info = {
            "es": {"name": "Español", "flag": "🇪🇸"},
            "pt": {"name": "Português", "flag": "🇧🇷"},
            "en": {"name": "English", "flag": "🇺🇸"},
        }
        
        return [
            {"code": code, **locale_info.get(code, {})}
            for code in SUPPORTED_LOCALES
        ]
    
    def format_date(self, date_obj, format: str = "short") -> str:
        """
        Formatea fecha según locale.
        
        Args:
            date_obj: Objeto fecha/datetime
            format: 'short', 'long', 'full'
        """
        if date_obj is None:
            return ""
        
        formats = {
            "es": {
                "short": "%d/%m/%Y",
                "long": "%d de %B de %Y",
                "full": "%A, %d de %B de %Y"
            },
            "pt": {
                "short": "%d/%m/%Y",
                "long": "%d de %B de %Y",
                "full": "%A, %d de %B de %Y"
            },
            "en": {
                "short": "%m/%d/%Y",
                "long": "%B %d, %Y",
                "full": "%A, %B %d, %Y"
            }
        }
        
        fmt = formats.get(self._current_locale, formats[self.default_locale]).get(format, "%d/%m/%Y")
        
        try:
            return date_obj.strftime(fmt)
        except:
            return str(date_obj)
    
    def format_number(self, number: float, decimals: int = 2) -> str:
        """Formatea número según locale."""
        if self._current_locale == "en":
            return f"{number:,.{decimals}f}"
        else:
            # Español/Portugués: coma como decimal, punto como miles
            return f"{number:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    
    def format_currency(self, amount: float, currency: str = "$") -> str:
        """Formatea moneda según locale."""
        if self._current_locale == "en":
            return f"{currency}{amount:,.2f}"
        else:
            return f"{currency} {self.format_number(amount, 2)}"
    
    def relative_date(self, days: int) -> str:
        """Retorna fecha relativa (hace X días)."""
        if days == 0:
            return self._("date_today")
        elif days == 1:
            return self._("date_yesterday")
        elif days < 7:
            return self._("date_days_ago", days=days)
        elif days < 30:
            weeks = days // 7
            return self._("date_weeks_ago", weeks=weeks)
        else:
            months = days // 30
            return self._("date_months_ago", months=months)


# Singleton global
_i18n_instance: Optional[I18nManager] = None


def get_i18n() -> I18nManager:
    """Obtiene instancia global de i18n."""
    global _i18n_instance
    if _i18n_instance is None:
        _i18n_instance = I18nManager()
    return _i18n_instance


def _(key: str, **kwargs) -> str:
    """Función helper para traducir."""
    return get_i18n()._(key, **kwargs)


def set_locale(locale: str) -> bool:
    """Cambia locale global."""
    return get_i18n().set_locale(locale)


def render_language_selector():
    """Renderiza selector de idioma en Streamlit."""
    i18n = get_i18n()
    
    locales = i18n.get_available_locales()
    
    current = i18n.current_locale
    options = {f"{loc['flag']} {loc['name']}": loc['code'] for loc in locales}
    
    selected_label = st.selectbox(
        "🌐 " + _("nav_settings"),
        options=list(options.keys()),
        index=list(options.values()).index(current) if current in options.values() else 0,
        key="language_selector"
    )
    
    selected_code = options[selected_label]
    
    if selected_code != current:
        if set_locale(selected_code):
            st.success(f"✅ Idioma cambiado a {selected_label}")
            st.rerun()


# Función para inicializar i18n en la app
def init_i18n():
    """Inicializa sistema de i18n."""
    i18n = get_i18n()
    
    # Intentar recuperar de session
    if 'i18n_locale' in st.session_state:
        i18n.set_locale(st.session_state['i18n_locale'])
    else:
        # Default
        st.session_state['i18n_locale'] = i18n.current_locale


if __name__ == "__main__":
    # Demo
    print("=== i18n Demo ===")
    
    i18n = get_i18n()
    
    for locale in SUPPORTED_LOCALES:
        i18n.set_locale(locale)
        print(f"\n{locale.upper()}:")
        print(f"  App: {i18n._('app_name')}")
        print(f"  Welcome: {i18n._('welcome')}")
        print(f"  Save: {i18n._('save')}")
        print(f"  Days ago: {i18n._('date_days_ago', days=5)}")
