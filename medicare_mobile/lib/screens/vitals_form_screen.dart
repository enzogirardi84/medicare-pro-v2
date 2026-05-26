import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:medicare_mobile/models/vitals.dart';
import 'package:medicare_mobile/services/api_service.dart';
import 'package:medicare_mobile/providers/app_providers.dart';
import 'package:medicare_mobile/widgets/shared_widgets.dart';

class VitalsFormScreen extends StatefulWidget {
  final String patientId;
  const VitalsFormScreen({super.key, required this.patientId});

  @override
  State<VitalsFormScreen> createState() => _VitalsFormScreenState();
}

class _VitalsFormScreenState extends State<VitalsFormScreen> {
  final _formKey = GlobalKey<FormState>();
  final _tempCtrl = TextEditingController();
  final _hrCtrl = TextEditingController();
  final _sysCtrl = TextEditingController();
  final _diaCtrl = TextEditingController();
  final _satCtrl = TextEditingController();
  final _pesoCtrl = TextEditingController();
  final _alturaCtrl = TextEditingController();
  bool _loading = false;

  @override
  void dispose() {
    _tempCtrl.dispose();
    _hrCtrl.dispose();
    _sysCtrl.dispose();
    _diaCtrl.dispose();
    _satCtrl.dispose();
    _pesoCtrl.dispose();
    _alturaCtrl.dispose();
    super.dispose();
  }

  bool _validateRanges() {
    final sys = int.tryParse(_sysCtrl.text);
    final dia = int.tryParse(_diaCtrl.text);
    final temp = double.tryParse(_tempCtrl.text);
    final hr = int.tryParse(_hrCtrl.text);
    final sat = int.tryParse(_satCtrl.text);

    if (temp != null && (temp < 30 || temp > 45)) {
      _showError('Temperatura debe estar entre 30°C y 45°C');
      return false;
    }
    if (hr != null && (hr < 30 || hr > 250)) {
      _showError('Frecuencia cardíaca debe estar entre 30 y 250 bpm');
      return false;
    }
    if (sys != null && (sys < 50 || sys > 250)) {
      _showError('Presión sistólica debe estar entre 50 y 250');
      return false;
    }
    if (dia != null && (dia < 30 || dia > 150)) {
      _showError('Presión diastólica debe estar entre 30 y 150');
      return false;
    }
    if (sys != null && dia != null && dia >= sys) {
      _showError('Presión diastólica debe ser menor que la sistólica');
      return false;
    }
    if (sat != null && (sat < 50 || sat > 100)) {
      _showError('Sat O₂ debe estar entre 50% y 100%');
      return false;
    }
    return true;
  }

  void _showError(String msg) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(msg), backgroundColor: Colors.red, behavior: SnackBarBehavior.floating),
    );
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    if (!_validateRanges()) return;

    setState(() => _loading = true);

    final vitals = VitalsCreate(
      pacienteId: widget.patientId,
      temperatura: double.tryParse(_tempCtrl.text),
      frecuenciaCardiaca: int.tryParse(_hrCtrl.text),
      presionSistolica: int.tryParse(_sysCtrl.text),
      presionDiastolica: int.tryParse(_diaCtrl.text),
      saturacionO2: int.tryParse(_satCtrl.text),
      peso: double.tryParse(_pesoCtrl.text),
      altura: double.tryParse(_alturaCtrl.text),
    );

    try {
      final api = context.read<ApiService>();
      await api.createVitals(vitals);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Signos vitales registrados'), backgroundColor: Colors.green),
      );
      Navigator.of(context).pop();
    } on ApiException catch (e) {
      if (e.isNetworkError) {
        final offline = context.read<OfflineProvider>();
        await offline.saveVitalsOffline(vitals);
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Sin conexión — datos guardados localmente'), backgroundColor: Colors.orange),
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
      appBar: AppBar(title: const Text('Signos vitales')),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            _field('Temperatura (°C)', _tempCtrl, hint: '36.5', range: '30 – 45'),
            _field('Frec. cardíaca (bpm)', _hrCtrl, hint: '72', range: '30 – 250'),
            Row(
              children: [
                Expanded(child: _field('PA sistólica', _sysCtrl, hint: '120', range: '50 – 250')),
                const SizedBox(width: 12),
                Expanded(child: _field('PA diastólica', _diaCtrl, hint: '80', range: '30 – 150')),
              ],
            ),
            _field('Sat O₂ (%)', _satCtrl, hint: '98', range: '50 – 100'),
            Row(
              children: [
                Expanded(child: _field('Peso (kg)', _pesoCtrl, hint: '70.5', range: '0.5 – 300')),
                const SizedBox(width: 12),
                Expanded(child: _field('Altura (m)', _alturaCtrl, hint: '1.75', range: '0.3 – 2.5')),
              ],
            ),
            const SizedBox(height: 28),
            SizedBox(
              height: 50,
              child: FilledButton(
                onPressed: _loading ? null : _submit,
                child: _loading
                    ? const SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2.5))
                    : const Text('Guardar', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _field(String label, TextEditingController ctrl, {String? hint, String? range}) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: TextFormField(
        controller: ctrl,
        keyboardType: const TextInputType.numberWithOptions(decimal: true, signed: false),
        decoration: InputDecoration(
          labelText: label,
          hintText: hint,
          helperText: range != null ? 'Rango: $range' : null,
              helperStyle: const TextStyle(fontSize: 11),
        ),
      ),
    );
  }
}
