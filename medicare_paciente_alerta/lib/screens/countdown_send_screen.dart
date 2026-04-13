import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:wakelock_plus/wakelock_plus.dart';

import '../config/app_settings.dart';
import '../models/triage_symptom.dart';
import '../services/alerta_paciente_edge_service.dart';
import '../services/location_service.dart';

/// Pantalla 3: cuenta regresiva 3 s y envio con GPS.
class CountdownSendScreen extends StatefulWidget {
  const CountdownSendScreen({super.key, required this.sintoma});

  final TriageSintoma sintoma;

  @override
  State<CountdownSendScreen> createState() => _CountdownSendScreenState();
}

class _CountdownSendScreenState extends State<CountdownSendScreen> {
  int _segundos = 3;
  Timer? _timer;
  bool _cancelado = false;
  bool _enviando = false;
  bool _obteniendoUbicacion = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    unawaited(WakelockPlus.enable());
    _timer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (!mounted || _cancelado) return;
      if (_segundos <= 1) {
        _timer?.cancel();
        _timer = null;
        _dispararEnvio();
        return;
      }
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
          _error = 'Falta configuracion. Abri ajustes y completa los datos.';
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
          title: const Text('Alerta enviada'),
          content: Text(
            pos == null
                ? 'Tu equipo fue avisado. Activa el GPS para proximas veces.'
                : 'Tu equipo fue avisado con tu ubicacion.'
                    '${pos.accuracy.isFinite ? ' Precision ~${pos.accuracy.round()} m.' : ''}',
          ),
          actions: [
            TextButton(
              onPressed: () {
                Navigator.pop(ctx);
                Navigator.of(context).popUntil((r) => r.isFirst);
              },
              child: const Text('OK'),
            ),
          ],
        ),
      );
    } else {
      HapticFeedback.mediumImpact();
      setState(() {
        _enviando = false;
        _obteniendoUbicacion = false;
        _error = res.message ?? 'Error al enviar';
      });
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
    return Scaffold(
      appBar: AppBar(
        title: const Text('Confirmar'),
        leading: IconButton(
          icon: const Icon(Icons.close),
          onPressed: _enviando ? null : _cancelar,
        ),
      ),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
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
                'Triage: ${widget.sintoma.nivel.apiLabel}',
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
                    _obteniendoUbicacion ? 'Obteniendo ubicacion...' : 'Enviando alerta...',
                    textAlign: TextAlign.center,
                  ),
                ],
              )
            else if (_error != null)
              Column(
                children: [
                  Icon(Icons.error_outline, size: 48, color: Colors.red.shade300),
                  const SizedBox(height: 12),
                  Text(_error!, textAlign: TextAlign.center),
                  const SizedBox(height: 20),
                  FilledButton(
                    onPressed: () {
                      setState(() => _error = null);
                      unawaited(_dispararEnvio());
                    },
                    child: const Text('Reintentar'),
                  ),
                  const SizedBox(height: 8),
                  OutlinedButton(
                    onPressed: () => Navigator.pop(context),
                    child: const Text('Volver'),
                  ),
                ],
              )
            else ...[
              Text(
                _segundos > 0
                    ? 'Si tocaste sin querer, volvé atrás.\nEnvio en $_segundos...'
                    : 'Enviando...',
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
                      value: _segundos > 0 ? (3 - _segundos) / 3 : 1,
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
            const Spacer(),
            if (!_enviando && _error == null)
              OutlinedButton(
                onPressed: _cancelar,
                child: const Text('Cancelar'),
              ),
          ],
        ),
      ),
    );
  }
}
