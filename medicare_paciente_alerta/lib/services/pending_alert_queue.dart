import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

/// Alertas que no se pudieron enviar: se reintentan desde el inicio con conexion.
abstract final class PendingAlertQueue {
  static const _key = 'pending_alerts_queue_v1';
  static const int maxItems = 15;

  static Future<List<Map<String, dynamic>>> leerTodos() async {
    final p = await SharedPreferences.getInstance();
    final raw = p.getString(_key);
    if (raw == null || raw.isEmpty) return [];
    try {
      final list = jsonDecode(raw);
      if (list is! List) return [];
      return list.map((e) => Map<String, dynamic>.from(e as Map)).toList();
    } catch (_) {
      return [];
    }
  }

  static Future<void> _guardar(List<Map<String, dynamic>> items) async {
    final p = await SharedPreferences.getInstance();
    if (items.isEmpty) {
      await p.remove(_key);
    } else {
      await p.setString(_key, jsonEncode(items));
    }
  }

  static Future<void> encolar({
    required String sintomaLabel,
    required String nivelUrgencia,
    double? latitud,
    double? longitud,
    double? precisionM,
  }) async {
    final list = await leerTodos();
    list.add({
      'sintoma': sintomaLabel,
      'nivel_urgencia': nivelUrgencia,
      'latitud': latitud,
      'longitud': longitud,
      'precision_m': precisionM,
      'enqueued_at': DateTime.now().toUtc().toIso8601String(),
    });
    while (list.length > maxItems) {
      list.removeAt(0);
    }
    await _guardar(list);
  }

  static Future<void> limpiar() async {
    await _guardar([]);
  }

  static Future<void> reemplazar(List<Map<String, dynamic>> items) async {
    await _guardar(items);
  }

  static Future<int> cantidad() async {
    return (await leerTodos()).length;
  }
}
