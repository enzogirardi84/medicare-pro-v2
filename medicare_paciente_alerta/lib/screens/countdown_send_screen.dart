import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:wakelock_plus/wakelock_plus.dart';

import '../config/app_settings.dart';
import '../l10n/app_strings.dart';
import '../models/triage_symptom.dart';
import '../services/alerta_paciente_edge_service.dart';
import '../services/location_service.dart';
import '../services/pending_alert_queue.dart';

/// Pantalla 3: cuenta regresiva configurable y envio con GPS.
class CountdownSendScreen extends StatefulWidget {
  const CountdownSendScreen({super.key, required this.sintoma});

  final TriageSintoma sintoma;

  @override
  State<CountdownSendScreen> createState() => _CountdownSendScreenState();
}

class _CountdownSendScreenState extends State<CountdownSendScreen> {
  int _totalSegundos = 3;
  int _segundos = 3;
  Timer? _timer;
  bool _cancelado = false;
  bool _enviando = false;
  bool _obteniendoUbicacion = false;
  bool _inicializando = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    unawaited(WakelockPlus.enable());
    unawaited(_boot());
  }

  Future<void> _boot() async {
    final n = await AppSettings.getCountdownSeconds();
    if (!mounted) return;
    setState(() {
      _totalSegundos = n;
      _segundos = n;
      _inicializando = false;
    });
    _iniciarTimer();
  }

  void _iniciarTimer() {
    _timer?.cancel();
    _timer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (!mounted || _cancelado) return;
      if (_segundos <= 1) {
        _timer?.cancel();
        _timer = null;
        unawaited(_dispararEnvio());
        return;
      }
      HapticFeedback.selectionClick();
      setState(() => _segundos--);
    });
  }

  Future<void> _dispararEnvio() async {
    if (_enviando || !mounted) return;
    setState(() {
      _enviando = true;
      _obteniendoUbicacion = true;
      _error = null;
    });

    final pacienteId = (await AppSettings.getPatientToken()).trim();
    final empresa = (await AppSettings.getEmpresaClave()).trim();
    final url = (await AppSettings.getSupabaseProjectUrl()).trim();
    final anon = (await AppSettings.getSupabaseAnonKey()).trim();
    final secret = (await AppSettings.getIngestSecret()).trim();

    if (pacienteId.isEmpty || empresa.isEmpty || url.isEmpty || anon.isEmpty || secret.isEmpty) {
      if (mounted) {
        setState(() {
          _enviando = false;
          _obteniendoUbicacion = false;
          _error = AppStrings.faltaConfiguracion;
        });
      }
      return;
    }

    final pos = await LocationService.getCurrentPosition();

    if (mounted) {
      setState(() => _obteniendoUbicacion = false);
    }

    final svc = AlertaPacienteEdgeService(
      projectUrl: url,
      anonKey: anon,
      ingestSecret: secret,
    );

    final res = await svc.enviar(
      pacienteId: pacienteId,
      sintomaLabel: widget.sintoma.label,
      nivel: widget.sintoma.nivel,
      empresaClave: empresa,
      latitud: pos?.latitude,
      longitud: pos?.longitude,
      precisionM: pos?.accuracy,
    );

    if (!mounted) return;

    if (res.ok) {
      HapticFeedback.heavyImpact();
      await AppSettings.setLastAlertSent(
        atIso: DateTime.now().toLocal().toIso8601String(),
        summary: '${widget.sintoma.label} (${widget.sintoma.nivel.apiLabel})',
      );
      if (!mounted) return;
      await showDialog<void>(
        context: context,
        barrierDismissible: false,
        builder: (ctx) => AlertDialog(
          title: const Text(AppStrings.alertaEnviadaTitulo),
          content: Text(
            pos == null
                ? AppStrings.alertaEnviadaSinGps
                : '${AppStrings.alertaEnviadaConGps}'
                    '${pos.accuracy.isFinite ? ' ${AppStrings.precisionMetros} ~${pos.accuracy.round()} m.' : ''}',
          ),
          actions: [
            TextButton(
              onPressed: () {
                Navigator.pop(ctx);
                Navigator.of(context).popUntil((r) => r.isFirst);
              },
              child: const Text(AppStrings.ok),
            ),
          ],
        ),
      );
    } else {
      HapticFeedback.mediumImpact();
      await PendingAlertQueue.encolar(
        sintomaLabel: widget.sintoma.label,
        nivelUrgencia: widget.sintoma.nivel.apiLabel,
        latitud: pos?.latitude,
        longitud: pos?.longitude,
        precisionM: pos?.accuracy,
      );
      if (!mounted) return;
      setState(() {
        _enviando = false;
        _obteniendoUbicacion = false;
        _error =
            '${res.message ?? AppStrings.errorEnviarGenerico}\n\n${AppStrings.guardadoEnCola}';
      });
    }
  }

  Future<void> _manejarSalir() async {
    if (_inicializando) {
      if (mounted) Navigator.pop(context);
      return;
    }
    if (_enviando) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(AppStrings.enviandoNoSalir),
          behavior: SnackBarBehavior.floating,
          duration: Duration(seconds: 3),
        ),
      );
      return;
    }
    if (_error != null) {
      if (mounted) Navigator.pop(context);
      return;
    }
    final yes = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text(AppStrings.salirConfirmTitulo),
        content: const Text(AppStrings.salirConfirmBody),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text(AppStrings.salirNo)),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text(AppStrings.salirSi)),
        ],
      ),
    );
    if (yes == true && mounted) {
      _cancelar();
    }
  }

  void _cancelar() {
    _cancelado = true;
    _timer?.cancel();
    Navigator.pop(context);
  }

  @override
  void dispose() {
    _timer?.cancel();
    unawaited(WakelockPlus.disable());
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, result) {
        if (didPop) return;
        unawaited(_manejarSalir());
      },
      child: Scaffold(
        appBar: AppBar(
          title: const Text(AppStrings.confirmar),
          leading: IconButton(
            icon: const Icon(Icons.close),
            onPressed: _enviando ? null : _manejarSalir,
          ),
        ),
        body: Padding(
          padding: const EdgeInsets.all(24),
          child: _inicializando
              ? const Center(child: CircularProgressIndicator())
              : Column(
                  children: [
                    Text(
                      widget.sintoma.label,
                      textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800),
                    ),
                    const SizedBox(height: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                      decoration: BoxDecoration(
                        color: widget.sintoma.nivel.color.withOpacity(0.2),
                        borderRadius: BorderRadius.circular(20),
                        border: Border.all(color: widget.sintoma.nivel.color),
                      ),
                      child: Text(
                        AppStrings.triajeEtiqueta(widget.sintoma.nivel.apiLabel),
                        style: TextStyle(
                          color: widget.sintoma.nivel.color,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                    const Spacer(),
                    if (_enviando)
                      Column(
                        children: [
                          const CircularProgressIndicator(),
                          const SizedBox(height: 16),
                          Text(
                            _obteniendoUbicacion ? AppStrings.obteniendoUbicacion : AppStrings.enviandoAlerta,
                            textAlign: TextAlign.center,
                          ),
                        ],
                      )
                    else if (_error != null)
                      Column(
                        children: [
                          Icon(Icons.error_outline, size: 48, color: Colors.red.shade300),
                          const SizedBox(height: 12),
                          SelectableText(
                            _error!,
                            textAlign: TextAlign.center,
                            style: Theme.of(context).textTheme.bodyLarge?.copyWith(color: Colors.white70),
                          ),
                          const SizedBox(height: 12),
                          TextButton.icon(
                            onPressed: () async {
                              await Clipboard.setData(ClipboardData(text: _error!));
                              if (!context.mounted) return;
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(
                                  content: Text(AppStrings.copiadoSoporte),
                                  behavior: SnackBarBehavior.floating,
                                  duration: Duration(seconds: 3),
                                ),
                              );
                            },
                            icon: const Icon(Icons.copy, size: 18),
                            label: const Text(AppStrings.copiarMensaje),
                          ),
                          const SizedBox(height: 12),
                          FilledButton(
                            onPressed: () {
                              setState(() => _error = null);
                              unawaited(_dispararEnvio());
                            },
                            child: const Text(AppStrings.reintentarEnvio),
                          ),
                          const SizedBox(height: 8),
                          OutlinedButton(
                            onPressed: () => Navigator.pop(context),
                            child: const Text(AppStrings.volver),
                          ),
                        ],
                      )
                    else ...[
                      Semantics(
                        liveRegion: true,
                        label: _segundos > 0
                            ? AppStrings.segundosRestantesParaEnviar(_segundos)
                            : AppStrings.enviando,
                        child: Column(
                          children: [
                            Text(
                              _segundos > 0
                                  ? '${AppStrings.cuentaRegresiva} $_segundos...'
                                  : AppStrings.enviando,
                              textAlign: TextAlign.center,
                              style: Theme.of(context).textTheme.titleMedium,
                            ),
                            const SizedBox(height: 28),
                            SizedBox(
                              width: 120,
                              height: 120,
                              child: Stack(
                                fit: StackFit.expand,
                                children: [
                                  CircularProgressIndicator(
                                    value: _totalSegundos > 0 && _segundos > 0
                                        ? (_totalSegundos - _segundos) / _totalSegundos
                                        : 1,
                                    strokeWidth: 8,
                                    backgroundColor: Colors.white12,
                                  ),
                                  Center(
                                    child: Text(
                                      '$_segundos',
                                      style: const TextStyle(fontSize: 44, fontWeight: FontWeight.w900),
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                    const Spacer(),
                    if (!_enviando && _error == null && !_inicializando)
                      OutlinedButton(
                        onPressed: _cancelar,
                        child: const Text(AppStrings.cancelar),
                      ),
                  ],
                ),
        ),
      ),
    );
  }
}
