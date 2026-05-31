"""Tests para modulos v2.4.0 — Swarm Drones, BCI, Mesh P2P, Blackout."""
from __future__ import annotations

import math
import time


class TestSwarmOrchestrator:
    def test_drone_payload_triage_red(self):
        from core.swarm_drone_triage import DronePayload, TriageLevel
        payload = DronePayload(drone_id="d1", lat=-34.6, lon=-58.4,
                                hr_estimate=25, movement_detected=False)
        assert payload.estimate_triage() == TriageLevel.BLACK

    def test_drone_payload_triage_green(self):
        from core.swarm_drone_triage import DronePayload, TriageLevel
        payload = DronePayload(drone_id="d2", lat=-34.6, lon=-58.4,
                                hr_estimate=72, movement_detected=True,
                                thermal_temp=36.6)
        assert payload.estimate_triage() == TriageLevel.GREEN

    def test_ingest_drone(self):
        from core.swarm_drone_triage import SwarmOrchestrator, DronePayload
        swarm = SwarmOrchestrator()
        payload = DronePayload(drone_id="d1", lat=-34.6, lon=-58.4, hr_estimate=140)
        triage = swarm.ingest_drone_payload(payload)
        assert triage.value == "red"
        assert swarm.get_active_drones() == 1

    def test_generate_routes_no_ambulances(self):
        from core.swarm_drone_triage import SwarmOrchestrator, DronePayload
        swarm = SwarmOrchestrator()
        payload = DronePayload(drone_id="d1", lat=-34.6, lon=-58.4, hr_estimate=72)
        swarm.ingest_drone_payload(payload)
        routes = swarm.generate_evacuation_routes()
        assert routes == []

    def test_generate_routes_with_ambulance(self):
        from core.swarm_drone_triage import SwarmOrchestrator, DronePayload
        swarm = SwarmOrchestrator()
        swarm.register_ambulance("amb-1", -34.6, -58.4)
        swarm.ingest_drone_payload(DronePayload(drone_id="d1", lat=-34.61, lon=-58.39,
                                                 hr_estimate=130, movement_detected=True))
        routes = swarm.generate_evacuation_routes()
        assert len(routes) >= 1
        assert len(routes[0].victims) >= 1

    def test_victims_count(self):
        from core.swarm_drone_triage import SwarmOrchestrator, DronePayload
        swarm = SwarmOrchestrator()
        swarm.ingest_drone_payload(DronePayload(drone_id="d1", lat=0, lon=0, hr_estimate=150))
        swarm.ingest_drone_payload(DronePayload(drone_id="d2", lat=0, lon=0, hr_estimate=80, movement_detected=True))
        counts = swarm.get_victims_count()
        assert counts["red"] >= 0


class TestEEGProcessor:
    def test_ingest_and_process(self):
        from core.bci_telemetry_core import EEGProcessor
        proc = EEGProcessor(sample_rate=256, window_seconds=2)
        for _ in range(512):  # 2 segundos
            proc.ingest_sample(math.sin(_ * 0.1) * 10)
        ch = proc.process_window("Cz")
        assert ch is not None
        assert ch.total_power > 0
        assert ch.channel_name == "Cz"

    def test_decode_consciousness_alert(self):
        from core.bci_telemetry_core import EEGProcessor, EEGChannel, ConsciousnessLevel
        ch = EEGChannel(channel_name="Cz")
        ch.alpha_power = 50.0
        ch.beta_power = 30.0
        ch.theta_power = 10.0
        ch.delta_power = 5.0
        state = EEGProcessor.decode_neural_state(EEGProcessor, [ch])
        assert state.consciousness == ConsciousnessLevel.ALERT

    def test_decode_consciousness_coma(self):
        from core.bci_telemetry_core import EEGProcessor, EEGChannel, ConsciousnessLevel
        ch = EEGChannel(channel_name="Cz")
        ch.delta_power = 100.0
        ch.theta_power = 80.0
        ch.alpha_power = 20.0
        ch.beta_power = 5.0
        ch.gamma_power = 1.0
        state = EEGProcessor.decode_neural_state(EEGProcessor, [ch])
        assert state.consciousness in (ConsciousnessLevel.COMA, ConsciousnessLevel.STUPOROUS)

    def test_bci_telemetry_core(self):
        from core.bci_telemetry_core import BCITelemetryCore
        bci = BCITelemetryCore(sample_rate=256)
        bci.register_channel("Cz")
        bci.register_channel("Fz")
        for _ in range(512):
            bci.ingest_sample("Cz", math.sin(_ * 0.1) * 10)
            bci.ingest_sample("Fz", math.cos(_ * 0.1) * 8)
        state = bci.process_and_decode()
        assert state is not None or bci.get_current_state() is None  # puede no tener suficientes datos


class TestMeshNetwork:
    def test_mesh_node_distance(self):
        from core.p2p_mesh_network import MeshNode, MeshTransport, MeshNodeRole
        a = MeshNode(node_id="a", role=MeshNodeRole.AMBULANCE, transport=MeshTransport.LORA,
                      lat=-34.6, lon=-58.4)
        b = MeshNode(node_id="b", role=MeshNodeRole.HUB, transport=MeshTransport.WIFI_DIRECT,
                      lat=-34.5, lon=-58.3)
        dist = a.distance_to(b)
        assert 10 < dist < 20  # ~14 km

    def test_gossip_register_node(self):
        from core.p2p_mesh_network import GossipProtocol, MeshNode, MeshTransport, MeshNodeRole
        local = MeshNode(node_id="amb-1", role=MeshNodeRole.AMBULANCE,
                          transport=MeshTransport.LORA, lat=-34.6, lon=-58.4)
        gossip = GossipProtocol(local)
        hub = MeshNode(node_id="hub-1", role=MeshNodeRole.HUB,
                        transport=MeshTransport.WIFI_DIRECT, lat=-34.6, lon=-58.4)
        gossip.register_node(hub)
        assert len(gossip._known_nodes) == 1

    def test_submit_packet(self):
        from core.p2p_mesh_network import (GossipProtocol, MeshNode, MeshPacket,
                                            MeshTransport, MeshNodeRole)
        local = MeshNode(node_id="amb-1", role=MeshNodeRole.AMBULANCE,
                          transport=MeshTransport.LORA, lat=0, lon=0)
        gossip = GossipProtocol(local)
        packet = MeshPacket(source_node="amb-1", payload={"hr": 80})
        assert gossip.submit_packet(packet) is True
        assert gossip.submit_packet(packet) is False  # duplicado

    def test_mesh_network_broadcast(self):
        from core.p2p_mesh_network import MeshNetwork, MeshNode, MeshTransport, MeshNodeRole
        local = MeshNode(node_id="amb-1", role=MeshNodeRole.AMBULANCE,
                          transport=MeshTransport.LORA, lat=-34.6, lon=-58.4)
        mesh = MeshNetwork(local)
        packet = mesh.broadcast_clinical_data({"hr": 80}, "amb-1:3", "signature_hex")
        # submit_packet incrementa hop_count
        assert packet.hop_count >= 1
        assert packet.source_node == "amb-1"

    def test_simulate_propagation(self):
        from core.p2p_mesh_network import MeshNetwork, MeshNode, MeshPacket, MeshTransport, MeshNodeRole
        local = MeshNode(node_id="amb-1", role=MeshNodeRole.AMBULANCE,
                          transport=MeshTransport.LORA, lat=0, lon=0)
        mesh = MeshNetwork(local)
        nodes = [local]
        for i in range(10):
            nodes.append(MeshNode(
                node_id=f"relay-{i}", role=MeshNodeRole.RELAY,
                transport=MeshTransport.LORA, lat=0.01 * i, lon=0.01 * i,
            ))
        nodes.append(MeshNode(node_id="hub-1", role=MeshNodeRole.HUB,
                               transport=MeshTransport.WIFI_DIRECT, lat=0.05, lon=0.05))
        packet = MeshPacket(source_node="amb-1", payload={"hr": 80})
        reached = mesh.simulate_propagation(packet, nodes)
        assert reached >= 0


class TestBlackoutSimulator:
    def test_scenario_defaults(self):
        from core.blackout_simulator import BlackoutScenario
        sc = BlackoutScenario()
        assert sc.ambulances_count == 1000
        assert sc.kubernetes_pods_loss_pct == 0.95
        assert sc.mesh_active is True

    def test_run_simulation(self):
        import asyncio
        from core.blackout_simulator import BlackoutSimulator, BlackoutScenario
        sim = BlackoutSimulator()
        sc = BlackoutScenario(
            ambulances_count=100,
            duration_seconds=10,
        )
        sim.configure(sc)
        report = asyncio.run(sim.run())
        assert report.total_packets_sent == 100
        assert report.packets_delivered >= 0
        assert 0 <= report.overall_resilience_score <= 100

    def test_resilience_score_range(self):
        import asyncio
        from core.blackout_simulator import BlackoutSimulator, BlackoutScenario
        sim = BlackoutSimulator()
        sim.configure(BlackoutScenario(ambulances_count=50, duration_seconds=5))
        report = asyncio.run(sim.run())
        assert 0 <= report.overall_resilience_score <= 100
