import 'package:flutter_test/flutter_test.dart';
import 'package:medicare_paciente_alerta/models/triage_symptom.dart';

void main() {
  group('triageNivelDesdeEtiquetaApi', () {
    test('mapea etiquetas conocidas', () {
      expect(triageNivelDesdeEtiquetaApi('Rojo'), TriageNivel.rojo);
      expect(triageNivelDesdeEtiquetaApi('Amarillo'), TriageNivel.amarillo);
      expect(triageNivelDesdeEtiquetaApi('Verde'), TriageNivel.verde);
    });

    test('null, vacio o desconocido cae en verde', () {
      expect(triageNivelDesdeEtiquetaApi(null), TriageNivel.verde);
      expect(triageNivelDesdeEtiquetaApi(''), TriageNivel.verde);
      expect(triageNivelDesdeEtiquetaApi('Otro'), TriageNivel.verde);
    });

    test('respeta trim', () {
      expect(triageNivelDesdeEtiquetaApi('  Rojo  '), TriageNivel.rojo);
    });
  });

  test('kSintomasPorNivel agrupa por nivel', () {
    expect(kSintomasPorNivel[TriageNivel.rojo]!.length, 5);
    expect(kSintomasPorNivel[TriageNivel.amarillo]!.length, 3);
    expect(kSintomasPorNivel[TriageNivel.verde]!.length, 5);
    expect(
      kSintomasPorNivel[TriageNivel.verde]!.map((s) => s.id).contains('otro'),
      isTrue,
    );
  });
}
