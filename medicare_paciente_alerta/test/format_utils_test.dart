import 'package:flutter_test/flutter_test.dart';
import 'package:medicare_paciente_alerta/utils/format_utils.dart';

void main() {
  group('formatearFechaHoraLocal', () {
    test('null o vacio', () {
      expect(formatearFechaHoraLocal(null), '');
      expect(formatearFechaHoraLocal(''), '');
      expect(formatearFechaHoraLocal('   '), '');
    });

    test('ISO UTC se muestra en local (formato dd/mm/yyyy hh:mm)', () {
      final s = formatearFechaHoraLocal('2026-04-10T15:30:00.000Z');
      expect(s, isNotEmpty);
      expect(s, contains('2026'));
      expect(s, contains(':'));
    });

    test('texto no parseable se devuelve recortado', () {
      expect(formatearFechaHoraLocal('sin-fecha'), 'sin-fecha');
    });
  });
}
