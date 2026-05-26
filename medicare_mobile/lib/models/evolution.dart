class Evolution {
  final String id;
  final String pacienteId;
  final String medicoId;
  final String fecha;
  final String motivoConsulta;
  final String diagnostico;
  final String? tratamiento;
  final String? examenFisico;
  final String? evolucion;
  final String creadoEn;

  Evolution({
    required this.id,
    required this.pacienteId,
    required this.medicoId,
    required this.fecha,
    required this.motivoConsulta,
    required this.diagnostico,
    this.tratamiento,
    this.examenFisico,
    this.evolucion,
    required this.creadoEn,
  });

  factory Evolution.fromJson(Map<String, dynamic> json) {
    return Evolution(
      id: json['id'] as String,
      pacienteId: json['paciente_id'] as String,
      medicoId: json['medico_id'] as String,
      fecha: json['fecha'] as String,
      motivoConsulta: json['motivo_consulta'] as String,
      diagnostico: json['diagnostico'] as String,
      tratamiento: json['tratamiento'] as String?,
      examenFisico: json['examen_fisico'] as String?,
      evolucion: json['evolucion'] as String?,
      creadoEn: json['creado_en'] as String,
    );
  }
}

class EvolutionCreate {
  final String pacienteId;
  final String motivoConsulta;
  final String diagnostico;
  final String? tratamiento;
  final String? examenFisico;
  final String? evolucion;

  EvolutionCreate({
    required this.pacienteId,
    required this.motivoConsulta,
    required this.diagnostico,
    this.tratamiento,
    this.examenFisico,
    this.evolucion,
  });

  Map<String, dynamic> toJson() => {
    'paciente_id': pacienteId,
    'motivo_consulta': motivoConsulta,
    'diagnostico': diagnostico,
    'tratamiento': tratamiento,
    'examen_fisico': examenFisico,
    'evolucion': evolucion,
  };
}
