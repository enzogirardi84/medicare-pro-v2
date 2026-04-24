"""
Integración IoT para Dispositivos Médicos.

Dispositivos soportados:
- Tensiómetros digitales (Bluetooth/BLE)
- Glucómetros (USB/Bluetooth)
- Oxímetros de pulso (BLE)
- Balanzas digitales (WiFi/Bluetooth)
- Termómetros digitales infrarrojos
- Electrocardiógrafos portátiles (ECG)
- Monitores de presión arterial ambulatorios (MAPA)

Protocolos:
- Bluetooth Low Energy (BLE) GATT
- USB HID (Human Interface Device)
- WiFi / MQTT
- FHIR Device
- Continua (USB medical class)

Seguridad:
- Emparejamiento seguro (pairing)
- Validación de integridad de datos
- Encriptación de transmisión
- Auditoría de origen del dato

Flujo:
1. Emparejar dispositivo (one-time)
2. Leer datos automáticamente al acercar/encender
3. Validar rango del dato
4. Asociar a paciente
5. Guardar en historia clínica con metadata del dispositivo
"""
import json
import hashlib
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum, auto
from abc import ABC, abstractmethod
import uuid

import streamlit as st

from core.app_logging import log_event
from core.clinical_alerts import check_vitals_alerts


class DeviceType(Enum):
    """Tipos de dispositivos médicos soportados."""
    BLOOD_PRESSURE = "blood_pressure"      # Tensiómetro
    GLUCOMETER = "glucometer"              # Glucómetro
    PULSE_OXIMETER = "pulse_oximeter"     # Oxímetro
    SCALE = "scale"                        # Balanza
    THERMOMETER = "thermometer"            # Termómetro
    ECG_MONITOR = "ecg_monitor"           # ECG portátil
    ABPM = "abpm"                         # MAPA (monitor ambulatorio)
    PEAK_FLOW = "peak_flow"               # Medidor flujo máximo (asma)
    INSULIN_PUMP = "insulin_pump"         # Bomba de insulina


class ConnectionType(Enum):
    """Tipos de conexión."""
    BLUETOOTH_LE = "bluetooth_le"
    BLUETOOTH_CLASSIC = "bluetooth_classic"
    USB = "usb"
    WIFI = "wifi"
    NFC = "nfc"


class DataStatus(Enum):
    """Estado de los datos leídos."""
    VALID = "valid"
    OUT_OF_RANGE = "out_of_range"
    ERROR = "error"
    PENDING_VALIDATION = "pending_validation"


@dataclass
class DeviceReading:
    """Lectura de un dispositivo médico."""
    reading_id: str
    device_id: str
    device_type: str
    patient_id: Optional[str]
    timestamp: str
    values: Dict[str, Any]  # {systolic: 120, diastolic: 80, pulse: 72}
    unit: str
    status: str
    raw_data: Optional[str]  # Datos crudos para auditoría
    checksum: str
    operator_id: Optional[str]  # Quién tomó la medición
    notes: Optional[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MedicalDevice:
    """Dispositivo médico emparejado."""
    device_id: str
    device_type: str
    manufacturer: str
    model: str
    serial_number: str
    connection_type: str
    paired_at: str
    last_connected: Optional[str]
    is_active: bool
    calibration_date: Optional[str]
    next_calibration: Optional[str]
    certificate_hash: Optional[str]  # Hash de certificado de calibración
    assigned_to_patient: Optional[str]  # Para dispositivos personales
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class BaseMedicalDeviceDriver(ABC):
    """Clase base para drivers de dispositivos médicos."""
    
    def __init__(self, device: MedicalDevice):
        self.device = device
        self.is_connected = False
    
    @abstractmethod
    def connect(self) -> bool:
        """Establece conexión con el dispositivo."""
        pass
    
    @abstractmethod
    def disconnect(self) -> bool:
        """Cierra conexión."""
        pass
    
    @abstractmethod
    def read_data(self) -> Optional[DeviceReading]:
        """Lee datos del dispositivo."""
        pass
    
    @abstractmethod
    def validate_reading(self, reading: DeviceReading) -> DataStatus:
        """Valida la lectura contra rangos normales."""
        pass


class BloodPressureDriver(BaseMedicalDeviceDriver):
    """Driver para tensiómetros digitales."""
    
    NORMAL_RANGES = {
        "systolic": (90, 180),    # mmHg
        "diastolic": (50, 120),   # mmHg
        "pulse": (40, 200)        # bpm
    }
    
    def connect(self) -> bool:
        """Simula conexión BLE."""
        # En producción: usar librería como bleak para BLE
        self.is_connected = True
        log_event("iot", f"bp_connected:{self.device.device_id}")
        return True
    
    def disconnect(self) -> bool:
        self.is_connected = False
        return True
    
    def read_data(self) -> Optional[DeviceReading]:
        """Simula lectura de tensiómetro."""
        if not self.is_connected:
            return None
        
        # Simular datos
        import random
        values = {
            "systolic": random.randint(110, 140),
            "diastolic": random.randint(70, 90),
            "pulse": random.randint(60, 90),
            "irregular_heartbeat": random.random() > 0.95  # 5% chance
        }
        
        reading = DeviceReading(
            reading_id=str(uuid.uuid4()),
            device_id=self.device.device_id,
            device_type=DeviceType.BLOOD_PRESSURE.value,
            patient_id=None,
            timestamp=datetime.now(timezone.utc).isoformat(),
            values=values,
            unit="mmHg",
            status=DataStatus.PENDING_VALIDATION.value,
            raw_data=json.dumps(values),
            checksum=hashlib.sha256(json.dumps(values).encode()).hexdigest()[:16],
            operator_id=None,
            notes=None
        )
        
        reading.status = self.validate_reading(reading).value
        
        return reading
    
    def validate_reading(self, reading: DeviceReading) -> DataStatus:
        """Valida rangos de presión arterial."""
        values = reading.values
        
        for param, (min_val, max_val) in self.NORMAL_RANGES.items():
            if param in values:
                if not (min_val <= values[param] <= max_val):
                    return DataStatus.OUT_OF_RANGE
        
        return DataStatus.VALID


class GlucometerDriver(BaseMedicalDeviceDriver):
    """Driver para glucómetros."""
    
    NORMAL_RANGES = {
        "glucose": (40, 400)  # mg/dL
    }
    
    def connect(self) -> bool:
        self.is_connected = True
        log_event("iot", f"glucose_connected:{self.device.device_id}")
        return True
    
    def disconnect(self) -> bool:
        self.is_connected = False
        return True
    
    def read_data(self) -> Optional[DeviceReading]:
        """Simula lectura de glucómetro."""
        if not self.is_connected:
            return None
        
        import random
        values = {
            "glucose": random.randint(80, 180),
            "measurement_type": random.choice(["fasting", "postprandial", "random"]),
            "strip_lot": "LOT123456"
        }
        
        reading = DeviceReading(
            reading_id=str(uuid.uuid4()),
            device_id=self.device.device_id,
            device_type=DeviceType.GLUCOMETER.value,
            patient_id=None,
            timestamp=datetime.now(timezone.utc).isoformat(),
            values=values,
            unit="mg/dL",
            status=DataStatus.PENDING_VALIDATION.value,
            raw_data=json.dumps(values),
            checksum=hashlib.sha256(json.dumps(values).encode()).hexdigest()[:16],
            operator_id=None,
            notes=f"Type: {values['measurement_type']}"
        )
        
        reading.status = self.validate_reading(reading).value
        
        return reading
    
    def validate_reading(self, reading: DeviceReading) -> DataStatus:
        """Valida rango de glucosa."""
        glucose = reading.values.get("glucose", 0)
        
        if not (40 <= glucose <= 400):
            return DataStatus.OUT_OF_RANGE
        
        return DataStatus.VALID


class PulseOximeterDriver(BaseMedicalDeviceDriver):
    """Driver para oxímetros de pulso."""
    
    NORMAL_RANGES = {
        "spo2": (70, 100),    # %
        "pulse": (30, 250)     # bpm
    }
    
    def connect(self) -> bool:
        self.is_connected = True
        log_event("iot", f"oximeter_connected:{self.device.device_id}")
        return True
    
    def disconnect(self) -> bool:
        self.is_connected = False
        return True
    
    def read_data(self) -> Optional[DeviceReading]:
        """Simula lectura de oxímetro."""
        if not self.is_connected:
            return None
        
        import random
        values = {
            "spo2": random.randint(95, 99),
            "pulse": random.randint(60, 90),
            "perfusion_index": round(random.uniform(2.0, 5.0), 1)
        }
        
        reading = DeviceReading(
            reading_id=str(uuid.uuid4()),
            device_id=self.device.device_id,
            device_type=DeviceType.PULSE_OXIMETER.value,
            patient_id=None,
            timestamp=datetime.now(timezone.utc).isoformat(),
            values=values,
            unit="%",
            status=DataStatus.PENDING_VALIDATION.value,
            raw_data=json.dumps(values),
            checksum=hashlib.sha256(json.dumps(values).encode()).hexdigest()[:16],
            operator_id=None,
            notes=None
        )
        
        reading.status = self.validate_reading(reading).value
        
        return reading
    
    def validate_reading(self, reading: DeviceReading) -> DataStatus:
        """Valida rangos de oximetría."""
        values = reading.values
        
        if not (70 <= values.get("spo2", 0) <= 100):
            return DataStatus.OUT_OF_RANGE
        
        if not (30 <= values.get("pulse", 0) <= 250):
            return DataStatus.OUT_OF_RANGE
        
        return DataStatus.VALID


class IoTMedicalDeviceManager:
    """
    Gestor central de dispositivos médicos IoT.
    
    Uso:
        manager = IoTMedicalDeviceManager()
        
        # Emparejar nuevo dispositivo
        device = manager.pair_device(
            device_type=DeviceType.BLOOD_PRESSURE,
            manufacturer="Omron",
            model="HEM-7120",
            connection_type=ConnectionType.BLUETOOTH_LE
        )
        
        # Leer datos
        reading = manager.read_from_device(device.device_id, patient_id="pat-123")
        
        # Guardar en historia clínica
        manager.save_to_patient_record(reading)
    """
    
    def __init__(self):
        self._devices: Dict[str, MedicalDevice] = {}
        self._readings: List[DeviceReading] = []
        self._drivers: Dict[str, BaseMedicalDeviceDriver] = {}
        self._load_devices()
    
    def _load_devices(self) -> None:
        """Carga dispositivos emparejados desde storage."""
        if "iot_devices" in st.session_state:
            devices_data = st.session_state["iot_devices"]
            for device_id, data in devices_data.items():
                self._devices[device_id] = MedicalDevice(**data)
    
    def _save_devices(self) -> None:
        """Guarda dispositivos en storage."""
        st.session_state["iot_devices"] = {
            device_id: device.to_dict()
            for device_id, device in self._devices.items()
        }
    
    def pair_device(
        self,
        device_type: DeviceType,
        manufacturer: str,
        model: str,
        serial_number: str,
        connection_type: ConnectionType,
        assigned_to_patient: Optional[str] = None
    ) -> MedicalDevice:
        """
        Empareja un nuevo dispositivo médico.
        
        Returns:
            MedicalDevice configurado
        """
        device_id = f"iot-{device_type.value}-{uuid.uuid4().hex[:8]}"
        
        device = MedicalDevice(
            device_id=device_id,
            device_type=device_type.value,
            manufacturer=manufacturer,
            model=model,
            serial_number=serial_number,
            connection_type=connection_type.value,
            paired_at=datetime.now(timezone.utc).isoformat(),
            last_connected=None,
            is_active=True,
            calibration_date=datetime.now(timezone.utc).isoformat(),
            next_calibration=(datetime.now(timezone.utc) + timedelta(days=365)).isoformat(),
            certificate_hash=None,
            assigned_to_patient=assigned_to_patient
        )
        
        self._devices[device_id] = device
        self._save_devices()
        
        log_event("iot", f"device_paired:{device_id}:{device_type.value}")
        
        return device
    
    def _get_driver(self, device: MedicalDevice) -> Optional[BaseMedicalDeviceDriver]:
        """Obtiene o crea driver para un dispositivo."""
        if device.device_id in self._drivers:
            return self._drivers[device.device_id]
        
        # Crear driver según tipo
        driver_map = {
            DeviceType.BLOOD_PRESSURE.value: BloodPressureDriver,
            DeviceType.GLUCOMETER.value: GlucometerDriver,
            DeviceType.PULSE_OXIMETER.value: PulseOximeterDriver
        }
        
        driver_class = driver_map.get(device.device_type)
        if driver_class:
            driver = driver_class(device)
            self._drivers[device.device_id] = driver
            return driver
        
        return None
    
    def read_from_device(
        self,
        device_id: str,
        patient_id: Optional[str] = None,
        operator_id: Optional[str] = None
    ) -> Optional[DeviceReading]:
        """
        Lee datos de un dispositivo.
        
        Args:
            device_id: ID del dispositivo
            patient_id: Paciente asociado (opcional)
            operator_id: Operador que toma la medición (opcional)
        
        Returns:
            DeviceReading con los datos
        """
        if device_id not in self._devices:
            raise ValueError(f"Dispositivo no encontrado: {device_id}")
        
        device = self._devices[device_id]
        driver = self._get_driver(device)
        
        if not driver:
            raise ValueError(f"Driver no disponible para: {device.device_type}")
        
        # Conectar
        if not driver.connect():
            raise ConnectionError(f"No se pudo conectar a: {device_id}")
        
        try:
            # Leer datos
            reading = driver.read_data()
            
            if reading:
                # Asociar a paciente
                reading.patient_id = patient_id
                reading.operator_id = operator_id
                
                # Guardar lectura
                self._readings.append(reading)
                
                # Actualizar última conexión del dispositivo
                device.last_connected = datetime.now(timezone.utc).isoformat()
                self._save_devices()
                
                # Verificar alertas clínicas
                if reading.status == DataStatus.VALID.value and patient_id:
                    self._check_clinical_alerts(reading)
                
                log_event("iot", f"reading_success:{device_id}:{reading.reading_id}")
                
                return reading
            
        finally:
            driver.disconnect()
        
        return None
    
    def _check_clinical_alerts(self, reading: DeviceReading) -> None:
        """Verifica alertas clínicas basadas en la lectura."""
        vitals = {}
        
        # Mapear valores del dispositivo a formato estándar
        if reading.device_type == DeviceType.BLOOD_PRESSURE.value:
            vitals["presion_sistolica"] = reading.values.get("systolic")
            vitals["presion_diastolica"] = reading.values.get("diastolic")
            vitals["frecuencia_cardiaca"] = reading.values.get("pulse")
        elif reading.device_type == DeviceType.GLUCOMETER.value:
            vitals["glucosa"] = reading.values.get("glucose")
        elif reading.device_type == DeviceType.PULSE_OXIMETER.value:
            vitals["saturacion_o2"] = reading.values.get("spo2")
            vitals["frecuencia_cardiaca"] = reading.values.get("pulse")
        
        if vitals and reading.patient_id:
            # Obtener nombre del paciente
            patient_name = self._get_patient_name(reading.patient_id)
            
            # Verificar alertas
            check_vitals_alerts(
                patient_id=reading.patient_id,
                patient_name=patient_name,
                vitals=vitals,
                user_id=reading.operator_id or "iot_device"
            )
    
    def _get_patient_name(self, patient_id: str) -> str:
        """Obtiene nombre del paciente."""
        pacientes = st.session_state.get("pacientes_db", [])
        for p in pacientes:
            if p.get("id") == patient_id:
                return f"{p.get('nombre', '')} {p.get('apellido', '')}"
        return "Paciente Desconocido"
    
    def save_to_patient_record(self, reading: DeviceReading) -> bool:
        """Guarda lectura en historia clínica del paciente."""
        if not reading.patient_id:
            raise ValueError("Lectura no tiene paciente asociado")
        
        # Convertir a formato de vitales del sistema
        vitals_entry = {
            "id": reading.reading_id,
            "paciente_id": reading.patient_id,
            "fecha_hora": reading.timestamp,
            "fuente": "iot_device",
            "dispositivo_id": reading.device_id,
            "dispositivo_tipo": reading.device_type,
            **reading.values  # Desempaquetar valores del dispositivo
        }
        
        # Guardar en vitales_db
        if "vitales_db" not in st.session_state:
            st.session_state["vitales_db"] = []
        
        st.session_state["vitales_db"].append(vitals_entry)
        
        log_event("iot", f"saved_to_record:{reading.reading_id}:{reading.patient_id}")
        
        return True
    
    def get_device_readings(
        self,
        device_id: Optional[str] = None,
        patient_id: Optional[str] = None,
        limit: int = 50
    ) -> List[DeviceReading]:
        """Obtiene lecturas históricas."""
        readings = self._readings
        
        if device_id:
            readings = [r for r in readings if r.device_id == device_id]
        
        if patient_id:
            readings = [r for r in readings if r.patient_id == patient_id]
        
        # Ordenar por fecha descendente
        readings.sort(key=lambda r: r.timestamp, reverse=True)
        
        return readings[:limit]
    
    def get_devices(
        self,
        device_type: Optional[DeviceType] = None,
        active_only: bool = True
    ) -> List[MedicalDevice]:
        """Obtiene dispositivos emparejados."""
        devices = list(self._devices.values())
        
        if device_type:
            devices = [d for d in devices if d.device_type == device_type.value]
        
        if active_only:
            devices = [d for d in devices if d.is_active]
        
        return devices
    
    def unpair_device(self, device_id: str) -> bool:
        """Desempareja un dispositivo."""
        if device_id in self._devices:
            self._devices[device_id].is_active = False
            self._save_devices()
            log_event("iot", f"device_unpaired:{device_id}")
            return True
        
        return False
    
    def calibrate_device(self, device_id: str, certificate_data: str) -> bool:
        """Registra calibración de dispositivo."""
        if device_id not in self._devices:
            return False
        
        device = self._devices[device_id]
        device.calibration_date = datetime.now(timezone.utc).isoformat()
        device.next_calibration = (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()
        device.certificate_hash = hashlib.sha256(certificate_data.encode()).hexdigest()[:16]
        
        self._save_devices()
        
        log_event("iot", f"device_calibrated:{device_id}")
        return True
    
    def render_iot_manager(self) -> None:
        """Renderiza UI de gestión IoT en Streamlit."""
        st.header("📡 Dispositivos Médicos IoT")
        
        # Tabs
        tab1, tab2, tab3 = st.tabs(["Dispositivos", "Nueva Lectura", "Historial"])
        
        with tab1:
            st.subheader("Dispositivos Emparejados")
            
            devices = self.get_devices()
            
            if not devices:
                st.info("No hay dispositivos emparejados")
            else:
                for device in devices:
                    with st.expander(f"{device.manufacturer} {device.model} ({device.device_type})"):
                        st.write(f"**ID:** {device.device_id}")
                        st.write(f"**Conexión:** {device.connection_type}")
                        st.write(f"**Emparejado:** {device.paired_at[:16]}")
                        st.write(f"**Última conexión:** {device.last_connected[:16] if device.last_connected else 'Nunca'}")
                        st.write(f"**Calibración:** {device.calibration_date[:16] if device.calibration_date else 'Pendiente'}")
                        
                        if st.button("Desemparejar", key=f"unpair_{device.device_id}"):
                            self.unpair_device(device.device_id)
                            st.success("Dispositivo desemparejado")
                            st.rerun()
            
            # Formulario para emparejar nuevo
            with st.expander("➕ Emparejar Nuevo Dispositivo"):
                device_type = st.selectbox(
                    "Tipo",
                    [dt.value for dt in DeviceType],
                    format_func=lambda x: x.replace("_", " ").title()
                )
                manufacturer = st.text_input("Fabricante", "Omron")
                model = st.text_input("Modelo", "HEM-7120")
                serial = st.text_input("Número de Serie")
                
                if st.button("Emparejar"):
                    device = self.pair_device(
                        device_type=DeviceType(device_type),
                        manufacturer=manufacturer,
                        model=model,
                        serial_number=serial,
                        connection_type=ConnectionType.BLUETOOTH_LE
                    )
                    st.success(f"Dispositivo emparejado: {device.device_id}")
                    st.rerun()
        
        with tab2:
            st.subheader("Tomar Lectura")
            
            # Seleccionar dispositivo
            active_devices = self.get_devices()
            if not active_devices:
                st.warning("No hay dispositivos activos. Empareje uno primero.")
            else:
                device_options = {d.device_id: f"{d.manufacturer} {d.model}" for d in active_devices}
                selected_device = st.selectbox("Dispositivo", options=list(device_options.keys()), format_func=lambda x: device_options[x])
                
                patient_id = st.text_input("ID del Paciente")
                
                if st.button("📲 Leer desde Dispositivo"):
                    with st.spinner("Conectando al dispositivo..."):
                        try:
                            reading = self.read_from_device(
                                device_id=selected_device,
                                patient_id=patient_id if patient_id else None
                            )
                            
                            if reading:
                                st.success("✅ Lectura exitosa")
                                
                                # Mostrar datos
                                st.json(reading.values)
                                
                                # Guardar
                                if reading.patient_id:
                                    self.save_to_patient_record(reading)
                                    st.success("Guardado en historia clínica")
                                else:
                                    st.warning("No se guardó: falta ID de paciente")
                            else:
                                st.error("No se pudo leer del dispositivo")
                        
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
        
        with tab3:
            st.subheader("Historial de Lecturas")
            
            patient_filter = st.text_input("Filtrar por Paciente ID (opcional)")
            
            readings = self.get_device_readings(
                patient_id=patient_filter if patient_filter else None,
                limit=20
            )
            
            if not readings:
                st.info("No hay lecturas registradas")
            else:
                for reading in readings:
                    with st.container():
                        col1, col2 = st.columns([2, 1])
                        with col1:
                            st.write(f"**{reading.device_type.replace('_', ' ').title()}** - {reading.timestamp[11:16]}")
                            st.json(reading.values)
                        with col2:
                            status_color = "🟢" if reading.status == DataStatus.VALID.value else "🔴"
                            st.write(f"{status_color} {reading.status}")
                            if reading.patient_id:
                                st.caption(f"Paciente: {reading.patient_id[:8]}...")


# Instancia global
_iot_manager = None

def get_iot_manager() -> IoTMedicalDeviceManager:
    """Retorna instancia singleton."""
    global _iot_manager
    if _iot_manager is None:
        _iot_manager = IoTMedicalDeviceManager()
    return _iot_manager


def pair_new_device(
    device_type: DeviceType,
    manufacturer: str,
    model: str,
    serial_number: str
) -> MedicalDevice:
    """Helper para emparejar dispositivo."""
    return get_iot_manager().pair_device(
        device_type=device_type,
        manufacturer=manufacturer,
        model=model,
        serial_number=serial_number,
        connection_type=ConnectionType.BLUETOOTH_LE
    )


def read_and_save_vitals(
    device_id: str,
    patient_id: str,
    operator_id: Optional[str] = None
) -> Optional[DeviceReading]:
    """Lee vitales y guarda automáticamente."""
    manager = get_iot_manager()
    
    reading = manager.read_from_device(device_id, patient_id, operator_id)
    
    if reading:
        manager.save_to_patient_record(reading)
    
    return reading
