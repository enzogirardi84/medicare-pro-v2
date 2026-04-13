import 'package:flutter_test/flutter_test.dart';
import 'package:medicare_paciente_alerta/config/app_settings.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  group('getCountdownSeconds / setCountdownSeconds', () {
    test('por defecto 3 segundos', () async {
      expect(await AppSettings.getCountdownSeconds(), 3);
    });

    test('acota entre 2 y 8', () async {
      await AppSettings.setCountdownSeconds(99);
      expect(await AppSettings.getCountdownSeconds(), 8);
      await AppSettings.setCountdownSeconds(1);
      expect(await AppSettings.getCountdownSeconds(), 2);
      await AppSettings.setCountdownSeconds(5);
      expect(await AppSettings.getCountdownSeconds(), 5);
    });
  });

  group('countdown en prefs fuera de rango', () {
    setUp(() {
      SharedPreferences.setMockInitialValues({'countdown_seconds': 50});
    });

    test('getCountdownSeconds acota al leer', () async {
      expect(await AppSettings.getCountdownSeconds(), 8);
    });
  });

  group('hasTriageConfig', () {
    test('false sin datos', () async {
      expect(await AppSettings.hasTriageConfig(), isFalse);
    });

    test('true con todos los campos obligatorios', () async {
      await AppSettings.setSupabaseProjectUrl('https://abc.supabase.co');
      await AppSettings.setSupabaseAnonKey('x' * 24);
      await AppSettings.setIngestSecret('secreto');
      await AppSettings.setEmpresaClave('clinica demo');
      await AppSettings.setPatientToken('12345');
      expect(await AppSettings.hasTriageConfig(), isTrue);
    });
  });

  test('setEmpresaClave guarda en minusculas', () async {
    await AppSettings.setEmpresaClave('  Clinica Norte  ');
    expect(await AppSettings.getEmpresaClave(), 'clinica norte');
  });

  test('setSupabaseProjectUrl quita barras finales', () async {
    await AppSettings.setSupabaseProjectUrl('https://x.supabase.co///');
    expect(await AppSettings.getSupabaseProjectUrl(), 'https://x.supabase.co');
  });

  test('getEmergencyPhone por defecto 107', () async {
    expect(await AppSettings.getEmergencyPhone(), '107');
  });

  group('alto contraste y texto grande', () {
    test('getHighContrast false por defecto', () async {
      expect(await AppSettings.getHighContrast(), isFalse);
    });

    test('setHighContrast persiste', () async {
      await AppSettings.setHighContrast(true);
      expect(await AppSettings.getHighContrast(), isTrue);
      await AppSettings.setHighContrast(false);
      expect(await AppSettings.getHighContrast(), isFalse);
    });

    test('getTextScaleFactor segun texto grande', () async {
      expect(await AppSettings.getTextScaleFactor(), 1.0);
      await AppSettings.setLargeText(true);
      expect(await AppSettings.getTextScaleFactor(), 1.22);
    });
  });
}
