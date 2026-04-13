import 'package:flutter/material.dart';

/// Nivel de triage que recibe MediCare (tabla alertas_pacientes).
enum TriageNivel {
  rojo,
  amarillo,
  verde,
}

extension TriageNivelX on TriageNivel {
  /// Valor en base de datos / API.
  String get apiLabel {
    switch (this) {
      case TriageNivel.rojo:
        return 'Rojo';
      case TriageNivel.amarillo:
        return 'Amarillo';
      case TriageNivel.verde:
        return 'Verde';
    }
  }

  Color get color {
    switch (this) {
      case TriageNivel.rojo:
        return const Color(0xFFDC2626);
      case TriageNivel.amarillo:
        return const Color(0xFFEAB308);
      case TriageNivel.verde:
        return const Color(0xFF16A34A);
    }
  }

  String get tituloSeccion {
    switch (this) {
      case TriageNivel.rojo:
        return 'RIESGO DE VIDA';
      case TriageNivel.amarillo:
        return 'URGENCIA';
      case TriageNivel.verde:
        return 'CONSULTA';
    }
  }
}

class TriageSintoma {
  const TriageSintoma({
    required this.id,
    required this.label,
    required this.nivel,
    required this.icon,
  });

  final String id;
  final String label;
  final TriageNivel nivel;
  final IconData icon;
}

/// Lista clinica alineada al triage de MediCare PRO.
const List<TriageSintoma> kSintomasTriage = [
  // Rojo
  TriageSintoma(id: 'disnea', label: 'Dificultad respiratoria', nivel: TriageNivel.rojo, icon: Icons.air),
  TriageSintoma(id: 'dolor_pecho', label: 'Dolor de pecho', nivel: TriageNivel.rojo, icon: Icons.favorite_border),
  TriageSintoma(id: 'perdida_conciencia', label: 'Perdida de conocimiento', nivel: TriageNivel.rojo, icon: Icons.bedtime_outlined),
  TriageSintoma(id: 'convulsiones', label: 'Convulsiones', nivel: TriageNivel.rojo, icon: Icons.bolt),
  TriageSintoma(id: 'anafilaxia', label: 'Reaccion alergica grave', nivel: TriageNivel.rojo, icon: Icons.warning_amber_rounded),
  // Amarillo
  TriageSintoma(id: 'caida', label: 'Caida de su altura', nivel: TriageNivel.amarillo, icon: Icons.accessible_forward),
  TriageSintoma(id: 'herida_cortante', label: 'Herida cortante', nivel: TriageNivel.amarillo, icon: Icons.content_cut),
  TriageSintoma(id: 'desmayo_ok', label: 'Desmayo (recuperado)', nivel: TriageNivel.amarillo, icon: Icons.self_improvement),
  // Verde
  TriageSintoma(id: 'fiebre', label: 'Fiebre', nivel: TriageNivel.verde, icon: Icons.thermostat_outlined),
  TriageSintoma(id: 'vomitos', label: 'Vomitos / nauseas', nivel: TriageNivel.verde, icon: Icons.sick_outlined),
  TriageSintoma(id: 'dolor_general', label: 'Dolor generalizado', nivel: TriageNivel.verde, icon: Icons.healing_outlined),
  TriageSintoma(id: 'debilidad', label: 'Debilidad generalizada', nivel: TriageNivel.verde, icon: Icons.accessibility_new),
];
