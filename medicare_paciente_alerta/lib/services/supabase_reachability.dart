import 'dart:async';

import 'package:http/http.dart' as http;

import '../l10n/app_strings.dart';
import '../utils/url_utils.dart';

/// Comprueba que el proyecto Supabase sea alcanzable (sin validar el secreto de Edge Function).
class SupabaseReachability {
  SupabaseReachability._();

  /// Null = OK. String = mensaje de error para el usuario.
  static Future<String?> probarProyecto({
    required String urlRaw,
    String anonKey = '',
  }) async {
    final base = normalizeApiBaseUrl(urlRaw.trim());
    if (base == null || base.isEmpty) {
      return AppStrings.supabaseUrlInvalidaEjemplo;
    }

    final health = Uri.parse('$base/auth/v1/health');
    try {
      final h = await http.get(health).timeout(const Duration(seconds: 12));
      if (h.statusCode < 200 || h.statusCode >= 300) {
        return AppStrings.proyectoRespondioCodigo(h.statusCode);
      }
    } on TimeoutException {
      return AppStrings.tiempoAgotadoRed;
    } catch (_) {
      return AppStrings.noSePudoContactarServidor;
    }

    final a = anonKey.trim();
    if (a.length < 20) {
      return null;
    }

    final rest = Uri.parse('$base/rest/v1/');
    try {
      final r = await http
          .get(
            rest,
            headers: {
              'apikey': a,
              'Authorization': 'Bearer $a',
            },
          )
          .timeout(const Duration(seconds: 12));
      if (r.statusCode == 401 || r.statusCode == 403) {
        return AppStrings.claveAnonRechazada;
      }
      if (r.statusCode >= 500) {
        return AppStrings.apiRestErrorCodigo(r.statusCode);
      }
    } on TimeoutException {
      return AppStrings.tiempoAgotadoClaveAnon;
    } catch (_) {
      /* Health ya paso; fallo menor en REST no bloquea */
    }

    return null;
  }
}
