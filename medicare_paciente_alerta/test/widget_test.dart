import 'package:flutter_test/flutter_test.dart';
import 'package:medicare_paciente_alerta/l10n/app_strings.dart';
import 'package:medicare_paciente_alerta/main.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  setUpAll(() {
    PackageInfo.setMockInitialValues(
      appName: 'Medicare paciente test',
      packageName: 'medicare_paciente_alerta',
      version: '0.1.12',
      buildNumber: '13',
      buildSignature: '',
      installerStore: null,
    );
  });

  testWidgets('App arranca', (tester) async {
    SharedPreferences.setMockInitialValues({});
    await tester.pumpWidget(const MedicarePacienteAlertaApp());
    await tester.pump();
    expect(find.byType(MedicarePacienteAlertaApp), findsOneWidget);
  });

  testWidgets('sin config llega a pantalla de ajustes', (tester) async {
    SharedPreferences.setMockInitialValues({});
    await tester.pumpWidget(const MedicarePacienteAlertaApp());
    await tester.pumpAndSettle();
    expect(find.text(AppStrings.configuracion), findsOneWidget);
    expect(
      find.byWidgetPredicate(
        (w) =>
            w is Text &&
            w.data != null &&
            RegExp(r'^Version \d[\d\.]*\+\d+\s*$').hasMatch(w.data!),
      ),
      findsOneWidget,
    );
  });

  testWidgets('con config triage muestra inicio MediCare', (tester) async {
    SharedPreferences.setMockInitialValues({
      'supabase_project_url': 'https://abc.supabase.co',
      'supabase_anon_key': 'x' * 24,
      'patient_alert_ingest_secret': 'sec',
      'empresa_clave': 'clinica',
      'patient_token': '12345',
    });
    await tester.pumpWidget(const MedicarePacienteAlertaApp());
    await tester.pumpAndSettle();
    expect(find.text(AppStrings.medicare), findsOneWidget);
  });
}
