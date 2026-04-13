import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';

import '../config/app_settings.dart';
import '../services/network_connectivity_service.dart';
import 'emergency_settings_screen.dart';
import 'symptom_grid_screen.dart';

/// Pantalla 1: un solo boton gigante (a prueba de panico).
class NeedHelpHomeScreen extends StatelessWidget {
  const NeedHelpHomeScreen({super.key, required this.onOpenSettings});

  final Future<void> Function() onOpenSettings;

  Future<void> _llamarEmergencias() async {
    final phone = await AppSettings.getEmergencyPhone();
    var cleaned = phone.replaceAll(RegExp(r'[\s.-]'), '');
    if (cleaned.isEmpty) cleaned = '107';
    final uri = Uri.parse('tel:$cleaned');
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('MediCare'),
        centerTitle: true,
        actions: [
          IconButton(
            icon: const Icon(Icons.settings_outlined),
            tooltip: 'Configuracion',
            onPressed: () async {
              await Navigator.push<bool>(
                context,
                MaterialPageRoute(
                  fullscreenDialog: true,
                  builder: (_) => const EmergencySettingsScreen(),
                ),
              );
              await onOpenSettings();
            },
          ),
        ],
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20),
          child: Column(
            children: [
              const SizedBox(height: 12),
              Text(
                'Si necesitas ayuda clinica de tu equipo, toca el boton rojo.',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodyLarge?.copyWith(color: Colors.white70),
              ),
              const Spacer(),
              LayoutBuilder(
                builder: (ctx, c) {
                  final sz = (c.maxWidth * 0.88).clamp(220.0, 340.0);
                  return Center(
                    child: SizedBox(
                      width: sz,
                      height: sz,
                      child: Material(
                        color: const Color(0xFFB91C1C),
                        elevation: 12,
                        shadowColor: Colors.redAccent,
                        shape: const CircleBorder(),
                        child: Semantics(
                          button: true,
                          label: 'Necesito ayuda clinica de mi equipo',
                          hint: 'Abre la lista de sintomas para enviar una alerta',
                          child: InkWell(
                            customBorder: const CircleBorder(),
                            onTap: () async {
                              HapticFeedback.lightImpact();
                              final ok = await NetworkConnectivityService.ensureBeforeAlert(context);
                              if (!context.mounted) return;
                              if (!ok) return;
                              await Navigator.push<void>(
                                context,
                                MaterialPageRoute<void>(
                                  builder: (_) => const SymptomGridScreen(),
                                ),
                              );
                            },
                            child: const Center(
                              child: Padding(
                                padding: EdgeInsets.all(16),
                                child: Text(
                                  'NECESITO\nAYUDA',
                                  textAlign: TextAlign.center,
                                  style: TextStyle(
                                    color: Colors.white,
                                    fontSize: 28,
                                    fontWeight: FontWeight.w900,
                                    height: 1.05,
                                  ),
                                ),
                              ),
                            ),
                          ),
                        ),
                      ),
                    ),
                  );
                },
              ),
              const Spacer(),
              OutlinedButton.icon(
                onPressed: _llamarEmergencias,
                icon: const Icon(Icons.phone_in_talk),
                label: const Text('Llamar emergencias (107)'),
              ),
              const SizedBox(height: 8),
              Text(
                'No reemplaza el servicio publico de urgencias.',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Colors.white54),
              ),
              const SizedBox(height: 16),
            ],
          ),
        ),
      ),
    );
  }
}
