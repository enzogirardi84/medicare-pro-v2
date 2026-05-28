"""Tests para core.iot_medical_devices."""
from __future__ import annotations

import pytest


class TestIotMedicalDevices:
    """Tests para funciones públicas de core.iot_medical_devices."""

    def test_iot_medical_devices_importable(self):
        import core.iot_medical_devices
        assert core.iot_medical_devices is not None

    def test_functions_exist(self):
        import core.iot_medical_devices
        assert callable(core.iot_medical_devices.get_iot_manager)
        assert callable(core.iot_medical_devices.pair_new_device)
        assert callable(core.iot_medical_devices.read_and_save_vitals)
        assert callable(core.iot_medical_devices.to_dict)
        assert callable(core.iot_medical_devices.to_dict)
        assert callable(core.iot_medical_devices.connect)
        assert callable(core.iot_medical_devices.disconnect)
        assert callable(core.iot_medical_devices.read_data)
        assert callable(core.iot_medical_devices.validate_reading)
        assert callable(core.iot_medical_devices.connect)
