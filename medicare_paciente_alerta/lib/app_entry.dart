import 'package:flutter/material.dart';

import 'config/app_settings.dart';
import 'screens/emergency_settings_screen.dart';
import 'screens/need_help_home_screen.dart';

/// Arranque: si falta config muestra ajustes; si no, boton NECESITO AYUDA.
class AppEntry extends StatefulWidget {
  const AppEntry({super.key});

  @override
  State<AppEntry> createState() => _AppEntryState();
}

class _AppEntryState extends State<AppEntry> {
  late Future<bool> _cfgFuture;

  @override
  void initState() {
    super.initState();
    _cfgFuture = AppSettings.hasTriageConfig();
  }

  void _reloadConfig() {
    setState(() {
      _cfgFuture = AppSettings.hasTriageConfig();
    });
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<bool>(
      future: _cfgFuture,
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) {
          return const Scaffold(
            body: Center(child: CircularProgressIndicator()),
          );
        }
        if (snap.data != true) {
          return EmergencySettingsScreen(onSaved: _reloadConfig);
        }
        return NeedHelpHomeScreen(
          onOpenSettings: () async {
            _reloadConfig();
          },
        );
      },
    );
  }
}
