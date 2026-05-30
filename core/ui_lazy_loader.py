"""Sistema de importacion dinamica de modulos con cache de compilacion.
Usa importlib + st.cache_resource para carga lazy aislada.
Una vez compilado, accesos subsecuentes < 5ms.
"""
from __future__ import annotations

import time
from importlib import import_module
from typing import Any, Callable, Optional

import streamlit as st

from core.app_logging import log_event


class StrictLazyLoader:
    """Cargador perezoso ultra-estricto con cache de compilacion.

    Los modulos se importan SOLO cuando se solicitan por primera vez.
    El objeto compilado se cachea via st.cache_resource (nivel app).
    """

    def __init__(self):
        self._registro: dict[str, tuple[str, str, list[str]]] = {}

    def registrar(
        self,
        nombre: str,
        module_path: str,
        function_name: str,
        dependencias_pesadas: list[str] | None = None,
    ) -> None:
        """Registra un modulo con sus dependencias.

        Args:
            nombre: Nombre visible (ej. "Dashboard").
            module_path: Ruta del modulo (ej. "views.dashboard").
            function_name: Funcion render (ej. "render_dashboard").
            dependencias_pesadas: Modulos heavy que arrastra (reportlab, folium, etc.).
        """
        self._registro[nombre] = (module_path, function_name, dependencias_pesadas or [])

    @st.cache_resource(ttl=3600, show_spinner=False)
    def _cargar_modulo_cache(
        module_path: str, function_name: str, _deps_hash: str
    ) -> Callable:
        """Carga el modulo con cache a nivel aplicacion.

        El hash de dependencias asegura invalidacion si cambian.
        Una vez cargado, el objeto compilado vive en cache 1 hora.
        """
        from importlib import import_module

        mod = import_module(module_path)
        fn = getattr(mod, function_name)
        log_event(
            "lazy_loader",
            f"cargado:{module_path}.{function_name}",
        )
        return fn

    def obtener(self, nombre: str) -> Optional[Callable]:
        """Obtiene la funcion render del modulo con lazy loading estricto.

        Returns:
            Callable listo para invocar con **kwargs.
        """
        if nombre not in self._registro:
            log_event("lazy_loader", f"no_registrado:{nombre}")
            return None

        module_path, function_name, deps = self._registro[nombre]

        # Hash de dependencias para invalidacion de cache
        import hashlib
        deps_hash = hashlib.md5("|".join(deps).encode()).hexdigest()[:12]

        try:
            t0 = time.perf_counter()
            fn = self._cargar_modulo_cache(module_path, function_name, deps_hash)
            dt = (time.perf_counter() - t0) * 1000
            if dt > 100:
                log_event("lazy_loader", f"lento:{nombre}:{dt:.0f}ms")
            return fn
        except Exception as exc:
            log_event("lazy_loader", f"error:{module_path}:{type(exc).__name__}:{exc}")
            return None

    def render(self, nombre: str, **kwargs: Any) -> None:
        """Renderiza un modulo registrado con lazy loading.

        Args:
            nombre: Nombre del modulo.
            **kwargs: Argumentos para la funcion render.
        """
        import streamlit as st
        t0 = time.perf_counter()
        fn = self.obtener(nombre)
        if fn is None:
            st.error(f"Modulo '{nombre}' no disponible")
            return

        try:
            fn(**kwargs)
        except Exception as exc:
            st.error(f"Error en {nombre}")
            log_event("lazy_loader", f"render_error:{nombre}:{type(exc).__name__}")

        dt = (time.perf_counter() - t0) * 1000
        log_event("ui_perf", f"modulo:{nombre}:{dt:.0f}ms")


# Instancia global del loader
_loader: StrictLazyLoader | None = None


def get_loader() -> StrictLazyLoader:
    global _loader
    if _loader is None:
        _loader = StrictLazyLoader()
        _registrar_modulos_base(_loader)
    return _loader


def _registrar_modulos_base(loader: StrictLazyLoader) -> None:
    """Registra los 50 modulos de vista con sus dependencias pesadas."""
    modulos = {
        "Dashboard": ("views.dashboard", "render_dashboard", ["pandas", "altair"]),
        "Mi Equipo": ("views.mi_equipo", "render_mi_equipo", []),
        "Admision": ("views.admision", "render_admision", []),
        "Evolucion": ("views.evolucion", "render_evolucion", []),
        "Clinica": ("views.clinica", "render_clinica", ["pandas"]),
        "Pediatria": ("views.pediatria", "render_pediatria", []),
        "Escalas Clinicas": ("views.escalas_clinicas", "render_escalas_clinicas", []),
        "Estudios": ("views.estudios", "render_estudios", []),
        "Diagnosticos": ("views.diagnosticos", "render_diagnosticos", []),
        "Enfermeria": ("views.enfermeria", "render_enfermeria", []),
        "Visitas y Agenda": ("views.visitas", "render_visitas", []),
        "Turnos Online": ("views.turnos_online", "render_turnos_online", []),
        "Recetas": ("views.recetas", "render_recetas", ["pandas"]),
        "Calculadora Dosis": ("views.calculadora_dosis", "render_calculadora_dosis", []),
        "Dispensario": ("views.dispensario_aps", "render_dispensario", []),
        "Emergencias": ("views.emergencias", "render_emergencias", []),
        "RRHH y Fichajes": ("views.rrhh", "render_rrhh", []),
        "Caja": ("views.caja", "render_caja", []),
        "Inventario": ("views.inventario", "render_inventario", ["pandas"]),
        "Materiales": ("views.materiales", "render_materiales", []),
        "Balance": ("views.balance", "render_balance", []),
        "Auditoria": ("views.auditoria", "render_auditoria", ["pandas"]),
        "Auditoria Legal": ("views.auditoria_legal", "render_auditoria_legal", []),
        "Documentos Legales": ("views.legal_docs", "render_legal_docs", []),
        "Visor PDF": ("views.pdf_view", "render_pdf_view", ["reportlab"]),
        "Factura Electronica": ("views.factura_electronica", "render_factura_electronica", []),
        "Telemedicina": ("views.telemedicina", "render_telemedicina", []),
        "Asistente Clinico": ("views.asistente_clinico", "render_asistente_clinico", []),
        "Chatbot IA": ("views.chatbot_ia", "render_chatbot_ia", []),
        "Historial": ("views.historial", "render_historial", ["pandas"]),
        "Portal Paciente": ("views.portal_paciente", "render_portal_paciente", []),
        "Vacunacion": ("views.vacunacion", "render_vacunacion", []),
        "Alertas App": ("views.alertas_paciente_app", "render_alertas_paciente_app", []),
        "Panel IA": ("views.ai_features_panel", "render_ai_features_panel", []),
        "Admin Dashboard": ("views.admin_dashboard", "render_admin_dashboard", ["pandas"]),
        "Admin Usuarios": ("views.admin_usuarios", "render_admin_usuarios", []),
    }
    for nombre, (ruta, fn, deps) in modulos.items():
        loader.registrar(nombre, ruta, fn, deps)
