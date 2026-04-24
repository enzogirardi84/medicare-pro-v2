"""
Plugins package for Medicare Pro.

Este directorio contiene plugins que extienden la funcionalidad del sistema.

Para crear un plugin:
1. Crear archivo .py en este directorio
2. Heredar de MedicarePlugin
3. Implementar get_info() y initialize()
4. Opcionalmente implementar handlers de hooks

Ejemplo:
    from core.plugin_system import MedicarePlugin, PluginInfo
    
    class MyPlugin(MedicarePlugin):
        def get_info(self) -> PluginInfo:
            return PluginInfo(
                name="my_plugin",
                version="1.0.0",
                description="Mi plugin personalizado",
                author="Tu Nombre",
                hooks=[PluginHook.PATIENT_CREATED]
            )
        
        def initialize(self, config: dict) -> bool:
            # Inicialización
            return True
        
        def on_patient_created(self, context: dict):
            # Handler del hook
            print(f"Paciente creado: {context}")
"""
