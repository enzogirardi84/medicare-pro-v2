import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

import '../l10n/app_strings.dart';
import '../models/triage_symptom.dart';
import '../utils/url_utils.dart';

class AlertaPacienteResult {
  const AlertaPacienteResult._({required this.ok, this.message});

  final bool ok;
  final String? message;

  factory AlertaPacienteResult.success() => const AlertaPacienteResult._(ok: true);
  factory AlertaPacienteResult.fail(String m) => AlertaPacienteResult._(ok: false, message: m);
}

/// POST a Edge Function `submit-alerta-paciente` → tabla `alertas_pacientes`.
class AlertaPacienteEdgeService {
  AlertaPacienteEdgeService({
    required this.projectUrl,
    required this.anonKey,
    required this.ingestSecret,
  });

  final String projectUrl;
  final String anonKey;
  final String ingestSecret;

  static Uri functionUri(String projectUrl) {
    final b = projectUrl.trim().replaceAll(RegExp(r'/+$'), '');
    return Uri.parse('$b/functions/v1/submit-alerta-paciente');
  }

  Future<AlertaPacienteResult> enviar({
    required String pacienteId,
    required String sintomaLabel,
    required TriageNivel nivel,
    required String empresaClave,
    double? latitud,
    double? longitud,
    double? precisionM,
  }) async {
    final base = normalizeApiBaseUrl(projectUrl.trim()) ?? projectUrl.trim();
    final uri = functionUri(base);
    final body = <String, dynamic>{
      'paciente_id': pacienteId,
      'sintoma': sintomaLabel,
      'nivel_urgencia': nivel.apiLabel,
      'empresa_clave': empresaClave,
      'fecha_hora': DateTime.now().toUtc().toIso8601String(),
      if (latitud != null) 'latitud': latitud,
      if (longitud != null) 'longitud': longitud,
      if (precisionM != null) 'precision_m': precisionM,
    };

    Future<http.Response> postOnce() {
      return http
          .post(
            uri,
            headers: {
              'Content-Type': 'application/json; charset=utf-8',
              'Accept': 'application/json',
              'Authorization': 'Bearer ${anonKey.trim()}',
              'X-Patient-Alert-Secret': ingestSecret.trim(),
            },
            body: jsonEncode(body),
          )
          .timeout(const Duration(seconds: 35));
    }

    Future<http.Response> postWithRetry() async {
      try {
        return await postOnce();
      } on SocketException catch (_) {
        await Future<void>.delayed(const Duration(milliseconds: 800));
        return postOnce();
      } on TimeoutException catch (_) {
        await Future<void>.delayed(const Duration(milliseconds: 800));
        return postOnce();
      }
    }

    try {
      final res = await postWithRetry();

      if (res.statusCode >= 200 && res.statusCode < 300) {
        return AlertaPacienteResult.success();
      }
      return AlertaPacienteResult.fail(_mensajeDesdeRespuesta(res));
    } catch (_) {
      return AlertaPacienteResult.fail(AppStrings.sinConexionOTimeout);
    }
  }

  static String _mensajeDesdeRespuesta(http.Response res) {
    final raw = res.body.trim();
    if (raw.isEmpty) {
      return AppStrings.servidorRespuestaVacia(res.statusCode);
    }
    try {
      final decoded = jsonDecode(raw);
      if (decoded is Map<String, dynamic>) {
        final err = decoded['error'];
        if (err is String && err.isNotEmpty) {
          return res.statusCode == 401
              ? AppStrings.noAutorizadoIngesta
              : AppStrings.errorHttpDetalle(res.statusCode, err);
        }
        final msg = decoded['message'];
        if (msg is String && msg.isNotEmpty) {
          return AppStrings.errorHttpDetalle(res.statusCode, msg);
        }
      }
    } catch (_) {
      /* cuerpo no JSON */
    }
    final corto = raw.length > 180 ? '${raw.substring(0, 180)}…' : raw;
    return AppStrings.errorHttpDetalle(res.statusCode, corto);
  }
}
