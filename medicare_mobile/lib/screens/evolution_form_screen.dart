import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:medicare_mobile/models/evolution.dart';
import 'package:medicare_mobile/services/api_service.dart';
import 'package:medicare_mobile/widgets/shared_widgets.dart';
import 'package:medicare_mobile/providers/app_providers.dart';

class EvolutionFormScreen extends StatefulWidget {
  final String patientId;
  const EvolutionFormScreen({super.key, required this.patientId});

  @override
  State<EvolutionFormScreen> createState() => _EvolutionFormScreenState();
}

class _EvolutionFormScreenState extends State<EvolutionFormScreen> {
  final _formKey = GlobalKey<FormState>();
  final _motivoCtrl = TextEditingController();
  final _diagnosticoCtrl = TextEditingController();
  final _tratamientoCtrl = TextEditingController();
  final _examenCtrl = TextEditingController();
  final _evolucionCtrl = TextEditingController();
  bool _loading = false;

  @override
  void dispose() {
    _motivoCtrl.dispose();
    _diagnosticoCtrl.dispose();
    _tratamientoCtrl.dispose();
    _examenCtrl.dispose();
    _evolucionCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _loading = true);

    final evolution = EvolutionCreate(
      pacienteId: widget.patientId,
      motivoConsulta: _motivoCtrl.text.trim(),
      diagnostico: _diagnosticoCtrl.text.trim(),
      tratamiento: _tratamientoCtrl.text.trim().isEmpty ? null : _tratamientoCtrl.text.trim(),
      examenFisico: _examenCtrl.text.trim().isEmpty ? null : _examenCtrl.text.trim(),
      evolucion: _evolucionCtrl.text.trim().isEmpty ? null : _evolucionCtrl.text.trim(),
    );

    try {
      final api = context.read<ApiService>();
      await api.createEvolution(evolution);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Evolución registrada correctamente'), backgroundColor: Colors.green),
      );
      Navigator.of(context).pop();
    } on ApiException catch (e) {
      if (e.isNetworkError) {
        final offline = context.read<OfflineProvider>();
        await offline.saveEvolutionOffline(evolution);
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Sin conexión — evolución guardada localmente'), backgroundColor: Colors.orange),
        );
        Navigator.of(context).pop();
        return;
      }
      if (!mounted) return;
      AppRetrySnackbar.show(context, e.message, onRetry: _submit);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Nueva evolución')),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            TextFormField(
              controller: _motivoCtrl,
              decoration: const InputDecoration(
                labelText: 'Motivo de consulta *',
                hintText: 'Describa el motivo principal',
              ),
              maxLines: 2,
              textCapitalization: TextCapitalization.sentences,
              validator: (v) => v == null || v.trim().length < 5 ? 'Mínimo 5 caracteres' : null,
            ),
            const SizedBox(height: 16),
            TextFormField(
              controller: _diagnosticoCtrl,
              decoration: const InputDecoration(
                labelText: 'Diagnóstico *',
                hintText: 'Diagnóstico principal',
              ),
              maxLines: 3,
              textCapitalization: TextCapitalization.sentences,
              validator: (v) => v == null || v.trim().length < 5 ? 'Mínimo 5 caracteres' : null,
            ),
            const SizedBox(height: 16),
            TextFormField(
              controller: _tratamientoCtrl,
              decoration: const InputDecoration(
                labelText: 'Tratamiento',
                hintText: 'Plan de tratamiento indicado',
              ),
              maxLines: 3,
              textCapitalization: TextCapitalization.sentences,
            ),
            const SizedBox(height: 16),
            TextFormField(
              controller: _examenCtrl,
              decoration: const InputDecoration(
                labelText: 'Examen físico',
                hintText: 'Hallazgos del examen físico',
              ),
              maxLines: 3,
              textCapitalization: TextCapitalization.sentences,
            ),
            const SizedBox(height: 16),
            TextFormField(
              controller: _evolucionCtrl,
              decoration: const InputDecoration(
                labelText: 'Evolución',
                hintText: 'Evolución del paciente',
              ),
              maxLines: 4,
              textCapitalization: TextCapitalization.sentences,
            ),
            const SizedBox(height: 28),
            SizedBox(
              height: 50,
              child: FilledButton(
                onPressed: _loading ? null : _submit,
                child: _loading
                    ? const SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2.5))
                    : const Text('Guardar evolución', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
