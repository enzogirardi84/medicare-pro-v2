import 'package:flutter/material.dart';

import '../app_text_scale_notifier.dart';
import '../config/app_settings.dart';
import '../utils/url_utils.dart';

/// Configuracion una vez: Supabase + clinica + identificador del paciente (DNI o codigo legajo).
class EmergencySettingsScreen extends StatefulWidget {
  const EmergencySettingsScreen({super.key, this.onSaved});

  final VoidCallback? onSaved;

  @override
  State<EmergencySettingsScreen> createState() => _EmergencySettingsScreenState();
}

class _EmergencySettingsScreenState extends State<EmergencySettingsScreen> {
  final _urlCtrl = TextEditingController();
  final _anonCtrl = TextEditingController();
  final _secretCtrl = TextEditingController();
  final _empresaCtrl = TextEditingController();
  final _pacienteCtrl = TextEditingController();
  final _nombreCtrl = TextEditingController();
  final _emergCtrl = TextEditingController();
  bool _loading = true;
  bool _largeText = false;

  @override
  void initState() {
    super.initState();
    _cargar();
  }

  Future<void> _cargar() async {
    _urlCtrl.text = (await AppSettings.getSupabaseProjectUrl()) ?? '';
    _anonCtrl.text = (await AppSettings.getSupabaseAnonKey()) ?? '';
    _secretCtrl.text = (await AppSettings.getIngestSecret()) ?? '';
    _empresaCtrl.text = (await AppSettings.getEmpresaClave()) ?? '';
    _pacienteCtrl.text = (await AppSettings.getPatientToken()) ?? '';
    _nombreCtrl.text = (await AppSettings.getPatientName()) ?? '';
    final em = await AppSettings.getEmergencyPhone();
    _emergCtrl.text = em == '107' ? '' : em;
    _largeText = await AppSettings.getLargeText();
    if (mounted) setState(() => _loading = false);
  }

  Future<void> _guardar({bool popRoute = false}) async {
    final ns = normalizeApiBaseUrl(_urlCtrl.text);
    if (_urlCtrl.text.trim().isNotEmpty && ns == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('URL Supabase invalida (https://xxx.supabase.co)'),
          backgroundColor: Colors.deepOrange,
        ),
      );
      return;
    }
    if (ns != null) {
      _urlCtrl.text = ns;
    }
    await AppSettings.setSupabaseProjectUrl(ns ?? '');
    await AppSettings.setSupabaseAnonKey(_anonCtrl.text);
    await AppSettings.setIngestSecret(_secretCtrl.text);
    await AppSettings.setEmpresaClave(_empresaCtrl.text);
    await AppSettings.setPatientToken(_pacienteCtrl.text);
    await AppSettings.setPatientName(_nombreCtrl.text);
    await AppSettings.setEmergencyPhone(_emergCtrl.text.trim());
    await AppSettings.setDeliveryMode('supabase');

    widget.onSaved?.call();
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Guardado')),
      );
      if (popRoute && Navigator.canPop(context)) {
        Navigator.pop(context, true);
      } else {
        setState(() {});
      }
    }
  }

  @override
  void dispose() {
    _urlCtrl.dispose();
    _anonCtrl.dispose();
    _secretCtrl.dispose();
    _empresaCtrl.dispose();
    _pacienteCtrl.dispose();
    _nombreCtrl.dispose();
    _emergCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final canPop = Navigator.canPop(context);
    if (_loading) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('Configuracion'),
        leading: canPop ? const BackButton() : null,
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          const Text(
            'Datos que entrega tu clinica. Sin esto no se puede enviar la alerta a MediCare.',
            style: TextStyle(color: Colors.white70),
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _urlCtrl,
            decoration: const InputDecoration(
              labelText: 'URL proyecto Supabase',
              border: OutlineInputBorder(),
            ),
            keyboardType: TextInputType.url,
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _anonCtrl,
            decoration: const InputDecoration(
              labelText: 'Clave anon',
              border: OutlineInputBorder(),
            ),
            obscureText: true,
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _secretCtrl,
            decoration: const InputDecoration(
              labelText: 'Secreto de ingesta (Edge Function)',
              border: OutlineInputBorder(),
            ),
            obscureText: true,
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _empresaCtrl,
            decoration: const InputDecoration(
              labelText: 'Clinica (minusculas, igual que MediCare)',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _pacienteCtrl,
            decoration: const InputDecoration(
              labelText: 'DNI o codigo de paciente',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _nombreCtrl,
            decoration: const InputDecoration(
              labelText: 'Nombre (opcional)',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: _emergCtrl,
            decoration: const InputDecoration(
              labelText: 'Emergencias telefono (opcional, default 107)',
              border: OutlineInputBorder(),
            ),
            keyboardType: TextInputType.phone,
          ),
          const SizedBox(height: 16),
          SwitchListTile(
            title: const Text('Texto mas grande'),
            subtitle: const Text('Letras mas grandes en toda la app'),
            value: _largeText,
            onChanged: (v) async {
              await AppSettings.setLargeText(v);
              appTextScaleNotifier.value = await AppSettings.getTextScaleFactor();
              if (mounted) setState(() => _largeText = v);
            },
          ),
          const SizedBox(height: 24),
          FilledButton(
            onPressed: () => _guardar(popRoute: canPop),
            child: const Text('Guardar'),
          ),
        ],
      ),
    );
  }
}
