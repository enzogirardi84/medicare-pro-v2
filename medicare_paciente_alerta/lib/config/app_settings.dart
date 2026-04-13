import 'package:shared_preferences/shared_preferences.dart';

/// Claves de configuracion local (sin secretos fuertes: el token es identificador de paciente en tu API).
class AppSettings {
  static const _kBaseUrl = 'api_base_url';
  static const _kPatientToken = 'patient_token';
  static const _kPatientName = 'patient_name';
  static const _kLastAlertAt = 'last_alert_at_iso';
  static const _kLastAlertSummary = 'last_alert_summary';
  static const _kEmergencyPhone = 'emergency_phone';
  static const _kDeliveryMode = 'delivery_mode';
  static const _kSupabaseUrl = 'supabase_project_url';
  static const _kSupabaseAnon = 'supabase_anon_key';
  static const _kIngestSecret = 'patient_alert_ingest_secret';
  static const _kEmpresaClave = 'empresa_clave';
  static const _kLargeText = 'large_text';
  static const _kCountdownSec = 'countdown_seconds';
  static const _kHighContrast = 'high_contrast';

  /// `api` = POST a tu servidor; `supabase` = Edge Function MediCare.
  static Future<String> getDeliveryMode() async {
    final p = await SharedPreferences.getInstance();
    final m = p.getString(_kDeliveryMode)?.trim().toLowerCase();
    if (m == 'supabase') return 'supabase';
    return 'api';
  }

  static Future<void> setDeliveryMode(String value) async {
    final p = await SharedPreferences.getInstance();
    final v = value.trim().toLowerCase();
    await p.setString(_kDeliveryMode, v == 'supabase' ? 'supabase' : 'api');
  }

  static Future<String?> getSupabaseProjectUrl() async {
    final p = await SharedPreferences.getInstance();
    return p.getString(_kSupabaseUrl);
  }

  static Future<void> setSupabaseProjectUrl(String value) async {
    final p = await SharedPreferences.getInstance();
    final v = value.trim();
    if (v.isEmpty) {
      await p.remove(_kSupabaseUrl);
    } else {
      await p.setString(_kSupabaseUrl, v.replaceAll(RegExp(r'/+$'), ''));
    }
  }

  static Future<String?> getSupabaseAnonKey() async {
    final p = await SharedPreferences.getInstance();
    return p.getString(_kSupabaseAnon);
  }

  static Future<void> setSupabaseAnonKey(String value) async {
    final p = await SharedPreferences.getInstance();
    final v = value.trim();
    if (v.isEmpty) {
      await p.remove(_kSupabaseAnon);
    } else {
      await p.setString(_kSupabaseAnon, v);
    }
  }

  static Future<String?> getIngestSecret() async {
    final p = await SharedPreferences.getInstance();
    return p.getString(_kIngestSecret);
  }

  static Future<void> setIngestSecret(String value) async {
    final p = await SharedPreferences.getInstance();
    final v = value.trim();
    if (v.isEmpty) {
      await p.remove(_kIngestSecret);
    } else {
      await p.setString(_kIngestSecret, v);
    }
  }

  static Future<String?> getEmpresaClave() async {
    final p = await SharedPreferences.getInstance();
    return p.getString(_kEmpresaClave);
  }

  static Future<void> setEmpresaClave(String value) async {
    final p = await SharedPreferences.getInstance();
    final v = value.trim().toLowerCase();
    if (v.isEmpty) {
      await p.remove(_kEmpresaClave);
    } else {
      await p.setString(_kEmpresaClave, v);
    }
  }

  static Future<String?> getBaseUrl() async {
    final p = await SharedPreferences.getInstance();
    return p.getString(_kBaseUrl);
  }

  static Future<void> setBaseUrl(String value) async {
    final p = await SharedPreferences.getInstance();
    final v = value.trim();
    if (v.isEmpty) {
      await p.remove(_kBaseUrl);
    } else {
      await p.setString(_kBaseUrl, v.endsWith('/') ? v.substring(0, v.length - 1) : v);
    }
  }

  static Future<String?> getPatientToken() async {
    final p = await SharedPreferences.getInstance();
    return p.getString(_kPatientToken);
  }

  static Future<void> setPatientToken(String value) async {
    final p = await SharedPreferences.getInstance();
    final v = value.trim();
    if (v.isEmpty) {
      await p.remove(_kPatientToken);
    } else {
      await p.setString(_kPatientToken, v);
    }
  }

  static Future<String?> getPatientName() async {
    final p = await SharedPreferences.getInstance();
    return p.getString(_kPatientName);
  }

  static Future<void> setPatientName(String value) async {
    final p = await SharedPreferences.getInstance();
    final v = value.trim();
    if (v.isEmpty) {
      await p.remove(_kPatientName);
    } else {
      await p.setString(_kPatientName, v);
    }
  }

  static Future<String?> getLastAlertAtIso() async {
    final p = await SharedPreferences.getInstance();
    return p.getString(_kLastAlertAt);
  }

  static Future<String?> getLastAlertSummary() async {
    final p = await SharedPreferences.getInstance();
    return p.getString(_kLastAlertSummary);
  }

  static Future<void> setLastAlertSent({required String atIso, required String summary}) async {
    final p = await SharedPreferences.getInstance();
    await p.setString(_kLastAlertAt, atIso);
    await p.setString(_kLastAlertSummary, summary);
  }

  /// Numero corto de emergencias (Argentina 107 / 911 segun zona). Solo digitos y + al inicio.
  static Future<String> getEmergencyPhone() async {
    final p = await SharedPreferences.getInstance();
    final s = p.getString(_kEmergencyPhone)?.trim();
    if (s == null || s.isEmpty) return '107';
    return s;
  }

  static Future<void> setEmergencyPhone(String value) async {
    final p = await SharedPreferences.getInstance();
    final v = value.trim();
    if (v.isEmpty) {
      await p.remove(_kEmergencyPhone);
    } else {
      await p.setString(_kEmergencyPhone, v);
    }
  }

  static Future<bool> getLargeText() async {
    final p = await SharedPreferences.getInstance();
    return p.getBool(_kLargeText) ?? false;
  }

  static Future<void> setLargeText(bool value) async {
    final p = await SharedPreferences.getInstance();
    if (value) {
      await p.setBool(_kLargeText, true);
    } else {
      await p.remove(_kLargeText);
    }
  }

  /// Factor para [MediaQuery.textScaler] (lectura comoda en adultos mayores).
  static Future<double> getTextScaleFactor() async {
    return (await getLargeText()) ? 1.22 : 1.0;
  }

  /// Segundos de cuenta regresiva antes de enviar (2-8).
  static Future<int> getCountdownSeconds() async {
    final p = await SharedPreferences.getInstance();
    final v = p.getInt(_kCountdownSec);
    if (v == null) {
      return 3;
    }
    return v.clamp(2, 8);
  }

  static Future<void> setCountdownSeconds(int value) async {
    final p = await SharedPreferences.getInstance();
    await p.setInt(_kCountdownSec, value.clamp(2, 8));
  }

  static Future<bool> getHighContrast() async {
    final p = await SharedPreferences.getInstance();
    return p.getBool(_kHighContrast) ?? false;
  }

  static Future<void> setHighContrast(bool value) async {
    final p = await SharedPreferences.getInstance();
    if (value) {
      await p.setBool(_kHighContrast, true);
    } else {
      await p.remove(_kHighContrast);
    }
  }

  /// True si puede enviar alertas triage (Supabase Edge Function submit-alerta-paciente).
  static Future<bool> hasTriageConfig() async {
    final url = (await getSupabaseProjectUrl())?.trim() ?? '';
    final anon = (await getSupabaseAnonKey())?.trim() ?? '';
    final sec = (await getIngestSecret())?.trim() ?? '';
    final emp = (await getEmpresaClave())?.trim() ?? '';
    final pid = (await getPatientToken())?.trim() ?? '';
    return url.isNotEmpty &&
        anon.isNotEmpty &&
        sec.isNotEmpty &&
        emp.isNotEmpty &&
        pid.isNotEmpty;
  }
}
