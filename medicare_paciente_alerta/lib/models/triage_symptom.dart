import 'package:flutter/material.dart';

import '../l10n/app_strings.dart';

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
        return AppStrings.triageSeccionRojo;
      case TriageNivel.amarillo:
        return AppStrings.triageSeccionAmarillo;
      case TriageNivel.verde:
        return AppStrings.triageSeccionVerde;
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

TriageNivel triageNivelDesdeEtiquetaApi(String? raw) {
  switch ((raw ?? '').trim()) {
    case 'Rojo':
      return TriageNivel.rojo;
    case 'Amarillo':
      return TriageNivel.amarillo;
    default:
      return TriageNivel.verde;
  }
}

/// Lista clinica alineada al triage de MediCare PRO.
const List<TriageSintoma> kSintomasTriage = [
  // Rojo
  TriageSintoma(id: 'disnea', label: AppStrings.sintomaDisnea, nivel: TriageNivel.rojo, icon: Icons.air),
  TriageSintoma(id: 'dolor_pecho', label: AppStrings.sintomaDolorPecho, nivel: TriageNivel.rojo, icon: Icons.favorite_border),
  TriageSintoma(id: 'perdida_conciencia', label: AppStrings.sintomaPerdidaConciencia, nivel: TriageNivel.rojo, icon: Icons.bedtime_outlined),
  TriageSintoma(id: 'convulsiones', label: AppStrings.sintomaConvulsiones, nivel: TriageNivel.rojo, icon: Icons.bolt),
  TriageSintoma(id: 'anafilaxia', label: AppStrings.sintomaAnafilaxia, nivel: TriageNivel.rojo, icon: Icons.warning_amber_rounded),
  // Amarillo
  TriageSintoma(id: 'caida', label: AppStrings.sintomaCaida, nivel: TriageNivel.amarillo, icon: Icons.accessible_forward),
  TriageSintoma(id: 'herida_cortante', label: AppStrings.sintomaHeridaCortante, nivel: TriageNivel.amarillo, icon: Icons.content_cut),
  TriageSintoma(id: 'desmayo_ok', label: AppStrings.sintomaDesmayoOk, nivel: TriageNivel.amarillo, icon: Icons.self_improvement),
  // Verde
  TriageSintoma(id: 'fiebre', label: AppStrings.sintomaFiebre, nivel: TriageNivel.verde, icon: Icons.thermostat_outlined),
  TriageSintoma(id: 'vomitos', label: AppStrings.sintomaVomitos, nivel: TriageNivel.verde, icon: Icons.sick_outlined),
  TriageSintoma(id: 'dolor_general', label: AppStrings.sintomaDolorGeneral, nivel: TriageNivel.verde, icon: Icons.healing_outlined),
  TriageSintoma(id: 'debilidad', label: AppStrings.sintomaDebilidad, nivel: TriageNivel.verde, icon: Icons.accessibility_new),
  TriageSintoma(id: 'otro', label: AppStrings.otroSintoma, nivel: TriageNivel.verde, icon: Icons.more_horiz),
];

/// Por nivel; se arma una sola vez al primer uso (evita `.where` en cada frame del grid).
final Map<TriageNivel, List<TriageSintoma>> kSintomasPorNivel = {
  for (final n in TriageNivel.values)
    n: kSintomasTriage.where((s) => s.nivel == n).toList(growable: false),
};
