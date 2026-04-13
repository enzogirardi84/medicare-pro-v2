import 'package:flutter_test/flutter_test.dart';
import 'package:medicare_paciente_alerta/main.dart';

void main() {
  testWidgets('App arranca', (tester) async {
    await tester.pumpWidget(const MedicarePacienteAlertaApp());
    await tester.pump();
    expect(find.byType(MedicarePacienteAlertaApp), findsOneWidget);
  });
}
