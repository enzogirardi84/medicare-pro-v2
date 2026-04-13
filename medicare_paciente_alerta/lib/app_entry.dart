import 'package:flutter/material.dart';

import 'config/app_settings.dart';
import 'l10n/app_strings.dart';
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
          return const _ArranqueCargando();
        }
        if (snap.hasError) {
          return Scaffold(
            body: SafeArea(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(Icons.error_outline, size: 48, color: Colors.red.shade300),
                    const SizedBox(height: 16),
                    Text(
                      AppStrings.configErrorTitulo,
                      textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 8),
                    Text(
                      '${snap.error}',
                      textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Colors.white54),
                    ),
                    const SizedBox(height: 24),
                    FilledButton(
                      onPressed: _reloadConfig,
                      child: const Text(AppStrings.reintentar),
                    ),
                  ],
                ),
              ),
            ),
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

class _ArranqueCargando extends StatelessWidget {
  const _ArranqueCargando();

  @override
  Widget build(BuildContext context) {
    final tt = Theme.of(context).textTheme;
    return Scaffold(
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.medical_services_rounded,
              size: 56,
              color: Theme.of(context).colorScheme.primary,
            ),
            const SizedBox(height: 20),
            const SizedBox(
              width: 36,
              height: 36,
              child: CircularProgressIndicator(strokeWidth: 3),
            ),
            const SizedBox(height: 20),
            Text(AppStrings.appTitle, style: tt.titleLarge?.copyWith(fontWeight: FontWeight.w800)),
            const SizedBox(height: 6),
            Text(AppStrings.cargando, style: tt.bodyMedium?.copyWith(color: Colors.white54)),
          ],
        ),
      ),
    );
  }
}
