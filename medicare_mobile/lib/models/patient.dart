class Patient {
  final String id;
  final String dni;
  final String nombre;
  final String apellido;
  final String fechaNacimiento;
  final String? email;
  final String? telefono;
  final String? obraSocial;
  final String? sexo;
  final String estado;
  final String creadoEn;
  final String? actualizadoEn;

  Patient({
    required this.id,
    required this.dni,
    required this.nombre,
    required this.apellido,
    required this.fechaNacimiento,
    this.email,
    this.telefono,
    this.obraSocial,
    this.sexo,
    this.estado = 'activo',
    required this.creadoEn,
    this.actualizadoEn,
  });

  factory Patient.fromJson(Map<String, dynamic> json) {
    return Patient(
      id: json['id'] as String,
      dni: json['dni'] as String,
      nombre: json['nombre'] as String,
      apellido: json['apellido'] as String,
      fechaNacimiento: json['fecha_nacimiento'] as String,
      email: json['email'] as String?,
      telefono: json['telefono'] as String?,
      obraSocial: json['obra_social'] as String?,
      sexo: json['sexo'] as String?,
      estado: json['estado'] as String? ?? 'activo',
      creadoEn: json['creado_en'] as String,
      actualizadoEn: json['actualizado_en'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
    'dni': dni,
    'nombre': nombre,
    'apellido': apellido,
    'fecha_nacimiento': fechaNacimiento,
    'email': email,
    'telefono': telefono,
    'obra_social': obraSocial,
    'sexo': sexo,
  };

  String get nombreCompleto => '$nombre $apellido';
}

class PatientCreate {
  final String dni;
  final String nombre;
  final String apellido;
  final String fechaNacimiento;
  final String? email;
  final String? telefono;
  final String? obraSocial;
  final String? sexo;

  PatientCreate({
    required this.dni,
    required this.nombre,
    required this.apellido,
    required this.fechaNacimiento,
    this.email,
    this.telefono,
    this.obraSocial,
    this.sexo,
  });

  Map<String, dynamic> toJson() => {
    'dni': dni,
    'nombre': nombre,
    'apellido': apellido,
    'fecha_nacimiento': fechaNacimiento,
    'email': email,
    'telefono': telefono,
    'obra_social': obraSocial,
    'sexo': sexo,
  };
}
