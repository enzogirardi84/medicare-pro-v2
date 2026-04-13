import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';

import '../config/app_settings.dart';
import '../l10n/app_strings.dart';
import '../services/network_connectivity_service.dart';
import '../services/pending_alert_queue.dart';
import '../services/pending_alerts_processor.dart';
import '../utils/format_utils.dart';
import 'emergency_settings_screen.dart';
import 'symptom_grid_screen.dart';

/// Pantalla 1: un solo boton gigante (a prueba de panico).
class NeedHelpHomeScreen extends StatefulWidget {
  const NeedHelpHomeScreen({super.key, required this.onOpenSettings});

  final Future<void> Function() onOpenSettings;

  @override
  State<NeedHelpHomeScreen> createState() => _NeedHelpHomeScreenState();
}

class _NeedHelpHomeScreenState extends State<NeedHelpHomeScreen> with WidgetsBindingObserver {
  String? _nombrePaciente;
  String? _ultimaAlertaResumen;
  String? _ultimaAlertaFecha;
  String _telefonoEmergencias = '107';
  int _ultimoTapAyudaMs = 0;
  int _pendientes = 0;
  bool _procesandoCola = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _cargarContexto();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      unawaited(_cargarContexto());
    }
  }

  Future<void> _cargarContexto() async {
    final nombre = (await AppSettings.getPatientName())?.trim();
    final sum = (await AppSettings.getLastAlertSummary())?.trim();
    final at = (await AppSettings.getLastAlertAtIso())?.trim();
    final tel = await AppSettings.getEmergencyPhone();
    final pen = await PendingAlertQueue.cantidad();
    if (!mounted) return;
    setState(() {
      _nombrePaciente = nombre != null && nombre.isNotEmpty ? nombre : null;
      _ultimaAlertaResumen = sum != null && sum.isNotEmpty ? sum : null;
      _ultimaAlertaFecha = at != null && at.isNotEmpty ? at : null;
      _telefonoEmergencias = tel.trim().isEmpty ? '107' : tel.trim();
      _pendientes = pen;
    });
  }

  Future<void> _enviarCola() async {
    if (_procesandoCola || _pendientes <= 0) return;
    final okNet = await NetworkConnectivityService.ensureBeforeAlert(context);
    if (!mounted || !okNet) return;
    final antes = _pendientes;
    setState(() => _procesandoCola = true);
    final r = await procesarColaPendiente();
    if (!mounted) return;
    setState(() => _procesandoCola = false);
    await _cargarContexto();
    if (!mounted) return;
    final String msg;
    final Color snackBg;
    if (r.enviadas == 0 && r.fallidas >= antes) {
      msg = AppStrings.pendientesNada;
      snackBg = Colors.red.shade900;
    } else if (r.fallidas == 0) {
      msg = AppStrings.pendientesListo;
      snackBg = Colors.teal.shade800;
    } else {
      msg = AppStrings.pendientesParcial;
      snackBg = Colors.deepOrange.shade800;
    }
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(msg),
        backgroundColor: snackBg,
        behavior: SnackBarBehavior.floating,
        duration: const Duration(seconds: 5),
      ),
    );
  }

  Future<void> _descartarCola() async {
    final yes = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text(AppStrings.descartarPendientesTitulo),
        content: const Text(AppStrings.descartarPendientesBody),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text(AppStrings.cancelar)),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text(AppStrings.descartarPendientes)),
        ],
      ),
    );
    if (yes == true) {
      await PendingAlertQueue.limpiar();
      await _cargarContexto();
    }
  }

  Future<void> _llamarEmergencias() async {
    var cleaned = _telefonoEmergencias.replaceAll(RegExp(r'[\s.-]'), '');
    if (cleaned.isEmpty) cleaned = '107';
    final uri = Uri.parse('tel:$cleaned');
    if (await canLaunchUrl(uri)) {
      final abrio = await launchUrl(uri, mode: LaunchMode.externalApplication);
      if (!abrio && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(AppStrings.marcarEmergenciasManual(cleaned)),
            behavior: SnackBarBehavior.floating,
            duration: const Duration(seconds: 6),
          ),
        );
      }
    } else if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(AppStrings.marcarEmergenciasManual(cleaned)),
          behavior: SnackBarBehavior.floating,
          duration: const Duration(seconds: 6),
        ),
      );
    }
  }

  Future<void> _abrirAjustes() async {
    await Navigator.push<bool>(
      context,
      MaterialPageRoute(
        fullscreenDialog: true,
        builder: (_) => const EmergencySettingsScreen(),
      ),
    );
    await widget.onOpenSettings();
    await _cargarContexto();
  }

  @override
  Widget build(BuildContext context) {
    final tt = Theme.of(context).textTheme;
    return Scaffold(
      appBar: AppBar(
        title: const Text(AppStrings.medicare),
        centerTitle: true,
        actions: [
          Badge(
            isLabelVisible: _pendientes > 0,
            label: Text(
              _pendientes > 9 ? '9+' : '$_pendientes',
              style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w800),
            ),
            child: IconButton(
              icon: const Icon(Icons.settings_outlined),
              tooltip: _pendientes > 0
                  ? AppStrings.ajustesTooltipConPendientes(_pendientes)
                  : AppStrings.configuracion,
              onPressed: _abrirAjustes,
            ),
          ),
        ],
      ),
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, constraints) {
            final cs = Theme.of(context).colorScheme;
            return RefreshIndicator(
              onRefresh: _cargarContexto,
              color: cs.primary,
              backgroundColor: cs.surfaceContainerHighest,
              child: SingleChildScrollView(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
                child: ConstrainedBox(
                  constraints: BoxConstraints(minHeight: constraints.maxHeight - 16),
                  child: Column(
                    children: [
                    if (_nombrePaciente != null) ...[
                      Text(
                        '${AppStrings.hola}, $_nombrePaciente',
                        textAlign: TextAlign.center,
                        style: tt.titleMedium?.copyWith(
                          color: const Color(0xFF5EEAD4),
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const SizedBox(height: 8),
                    ],
                    Text(
                      AppStrings.ayudaIntro,
                      textAlign: TextAlign.center,
                      style: tt.bodyLarge?.copyWith(color: Colors.white70),
                    ),
                    if (_pendientes > 0) ...[
                      const SizedBox(height: 16),
                      Semantics(
                        container: true,
                        label:
                            '${AppStrings.pendientesTitulo}, $_pendientes. ${AppStrings.pendientesSub}',
                        child: Material(
                          color: Colors.deepOrange.shade900.withOpacity(0.45),
                          borderRadius: BorderRadius.circular(12),
                          child: Padding(
                            padding: const EdgeInsets.all(14),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.stretch,
                              children: [
                                Row(
                                  children: [
                                    Icon(Icons.cloud_off_outlined, color: Colors.orange.shade200),
                                    const SizedBox(width: 10),
                                    Expanded(
                                      child: Text(
                                        '${AppStrings.pendientesTitulo} ($_pendientes)',
                                        style: tt.titleSmall?.copyWith(fontWeight: FontWeight.w800),
                                      ),
                                    ),
                                  ],
                                ),
                                const SizedBox(height: 6),
                                Text(AppStrings.pendientesSub, style: tt.bodySmall?.copyWith(color: Colors.white70)),
                                const SizedBox(height: 12),
                                Row(
                                  children: [
                                    Expanded(
                                      child: FilledButton.icon(
                                        onPressed: _procesandoCola ? null : _enviarCola,
                                        icon: _procesandoCola
                                            ? const SizedBox(
                                                width: 18,
                                                height: 18,
                                                child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                                              )
                                            : const Icon(Icons.send, size: 20),
                                        label: Text(_procesandoCola ? AppStrings.pendientesEnviando : AppStrings.enviarPendientes),
                                      ),
                                    ),
                                    const SizedBox(width: 8),
                                    OutlinedButton(
                                      onPressed: _procesandoCola ? null : _descartarCola,
                                      child: const Text(AppStrings.descartarPendientes),
                                    ),
                                  ],
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ],
                    if (_ultimaAlertaResumen != null) ...[
                      const SizedBox(height: 16),
                      Semantics(
                        container: true,
                        label:
                            '${AppStrings.ultimaAlertaTitulo}. $_ultimaAlertaResumen. ${formatearFechaHoraLocal(_ultimaAlertaFecha)}',
                        child: Material(
                          color: const Color(0xFF1E293B),
                          borderRadius: BorderRadius.circular(12),
                          child: Padding(
                            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.stretch,
                              children: [
                                Text(
                                  AppStrings.ultimaAlertaTitulo,
                                  style: tt.labelSmall?.copyWith(color: Colors.white54, letterSpacing: 0.4),
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  _ultimaAlertaResumen!,
                                  style: tt.bodyMedium?.copyWith(fontWeight: FontWeight.w600),
                                ),
                                if (_ultimaAlertaFecha != null)
                                  Text(
                                    formatearFechaHoraLocal(_ultimaAlertaFecha),
                                    style: tt.bodySmall?.copyWith(color: Colors.white54),
                                  ),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ],
                    const SizedBox(height: 28),
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
                                label: AppStrings.necesitoAyudaLabel,
                                hint: AppStrings.necesitoAyudaHint,
                                child: InkWell(
                                  customBorder: const CircleBorder(),
                                  onTap: () async {
                                    final now = DateTime.now().millisecondsSinceEpoch;
                                    if (now - _ultimoTapAyudaMs < 900) {
                                      return;
                                    }
                                    _ultimoTapAyudaMs = now;
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
                                    await _cargarContexto();
                                  },
                                  child: const Center(
                                    child: Padding(
                                      padding: EdgeInsets.all(16),
                                      child: Text(
                                        AppStrings.necesitoAyudaBoton,
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
                    const SizedBox(height: 28),
                    Tooltip(
                      message: _telefonoEmergencias == '107'
                          ? AppStrings.llamarEmergencias
                          : '${AppStrings.llamarEmergenciasCon} $_telefonoEmergencias',
                      child: OutlinedButton.icon(
                        onPressed: _llamarEmergencias,
                        icon: const Icon(Icons.phone_in_talk),
                        label: Text(
                          _telefonoEmergencias == '107'
                              ? AppStrings.llamarEmergencias
                              : '${AppStrings.llamarEmergenciasCon} ($_telefonoEmergencias)',
                        ),
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      AppStrings.disclaimerUrgencias,
                      textAlign: TextAlign.center,
                      style: tt.bodySmall?.copyWith(color: Colors.white54),
                    ),
                    const SizedBox(height: 24),
                  ],
                ),
              ),
              ),
            );
          },
        ),
      ),
    );
  }
}
