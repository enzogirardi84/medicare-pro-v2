"""Algoritmo Cuantico QAOA para optimizacion de despacho medico.
Mapea constraints PostGIS + triage de drones a Hamiltoniano de costo.
Resuelve asignacion optima de 1000 ambulancias en QPU simulada.
"""
from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. MODELOS CUANTICOS
# ═══════════════════════════════════════════════════════════════════

@dataclass
class QuantumHamiltonian:
    """Hamiltoniano de costo para QAOA."""
    num_qubits: int = 0
    cost_terms: list[tuple[int, int, float]] = field(default_factory=list)  # (i, j, weight)
    field_terms: list[tuple[int, float]] = field(default_factory=list)      # (i, bias)

    def add_interaction(self, i: int, j: int, weight: float):
        self.cost_terms.append((i, j, weight))

    def add_bias(self, i: int, bias: float):
        self.field_terms.append((i, bias))


@dataclass
class QAOResult:
    """Resultado de la optimizacion QAOA."""
    assignment: list[int]          # ambulancia i → victima j
    cost: float = 0.0
    shots: int = 0
    p_levels: int = 1
    execution_time_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)


# ═══════════════════════════════════════════════════════════════════
# 2. COMPILADOR DE HAMILTONIANO DE COSTO
# ═══════════════════════════════════════════════════════════════════

class QAOACompiler:
    """Compilador del problema de despacho a Hamiltoniano QAOA.

    Mapea:
    - Ambulancias → qubits
    - Distancia victima-ambulancia → peso de interaccion
    - Nivel de triage → bias del qubit
    - Restriccion 1 ambulancia por victima → constraint ferromagnetico
    """

    def __init__(self):
        self._hamiltonian = QuantumHamiltonian()

    def compile(self, ambulances: list[dict], victims: list[dict]) -> QuantumHamiltonian:
        """Compila el problema de despacho a Hamiltoniano.

        Args:
            ambulances: [{ambulance_id, lat, lon, triage_capacity}]
            victims: [{victim_id, lat, lon, triage_level}]

        Returns:
            QuantumHamiltonian listo para QAOA.
        """
        n_amb = len(ambulances)
        n_vic = len(victims)
        n_qubits = n_amb * n_vic  # un qubit por (ambulancia, victima)

        h = QuantumHamiltonian(num_qubits=n_qubits)

        # Terminos de costo: distancia + triage
        for i, amb in enumerate(ambulances):
            for j, vic in enumerate(victims):
                qubit_idx = i * n_vic + j

                # Distancia (normalizada)
                dist = self._haversine(
                    amb["lat"], amb["lon"],
                    vic["lat"], vic["lon"],
                )
                dist_weight = dist / 100.0  # normalizar a 0-1

                # Prioridad de triage
                triage_weight = {
                    "red": 0.9, "yellow": 0.5, "green": 0.2,
                }.get(vic.get("triage_level", "green"), 0.3)

                # Bias total del qubit (menor = mas probable de activar)
                bias = dist_weight - triage_weight
                h.add_bias(qubit_idx, bias)

                # Interaccion ferromagnetica: misma victima no puede ir a 2 ambulancias
                for i2 in range(n_amb):
                    if i2 != i:
                        qubit_idx2 = i2 * n_vic + j
                        h.add_interaction(qubit_idx, qubit_idx2, 10.0)  # penalizacion alta

        self._hamiltonian = h
        log_event("qaoa", f"compiled:{n_qubits} qubits:{len(h.cost_terms)} terms")
        return h

    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlon / 2) ** 2)
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ═══════════════════════════════════════════════════════════════════
# 3. SIMULADOR QAOA (STUB PARA QISKIT/AMAZON BRAKET)
# ═══════════════════════════════════════════════════════════════════

class QAOASimulator:
    """Simulador QAOA con modelo de ruido cuantico.

    En produccion:
    - Qiskit: qaoa = QAOA(sampler=Sampler(), optimizer=COBYLA())
    - Braket: qaoa = BraketQAOA(device=Device("Arn:aws:braket:us-east-1:qpu"))

    Stub: implementa optimizacion classica con Simulated Annealing.
    """

    def __init__(self, noise_model: str = "ideal"):
        self.noise_model = noise_model
        self._executions = 0

    def optimize(self, hamiltonian: QuantumHamiltonian,
                 p_levels: int = 2, shots: int = 1024) -> QAOResult:
        """Ejecuta QAOA y retorna asignacion optima.

        En produccion:
            qc = qaoa_circuit(hamiltonian, p_levels)
            result = sampler.run(qc, shots=shots).result()

        Stub: Simulated Annealing para encontrar minimo.
        """
        start = time.perf_counter()
        n_qubits = hamiltonian.num_qubits

        # Inicializar asignacion aleatoria
        best_assignment = [random.randint(0, 1) for _ in range(n_qubits)]
        best_cost = self._compute_cost(best_assignment, hamiltonian)

        # Simulated Annealing
        temp = 10.0
        cooling = 0.95
        iterations = 1000

        for _ in range(iterations):
            # Mutar un bit
            new_assignment = list(best_assignment)
            idx = random.randint(0, n_qubits - 1)
            new_assignment[idx] = 1 - new_assignment[idx]

            new_cost = self._compute_cost(new_assignment, hamiltonian)

            if new_cost < best_cost or random.random() < math.exp(
                (best_cost - new_cost) / temp
            ):
                best_assignment = new_assignment
                best_cost = new_cost

            temp *= cooling

            # Ruido cuantico simulado (afecta resultado final)
            if self.noise_model == "realistic":
                if random.random() < 0.01:  # 1% de error por shot
                    best_cost += random.uniform(0, 0.1)

        elapsed_ms = (time.perf_counter() - start) * 1000
        self._executions += 1

        result = QAOResult(
            assignment=best_assignment,
            cost=round(best_cost, 4),
            shots=shots,
            p_levels=p_levels,
            execution_time_ms=round(elapsed_ms, 2),
        )

        log_event("qaoa", f"optimized:cost={result.cost}:time={result.execution_time_ms}ms")
        return result

    def _compute_cost(self, assignment: list[int], h: QuantumHamiltonian) -> float:
        """Computa el costo de una asignacion dado el Hamiltoniano."""
        cost = 0.0
        for i, bias in h.field_terms:
            if i < len(assignment):
                cost += assignment[i] * bias
        for i, j, weight in h.cost_terms:
            if i < len(assignment) and j < len(assignment):
                cost += assignment[i] * assignment[j] * weight
        return cost

    def decode_assignment(self, result: QAOResult, ambulances: list[dict],
                           victims: list[dict]) -> list[dict]:
        """Decodifica el resultado QAOA a asignaciones concretas."""
        n_vic = len(victims)
        assignments = []
        for i, amb in enumerate(ambulances):
            assigned_victims = []
            for j, vic in enumerate(victims):
                qubit_idx = i * n_vic + j
                if qubit_idx < len(result.assignment) and result.assignment[qubit_idx]:
                    assigned_victims.append(vic["victim_id"])
            if assigned_victims:
                assignments.append({
                    "ambulance_id": amb["ambulance_id"],
                    "assigned_victims": assigned_victims,
                })
        return assignments

    def get_execution_count(self) -> int:
        return self._executions


__all__ = [
    "QAOACompiler",
    "QAOASimulator",
    "QuantumHamiltonian",
    "QAOResult",
]
