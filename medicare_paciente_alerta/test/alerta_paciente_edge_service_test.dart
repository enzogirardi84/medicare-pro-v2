import 'package:flutter_test/flutter_test.dart';
import 'package:medicare_paciente_alerta/services/alerta_paciente_edge_service.dart';

void main() {
  group('AlertaPacienteEdgeService.functionUri', () {
    test('anexa functions/v1/submit-alerta-paciente', () {
      final u = AlertaPacienteEdgeService.functionUri('https://abc.supabase.co');
      expect(u.toString(), 'https://abc.supabase.co/functions/v1/submit-alerta-paciente');
    });

    test('quita barras finales del proyecto', () {
      final u = AlertaPacienteEdgeService.functionUri('https://abc.supabase.co///');
      expect(u.toString(), 'https://abc.supabase.co/functions/v1/submit-alerta-paciente');
    });

    test('respeta trim', () {
      final u = AlertaPacienteEdgeService.functionUri('  https://x.supabase.co  ');
      expect(u.toString(), 'https://x.supabase.co/functions/v1/submit-alerta-paciente');
    });
  });
}
