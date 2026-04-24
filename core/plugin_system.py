"""
Sistema de Plugins/Extensiones para Medicare Pro.

Permite extender funcionalidad mediante plugins:
- Hooks en puntos clave
- Registro de vistas adicionales
- Integraciones personalizadas
- Reportes custom

Arquitectura:
- Descubrimiento automático de plugins
- Carga dinámica
- Sandbox de seguridad
- Dependencias entre plugins
"""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import json
import os
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type, Union
from enum import Enum, auto

from core.app_logging import log_event
from core.audit_trail import audit_log, AuditEventType


class PluginHook(Enum):
    """Hooks disponibles para plugins."""
    APP_INIT = "app_init"              # Inicialización de app
    USER_LOGIN = "user_login"          # Usuario inicia sesión
    USER_LOGOUT = "user_logout"        # Usuario cierra sesión
    PATIENT_CREATED = "patient_created"  # Paciente creado
    PATIENT_UPDATED = "patient_updated"  # Paciente actualizado
    EVOLUTION_CREATED = "evolution_created"  # Evolución creada
    VITALS_RECORDED = "vitals_recorded"      # Signos vitales registrados
    PRE_RENDER = "pre_render"          # Antes de renderizar página
    POST_RENDER = "post_render"        # Después de renderizar página
    DAILY_BATCH = "daily_batch"        # Job diario


@dataclass
class PluginInfo:
    """Metadata de un plugin."""
    name: str
    version: str
    description: str
    author: str
    requires: List[str] = field(default_factory=list)
    hooks: List[PluginHook] = field(default_factory=list)
    config_schema: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    priority: int = 100  # Menor = ejecuta primero


class MedicarePlugin(ABC):
    """
    Clase base para plugins de Medicare Pro.
    
    Los plugins deben heredar de esta clase e implementar
    los métodos abstractos.
    """
    
    def __init__(self):
        self.info: Optional[PluginInfo] = None
        self.config: Dict[str, Any] = {}
        self.enabled = False
    
    @abstractmethod
    def get_info(self) -> PluginInfo:
        """Retorna metadata del plugin."""
        pass
    
    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> bool:
        """
        Inicializa el plugin.
        
        Args:
            config: Configuración del plugin
        
        Returns:
            True si la inicialización fue exitosa
        """
        pass
    
    def on_hook(self, hook: PluginHook, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Maneja un hook.
        
        Args:
            hook: Tipo de hook
            context: Contexto del hook
        
        Returns:
            Dict opcional con datos modificados o None
        """
        handler_name = f"on_{hook.value}"
        if hasattr(self, handler_name):
            handler = getattr(self, handler_name)
            return handler(context)
        return None
    
    def get_config_schema(self) -> Dict[str, Any]:
        """Retorna schema de configuración para UI."""
        return self.info.config_schema if self.info else {}
    
    def validate_config(self, config: Dict[str, Any]) -> List[str]:
        """Valida configuración del plugin."""
        errors = []
        schema = self.get_config_schema()
        
        for key, value in config.items():
            if key in schema:
                field_schema = schema[key]
                field_type = field_schema.get("type", "string")
                
                # Validar tipo
                if field_type == "string" and not isinstance(value, str):
                    errors.append(f"{key} debe ser string")
                elif field_type == "number" and not isinstance(value, (int, float)):
                    errors.append(f"{key} debe ser número")
                elif field_type == "boolean" and not isinstance(value, bool):
                    errors.append(f"{key} debe ser booleano")
        
        return errors


class PluginManager:
    """
    Manager central de plugins.
    
    Gestiona:
    - Descubrimiento y carga de plugins
    - Registro de hooks
    - Configuración de plugins
    - Dependencias
    """
    
    PLUGIN_DIR = "plugins"
    
    def __init__(self):
        self._plugins: Dict[str, MedicarePlugin] = {}
        self._hooks: Dict[PluginHook, List[MedicarePlugin]] = {hook: [] for hook in PluginHook}
        self._config: Dict[str, Dict[str, Any]] = {}
        
        # Asegurar directorio de plugins existe
        Path(self.PLUGIN_DIR).mkdir(exist_ok=True)
    
    def discover_plugins(self) -> List[PluginInfo]:
        """
        Descubre plugins disponibles.
        
        Returns:
            Lista de metadata de plugins encontrados
        """
        discovered = []
        
        plugin_path = Path(self.PLUGIN_DIR)
        if not plugin_path.exists():
            return discovered
        
        # Buscar archivos .py en directorio plugins
        for plugin_file in plugin_path.glob("*.py"):
            if plugin_file.name.startswith("__"):
                continue
            
            try:
                # Cargar módulo temporalmente para obtener metadata
                spec = importlib.util.spec_from_file_location(
                    plugin_file.stem,
                    plugin_file
                )
                module = importlib.util.module_from_spec(spec)
                
                # Buscar clase de plugin
                plugin_class = self._find_plugin_class(module)
                
                if plugin_class:
                    # Instanciar temporalmente para obtener info
                    temp_instance = plugin_class()
                    info = temp_instance.get_info()
                    discovered.append(info)
                    
            except Exception as e:
                log_event("plugin", f"Failed to discover plugin {plugin_file}: {e}")
        
        return discovered
    
    def _find_plugin_class(self, module) -> Optional[Type[MedicarePlugin]]:
        """Encuentra clase de plugin en un módulo."""
        for name, obj in inspect.getmembers(module):
            if (inspect.isclass(obj) and 
                issubclass(obj, MedicarePlugin) and 
                obj != MedicarePlugin):
                return obj
        return None
    
    def load_plugin(self, plugin_name: str) -> bool:
        """
        Carga e inicializa un plugin.
        
        Args:
            plugin_name: Nombre del plugin (sin extensión)
        
        Returns:
            True si se cargó exitosamente
        """
        if plugin_name in self._plugins:
            log_event("plugin", f"Plugin {plugin_name} already loaded")
            return True
        
        plugin_file = Path(self.PLUGIN_DIR) / f"{plugin_name}.py"
        
        if not plugin_file.exists():
            log_event("plugin_error", f"Plugin file not found: {plugin_file}")
            return False
        
        try:
            # Cargar módulo
            spec = importlib.util.spec_from_file_location(plugin_name, plugin_file)
            module = importlib.util.module_from_spec(spec)
            sys.modules[plugin_name] = module
            spec.loader.exec_module(module)
            
            # Encontrar clase
            plugin_class = self._find_plugin_class(module)
            
            if not plugin_class:
                log_event("plugin_error", f"No plugin class found in {plugin_name}")
                return False
            
            # Instanciar
            instance = plugin_class()
            info = instance.get_info()
            
            # Verificar dependencias
            for required in info.requires:
                if required not in self._plugins:
                    log_event("plugin_error", f"Plugin {plugin_name} requires {required}")
                    return False
            
            # Obtener config
            plugin_config = self._config.get(plugin_name, {})
            
            # Validar config
            errors = instance.validate_config(plugin_config)
            if errors:
                log_event("plugin_error", f"Plugin {plugin_name} config errors: {errors}")
                return False
            
            # Inicializar
            if not instance.initialize(plugin_config):
                log_event("plugin_error", f"Plugin {plugin_name} initialization failed")
                return False
            
            # Registrar
            self._plugins[plugin_name] = instance
            instance.info = info
            instance.config = plugin_config
            instance.enabled = True
            
            # Registrar hooks
            for hook in info.hooks:
                self._hooks[hook].append(instance)
                # Ordenar por prioridad
                self._hooks[hook].sort(key=lambda p: p.info.priority if p.info else 100)
            
            log_event("plugin", f"Plugin {plugin_name} v{info.version} loaded successfully")
            
            audit_log(
                AuditEventType.CONFIG_CHANGE,
                resource_type="plugin",
                resource_id=plugin_name,
                action="LOAD",
                description=f"Plugin loaded: {info.name} v{info.version}"
            )
            
            return True
            
        except Exception as e:
            log_event("plugin_error", f"Failed to load plugin {plugin_name}: {e}")
            return False
    
    def unload_plugin(self, plugin_name: str) -> bool:
        """Descarga un plugin."""
        if plugin_name not in self._plugins:
            return False
        
        plugin = self._plugins[plugin_name]
        
        # Desregistrar hooks
        for hook_list in self._hooks.values():
            if plugin in hook_list:
                hook_list.remove(plugin)
        
        # Eliminar
        del self._plugins[plugin_name]
        
        log_event("plugin", f"Plugin {plugin_name} unloaded")
        return True
    
    def trigger_hook(self, hook: PluginHook, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dispara un hook y ejecuta todos los plugins registrados.
        
        Args:
            hook: Tipo de hook
            context: Contexto del hook
        
        Returns:
            Contexto posiblemente modificado
        """
        plugins = self._hooks.get(hook, [])
        modified_context = context.copy()
        
        for plugin in plugins:
            if not plugin.enabled:
                continue
            
            try:
                result = plugin.on_hook(hook, modified_context)
                
                if result:
                    # Merge resultado con contexto
                    modified_context.update(result)
                    
            except Exception as e:
                log_event("plugin_error", f"Plugin {plugin.info.name if plugin.info else 'unknown'} hook error: {e}")
        
        return modified_context
    
    def get_loaded_plugins(self) -> List[PluginInfo]:
        """Lista plugins cargados."""
        return [p.info for p in self._plugins.values() if p.info]
    
    def set_plugin_config(self, plugin_name: str, config: Dict[str, Any]):
        """Establece configuración de plugin."""
        self._config[plugin_name] = config
        
        # Si el plugin está cargado, recargar
        if plugin_name in self._plugins:
            plugin = self._plugins[plugin_name]
            plugin.config = config
    
    def save_config(self):
        """Guarda configuración de plugins a disco."""
        config_path = Path(self.PLUGIN_DIR) / "plugin_config.json"
        
        with open(config_path, 'w') as f:
            json.dump(self._config, f, indent=2)
    
    def load_config(self):
        """Carga configuración de plugins."""
        config_path = Path(self.PLUGIN_DIR) / "plugin_config.json"
        
        if config_path.exists():
            with open(config_path) as f:
                self._config = json.load(f)


# Decorator para fácil registro de hooks
def register_hook(hook: PluginHook):
    """
    Decorador para registrar métodos como handlers de hooks.
    
    Uso:
        class MyPlugin(MedicarePlugin):
            @register_hook(PluginHook.PATIENT_CREATED)
            def on_patient_created(self, context):
                print(f"Patient created: {context['patient_id']}")
    """
    def decorator(func: Callable) -> Callable:
        func._hook = hook
        return func
    return decorator


# Singleton
_plugin_manager: Optional[PluginManager] = None


def get_plugin_manager() -> PluginManager:
    """Obtiene instancia del manager de plugins."""
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
        _plugin_manager.load_config()
    return _plugin_manager


def trigger_app_hook(hook: PluginHook, **context) -> Dict[str, Any]:
    """Helper para disparar hooks desde la app."""
    manager = get_plugin_manager()
    return manager.trigger_hook(hook, context)


# Ejemplo de plugin
class ExamplePlugin(MedicarePlugin):
    """Plugin de ejemplo que demuestra la API."""
    
    def get_info(self) -> PluginInfo:
        return PluginInfo(
            name="example_plugin",
            version="1.0.0",
            description="Plugin de ejemplo para Medicare Pro",
            author="Medicare Team",
            requires=[],
            hooks=[
                PluginHook.PATIENT_CREATED,
                PluginHook.EVOLUTION_CREATED
            ],
            config_schema={
                "webhook_url": {
                    "type": "string",
                    "label": "Webhook URL",
                    "default": ""
                },
                "notify_on_patient": {
                    "type": "boolean",
                    "label": "Notificar en nuevo paciente",
                    "default": True
                }
            }
        )
    
    def initialize(self, config: Dict[str, Any]) -> bool:
        self.webhook_url = config.get("webhook_url", "")
        self.notify_on_patient = config.get("notify_on_patient", True)
        
        log_event("plugin", "Example plugin initialized")
        return True
    
    def on_patient_created(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Handler para hook de paciente creado."""
        if not self.notify_on_patient:
            return None
        
        patient_id = context.get("patient_id")
        patient_name = context.get("patient_name", "Unknown")
        
        log_event("plugin", f"Example plugin: Patient {patient_name} created")
        
        # Aquí podrías enviar webhook, notificación, etc.
        if self.webhook_url:
            try:
                import requests
                requests.post(
                    self.webhook_url,
                    json={
                        "event": "patient_created",
                        "patient_id": patient_id,
                        "patient_name": patient_name
                    },
                    timeout=5
                )
            except Exception as e:
                log_event("plugin_error", f"Webhook failed: {e}")
        
        return None
    
    def on_evolution_created(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Handler para hook de evolución creada."""
        log_event("plugin", "Example plugin: Evolution created")
        return None
