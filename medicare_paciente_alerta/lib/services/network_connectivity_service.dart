import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/material.dart';

import '../l10n/app_strings.dart';

/// Comprueba wifi/datos antes del flujo de alerta (no garantiza salida a Internet).
class NetworkConnectivityService {
  NetworkConnectivityService._();

  static Future<bool> hasUsableNetwork() async {
    final results = await Connectivity().checkConnectivity();
    if (results.isEmpty) return true;
    return results.any((r) => r != ConnectivityResult.none);
  }

  /// Si no hay red, muestra aviso y devuelve false.
  static Future<bool> ensureBeforeAlert(BuildContext context) async {
    final ok = await hasUsableNetwork();
    if (!context.mounted) return false;
    if (ok) return true;

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: const Text(AppStrings.sinRed),
        backgroundColor: Colors.deepOrange.shade800,
        behavior: SnackBarBehavior.floating,
        duration: const Duration(seconds: 6),
        action: SnackBarAction(
          label: AppStrings.ok,
          textColor: Colors.white,
          onPressed: () {
            ScaffoldMessenger.of(context).hideCurrentSnackBar();
          },
        ),
      ),
    );
    return false;
  }
}
