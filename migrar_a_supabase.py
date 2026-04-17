#!/usr/bin/env python3
"""
MIGRACIÓN DE DATOS LOCALES A SUPABASE
Pasa todos los datos de local_data.json a la nube
"""

import json
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Tuple

class MigradorSupabase:
    """Migra datos locales a Supabase de forma segura."""
    
    def __init__(self):
        self.supabase = None
        self.errores = []
        self.migrados = 0
        
    def conectar(self) -> bool:
        """Conecta a Supabase."""
        try:
            import toml
            from supabase import create_client
            
            secrets = toml.load('.streamlit/secrets.toml')
            self.supabase = create_client(
                secrets['SUPABASE_URL'],
                secrets['SUPABASE_KEY']
            )
            print("✅ Conectado a Supabase")
            return True
        except Exception as e:
            print(f"❌ Error conectando: {e}")
            return False
    
    def cargar_locales(self) -> Dict:
        """Carga datos de local_data.json."""
        local_file = Path(".streamlit/local_data.json")
        
        if not local_file.exists():
            print("❌ No existe local_data.json")
            return {}
        
        with open(local_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def migrar_signos_vitales(self, datos: List[Dict]) -> Tuple[int, int]:
        """Migra signos vitales."""
        if not datos:
            return 0, 0
        
        print(f"\n📊 Migrando {len(datos)} signos vitales...")
        
        exitosos = 0
        fallidos = 0
        
        for i, sv in enumerate(datos, 1):
            try:
                # Adaptar formato
                data = {
                    "paciente_id": sv.get("paciente_id") or sv.get("dni") or "desconocido",
                    "tension_arterial_sistolica": self._extraer_ta_sistolica(sv.get("ta", "")),
                    "tension_arterial_diastolica": self._extraer_ta_diastolica(sv.get("ta", "")),
                    "frecuencia_cardiaca": self._to_int(sv.get("fc")),
                    "frecuencia_respiratoria": self._to_int(sv.get("fr")),
                    "temperatura": self._to_float(sv.get("temp")),
                    "saturacion_oxigeno": self._to_int(sv.get("sat")),
                    "glucemia": self._to_int(sv.get("hgt")),
                    "observaciones": sv.get("observaciones", ""),
                    "created_at": sv.get("fecha") or datetime.now().isoformat()
                }
                
                # Limpiar Nones
                data = {k: v for k, v in data.items() if v is not None}
                
                response = self.supabase.table("signos_vitales").insert(data).execute()
                
                if hasattr(response, 'data'):
                    exitosos += 1
                    print(f"  ✓ {i}/{len(datos)} - Signos vitales migrados")
                else:
                    fallidos += 1
                    print(f"  ✗ {i}/{len(datos)} - Error en respuesta")
                
                # Rate limiting
                time.sleep(0.1)
                
            except Exception as e:
                fallidos += 1
                print(f"  ✗ {i}/{len(datos)} - Error: {str(e)[:50]}")
                self.errores.append(f"Signos vitales {i}: {e}")
        
        return exitosos, fallidos
    
    def migrar_pacientes(self, datos: List[Dict]) -> Tuple[int, int]:
        """Migra pacientes."""
        if not datos:
            return 0, 0
        
        print(f"\n👥 Migrando {len(datos)} pacientes...")
        
        exitosos = 0
        fallidos = 0
        
        for i, p in enumerate(datos, 1):
            try:
                # Adaptar formato
                data = {
                    "dni": p.get("d") or p.get("dni") or f"SIN_DNI_{i}",
                    "nombre": p.get("n") or p.get("nombre") or "Sin Nombre",
                    "apellido": p.get("a") or p.get("apellido") or "",
                    "obra_social": p.get("o") or p.get("obra_social") or "",
                    "numero_afiliado": p.get("na") or p.get("numero_afiliado") or "",
                    "telefono": p.get("t") or p.get("telefono") or "",
                    "alergias": p.get("alergias", ""),
                    "estado": p.get("estado", "Activo"),
                    "created_at": datetime.now().isoformat()
                }
                
                response = self.supabase.table("pacientes").insert(data).execute()
                
                if hasattr(response, 'data'):
                    exitosos += 1
                    print(f"  ✓ {i}/{len(datos)} - Paciente {data['dni']} migrado")
                else:
                    fallidos += 1
                
                time.sleep(0.1)
                
            except Exception as e:
                fallidos += 1
                print(f"  ✗ {i}/{len(datos)} - Error: {str(e)[:50]}")
                self.errores.append(f"Paciente {i}: {e}")
        
        return exitosos, fallidos
    
    def migrar_usuarios(self, datos: List[Dict]) -> Tuple[int, int]:
        """Migra usuarios."""
        if not datos:
            return 0, 0
        
        print(f"\n👤 Migrando {len(datos)} usuarios...")
        
        exitosos = 0
        fallidos = 0
        
        for i, u in enumerate(datos, 1):
            try:
                data = {
                    "email": u.get("email") or u.get("usuario") or f"usuario{i}@temp.com",
                    "nombre": u.get("nombre") or u.get("n") or "Sin Nombre",
                    "rol": u.get("rol", "medico"),
                    "matricula": u.get("matricula", ""),
                    "estado": u.get("estado", "Activo"),
                    "created_at": datetime.now().isoformat()
                }
                
                response = self.supabase.table("usuarios").insert(data).execute()
                
                if hasattr(response, 'data'):
                    exitosos += 1
                    print(f"  ✓ {i}/{len(datos)} - Usuario {data['email']} migrado")
                else:
                    fallidos += 1
                
                time.sleep(0.1)
                
            except Exception as e:
                fallidos += 1
                print(f"  ✗ {i}/{len(datos)} - Error: {str(e)[:50]}")
                self.errores.append(f"Usuario {i}: {e}")
        
        return exitosos, fallidos
    
    def _extraer_ta_sistolica(self, ta: str) -> int:
        """Extrae TA sistólica de formato '120/80'."""
        try:
            if "/" in str(ta):
                return int(str(ta).split("/")[0])
        except:
            pass
        return None
    
    def _extraer_ta_diastolica(self, ta: str) -> int:
        """Extrae TA diastólica de formato '120/80'."""
        try:
            if "/" in str(ta):
                return int(str(ta).split("/")[1])
        except:
            pass
        return None
    
    def _to_int(self, val) -> int:
        """Convierte a int seguro."""
        try:
            return int(float(val)) if val else None
        except:
            return None
    
    def _to_float(self, val) -> float:
        """Convierte a float seguro."""
        try:
            return float(val) if val else None
        except:
            return None
    
    def ejecutar(self):
        """Ejecuta la migración completa."""
        print("="*70)
        print("MIGRACIÓN DE DATOS A SUPABASE")
        print("="*70)
        
        # Conectar
        if not self.conectar():
            return False
        
        # Cargar datos locales
        datos = self.cargar_locales()
        if not datos:
            return False
        
        resultados = {}
        
        # Migrar cada entidad
        resultados["pacientes"] = self.migrar_pacientes(datos.get("pacientes_db", []))
        resultados["usuarios"] = self.migrar_usuarios(datos.get("usuarios_db", []))
        resultados["signos_vitales"] = self.migrar_signos_vitales(datos.get("vitales_db", []))
        
        # Resumen
        print("\n" + "="*70)
        print("RESUMEN DE MIGRACIÓN")
        print("="*70)
        
        total_exitosos = 0
        total_fallidos = 0
        
        for entidad, (exitosos, fallidos) in resultados.items():
            total = exitosos + fallidos
            if total > 0:
                porcentaje = (exitosos / total) * 100
                print(f"{entidad:20s}: {exitosos:4d}/{total:4d} ({porcentaje:5.1f}%) ✓")
                total_exitosos += exitosos
                total_fallidos += fallidos
        
        print(f"\nTotal: {total_exitosos} migrados, {total_fallidos} fallidos")
        
        if self.errores:
            print(f"\n⚠️ {len(self.errores)} errores registrados")
            
            # Guardar log de errores
            with open('errores_migracion.txt', 'w', encoding='utf-8') as f:
                for error in self.errores:
                    f.write(f"{error}\n")
            print("Log de errores guardado en: errores_migracion.txt")
        
        return total_fallidos == 0


def main():
    migrador = MigradorSupabase()
    exito = migrador.ejecutar()
    
    if exito:
        print("\n✅ Migración completada exitosamente")
    else:
        print("\n⚠️ Migración completada con errores")
    
    return exito


if __name__ == "__main__":
    main()
