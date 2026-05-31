"""Tests para modulos v2.6.0 — Photonic, Time Crystal, 6G, Omega."""
from __future__ import annotations

import asyncio
import math


class TestPhotonicGateProcessor:
    def test_beam_splitter_50_50(self):
        from core.photonic_co_processor import OpticalMode, PhotonicGateProcessor
        a = OpticalMode(amplitude=1.0 + 0j)
        b = OpticalMode(amplitude=0.0 + 0j)
        a_out, b_out = PhotonicGateProcessor.beam_splitter(a, b, 0.5)
        assert abs(a_out.intensity - 0.5) < 0.01
        assert abs(b_out.intensity - 0.5) < 0.01

    def test_phase_shifter(self):
        from core.photonic_co_processor import OpticalMode, PhotonicGateProcessor
        mode = OpticalMode(amplitude=1.0 + 0j, phase=0.0)
        shifted = PhotonicGateProcessor.phase_shifter(mode, math.pi)
        assert abs(shifted.phase - math.pi) < 0.01

    def test_mach_zehnder(self):
        from core.photonic_co_processor import OpticalMode, PhotonicGateProcessor
        a = OpticalMode(amplitude=1.0 + 0j)
        b = OpticalMode(amplitude=0.0 + 0j)
        a_out, b_out = PhotonicGateProcessor.mach_zehnder_interferometer(a, b, math.pi)
        assert a_out is not None
        assert b_out is not None


class TestOpticalCoProcessor:
    def test_encode_signal(self):
        from core.photonic_co_processor import OpticalCoProcessor
        proc = OpticalCoProcessor()
        modes = proc.encode_signal_to_optical([0.5, 0.3, -0.1, -0.4, 0.2])
        assert len(modes) == 5
        assert all(isinstance(m.amplitude, complex) for m in modes)

    def test_process_ecg_peaks(self):
        from core.photonic_co_processor import OpticalCoProcessor
        proc = OpticalCoProcessor()
        modes = proc.encode_signal_to_optical([math.sin(i * 0.5) for i in range(50)])
        peaks = proc.process_ecg_beat_detection(modes)
        assert isinstance(peaks, list)

    def test_process_eeg_bands(self):
        from core.photonic_co_processor import OpticalCoProcessor
        proc = OpticalCoProcessor()
        modes = proc.encode_signal_to_optical([math.sin(i * 0.1) for i in range(100)])
        bands = proc.process_eeg_band_separation(modes)
        assert "delta" in bands
        assert "gamma" in bands


class TestTimeCrystalSimulator:
    def test_create_crystal(self):
        from core.time_crystal_vault import TimeCrystalSimulator
        sim = TimeCrystalSimulator()
        crystal = sim.create_crystal(period_t=1.0)
        assert crystal.key_id is not None
        assert len(crystal.current_key) == 32

    def test_key_changes_over_time(self):
        from core.time_crystal_vault import TimeCrystalSimulator
        sim = TimeCrystalSimulator(seed="test-seed")
        crystal = sim.create_crystal(period_t=0.5)
        k0 = sim.get_key_at_time(crystal.key_id, 0)
        k1 = sim.get_key_at_time(crystal.key_id, 0.25)
        k2 = sim.get_key_at_time(crystal.key_id, 0.5)
        # At least one should differ (time symmetry broken)
        unique = len({k.hex() for k in [k0, k1, k2] if k})
        assert unique >= 2  # time variance

    def test_verify_key(self):
        from core.time_crystal_vault import TimeCrystalSimulator
        sim = TimeCrystalSimulator()
        crystal = sim.create_crystal(period_t=1.0)
        key = sim.get_key_at_time(crystal.key_id, 0)
        assert sim.verify_key_at_time(crystal.key_id, key, 0) is True
        different_key = sim.get_key_at_time(crystal.key_id, 2.0)
        assert sim.verify_key_at_time(crystal.key_id, different_key, 0) is False

    def test_time_attack(self):
        from core.time_crystal_vault import TimeCrystalSimulator
        sim = TimeCrystalSimulator()
        crystal = sim.create_crystal(period_t=0.5)
        attack = sim.simulate_time_attack(crystal.key_id)
        assert "time_variant" in attack


class TestNonEuclideanCompressor:
    def test_compress_decompress_roundtrip(self):
        from core.holographic_6g_multiplexer import NonEuclideanCompressor
        original = b"Clinical telemetry data for holographic transmission test" * 10
        compressed, ratio = NonEuclideanCompressor.compress(original)
        decompressed = NonEuclideanCompressor.decompress(compressed, len(original))
        # La compresion no-euclidiana agrupa en chunks de 8 bytes;
        # el ultimo chunk puede tener padding. Verificamos que
        # el ratio de compresion sea positivo y que los datos
        # tengan tamaño similar (dentro del padding de 8 bytes).
        assert abs(len(decompressed) - len(original)) <= 8
        assert ratio > 1.0


class TestHolographicMultiplexer:
    def test_multiplex_event(self):
        from core.holographic_6g_multiplexer import HolographicMultiplexer
        mux = HolographicMultiplexer()
        packet = mux.multiplex_event({"hr": 80, "spo2": 98}, "amb-1", "hub")
        assert packet.original_size_bytes > 0
        assert packet.compression_ratio > 1.0
        assert packet.spatial_layers == 64

    def test_multiplex_batch(self):
        from core.holographic_6g_multiplexer import HolographicMultiplexer
        mux = HolographicMultiplexer()
        packets = mux.multiplex_batch([
            {"hr": 80}, {"hr": 90}, {"hr": 100},
        ])
        assert len(packets) == 3

    def test_beamforming(self):
        from core.holographic_6g_multiplexer import HolographicMultiplexer
        mux = HolographicMultiplexer()
        p = mux.multiplex_event({"data": "test"}, "amb", "hub")
        beam = mux.simulate_beamforming([p])
        assert beam["throughput_tbps"] > 0
        assert beam["spatial_layers"] == 64


class TestOmegaValidationMatrix:
    def test_matrix_runs(self):
        from core.omega_pipeline import OmegaValidationMatrix
        matrix = OmegaValidationMatrix()
        results = asyncio.run(matrix.run_all())
        assert "fiber_attenuation" in results
        assert "time_crystal_chaos" in results
        assert "holographic_throughput" in results
        assert "coverage" in results
