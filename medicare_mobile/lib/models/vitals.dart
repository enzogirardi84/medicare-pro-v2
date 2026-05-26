class Vitals {
  final String id;
  final String pacienteId;
  final double? temperatura;
  final int? frecuenciaCardiaca;
  final int? presionSistolica;
  final int? presionDiastolica;
  final int? saturacionO2;
  final double? peso;
  final double? altura;
  final String fechaHora;
  final String registradoPor;

  Vitals({
    required this.id,
    required this.pacienteId,
    this.temperatura,
    this.frecuenciaCardiaca,
    this.presionSistolica,
    this.presionDiastolica,
    this.saturacionO2,
    this.peso,
    this.altura,
    required this.fechaHora,
    required this.registradoPor,
  });

  factory Vitals.fromJson(Map<String, dynamic> json) {
    return Vitals(
      id: json['id'] as String,
      pacienteId: json['paciente_id'] as String,
      temperatura: (json['temperatura'] as num?)?.toDouble(),
      frecuenciaCardiaca: json['frecuencia_cardiaca'] as int?,
      presionSistolica: json['presion_sistolica'] as int?,
      presionDiastolica: json['presion_diastolica'] as int?,
      saturacionO2: json['saturacion_o2'] as int?,
      peso: (json['peso'] as num?)?.toDouble(),
      altura: (json['altura'] as num?)?.toDouble(),
      fechaHora: json['fecha_hora'] as String,
      registradoPor: json['registrado_por'] as String,
    );
  }
}

class VitalsCreate {
  final String pacienteId;
  final double? temperatura;
  final int? frecuenciaCardiaca;
  final int? presionSistolica;
  final int? presionDiastolica;
  final int? saturacionO2;
  final double? peso;
  final double? altura;

  VitalsCreate({
    required this.pacienteId,
    this.temperatura,
    this.frecuenciaCardiaca,
    this.presionSistolica,
    this.presionDiastolica,
    this.saturacionO2,
    this.peso,
    this.altura,
  });

  Map<String, dynamic> toJson() => {
    'paciente_id': pacienteId,
    'temperatura': temperatura,
    'frecuencia_cardiaca': frecuenciaCardiaca,
    'presion_sistolica': presionSistolica,
    'presion_diastolica': presionDiastolica,
    'saturacion_o2': saturacionO2,
    'peso': peso,
    'altura': altura,
  };
}
