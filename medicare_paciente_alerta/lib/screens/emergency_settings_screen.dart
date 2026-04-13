import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:package_info_plus/package_info_plus.dart';

import '../app_text_scale_notifier.dart';
import '../app_theme_notifier.dart';
import '../config/app_settings.dart';
import '../l10n/app_strings.dart';
import '../services/supabase_reachability.dart';
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
  bool _mostrarAnon = false;
  bool _mostrarSecreto = false;
  bool _probandoRed = false;
  int _cuentaSegundos = 3;
  bool _altoContraste = false;
  String? _versionLabel;

  /// Foco en orden: URL, anon, secreto, clinica, DNI, nombre, telefono emergencias.
  final List<FocusNode> _fieldFocus = List.generate(7, (_) => FocusNode());

  void _irCampo(int index) {
    if (!mounted) return;
    if (index >= 0 && index < _fieldFocus.length) {
      _fieldFocus[index].requestFocus();
    } else {
      FocusScope.of(context).unfocus();
    }
  }

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
    _cuentaSegundos = await AppSettings.getCountdownSeconds();
    _altoContraste = await AppSettings.getHighContrast();
    try {
      final info = await PackageInfo.fromPlatform();
      if (!mounted) return;
      _versionLabel = '${info.version}+${info.buildNumber}';
    } catch (_) {
      if (!mounted) return;
      _versionLabel = null;
    }
    if (mounted) setState(() => _loading = false);
  }

  Future<void> _probarConexionSupabase() async {
    if (_probandoRed) return;
    setState(() => _probandoRed = true);
    final err = await SupabaseReachability.probarProyecto(
      urlRaw: _urlCtrl.text,
      anonKey: _anonCtrl.text,
    );
    if (!mounted) return;
    setState(() => _probandoRed = false);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(err ?? AppStrings.conexionOk),
        backgroundColor: err != null ? Colors.deepOrange.shade800 : Colors.teal.shade800,
        behavior: SnackBarBehavior.floating,
        duration: Duration(seconds: err != null ? 6 : 3),
      ),
    );
  }

  Future<void> _guardar({bool popRoute = false}) async {
    final ns = normalizeApiBaseUrl(_urlCtrl.text);
    if (_urlCtrl.text.trim().isNotEmpty && ns == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(AppStrings.urlInvalida),
          backgroundColor: Colors.deepOrange,
          behavior: SnackBarBehavior.floating,
          duration: Duration(seconds: 5),
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
    if (_pacienteCtrl.text.trim().length < 3) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(AppStrings.dniCorto),
          backgroundColor: Colors.deepOrange,
          behavior: SnackBarBehavior.floating,
          duration: Duration(seconds: 5),
        ),
      );
      return;
    }
    await AppSettings.setEmpresaClave(_empresaCtrl.text);
    await AppSettings.setPatientToken(_pacienteCtrl.text);
    await AppSettings.setPatientName(_nombreCtrl.text);
    await AppSettings.setEmergencyPhone(_emergCtrl.text.trim());
    await AppSettings.setDeliveryMode('supabase');
    await AppSettings.setCountdownSeconds(_cuentaSegundos);
    await AppSettings.setHighContrast(_altoContraste);
    appHighContrastNotifier.value = _altoContraste;

    widget.onSaved?.call();
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(AppStrings.guardado),
          behavior: SnackBarBehavior.floating,
          duration: Duration(seconds: 3),
        ),
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
    for (final n in _fieldFocus) {
      n.dispose();
    }
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
      return Scaffold(
        appBar: AppBar(title: const Text(AppStrings.configuracion)),
        body: const Center(child: CircularProgressIndicator()),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text(AppStrings.configuracion),
        leading: canPop ? const BackButton() : null,
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
        children: [
          const Text(
            AppStrings.configDatosClinica,
            style: TextStyle(color: Colors.white70),
          ),
          const SizedBox(height: 8),
          Text(
            AppStrings.configClinicaAyuda,
            style: TextStyle(color: Colors.teal.shade200, fontSize: 13),
          ),
          const SizedBox(height: 16),
          AutofillGroup(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                TextField(
                  controller: _urlCtrl,
                  focusNode: _fieldFocus[0],
                  decoration: const InputDecoration(
                    labelText: AppStrings.campoUrlSupabase,
                    hintText: AppStrings.hintUrlSupabase,
                    border: OutlineInputBorder(),
                  ),
                  keyboardType: TextInputType.url,
                  textInputAction: TextInputAction.next,
                  autofillHints: const [AutofillHints.url],
                  autocorrect: false,
                  onSubmitted: (_) => _irCampo(1),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _anonCtrl,
                  focusNode: _fieldFocus[1],
                  decoration: InputDecoration(
                    labelText: AppStrings.campoClaveAnon,
                    border: const OutlineInputBorder(),
                    suffixIcon: IconButton(
                      tooltip: _mostrarAnon ? AppStrings.tooltipOcultar : AppStrings.tooltipMostrar,
                      icon: Icon(_mostrarAnon ? Icons.visibility_off : Icons.visibility),
                      onPressed: () => setState(() => _mostrarAnon = !_mostrarAnon),
                    ),
                  ),
                  obscureText: !_mostrarAnon,
                  textInputAction: TextInputAction.next,
                  autocorrect: false,
                  enableSuggestions: false,
                  onSubmitted: (_) => _irCampo(2),
                ),
                const SizedBox(height: 8),
                OutlinedButton.icon(
                  onPressed: _probandoRed ? null : _probarConexionSupabase,
                  icon: _probandoRed
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.wifi_tethering, size: 20),
                  label: Text(_probandoRed ? AppStrings.probando : AppStrings.probarConexion),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _secretCtrl,
                  focusNode: _fieldFocus[2],
                  decoration: InputDecoration(
                    labelText: AppStrings.campoSecretoIngesta,
                    border: const OutlineInputBorder(),
                    suffixIcon: IconButton(
                      tooltip: _mostrarSecreto ? AppStrings.tooltipOcultar : AppStrings.tooltipMostrar,
                      icon: Icon(_mostrarSecreto ? Icons.visibility_off : Icons.visibility),
                      onPressed: () => setState(() => _mostrarSecreto = !_mostrarSecreto),
                    ),
                  ),
                  obscureText: !_mostrarSecreto,
                  textInputAction: TextInputAction.next,
                  autocorrect: false,
                  enableSuggestions: false,
                  onSubmitted: (_) => _irCampo(3),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _empresaCtrl,
                  focusNode: _fieldFocus[3],
                  decoration: const InputDecoration(
                    labelText: AppStrings.campoClinica,
                    border: OutlineInputBorder(),
                  ),
                  textCapitalization: TextCapitalization.none,
                  textInputAction: TextInputAction.next,
                  autofillHints: const [AutofillHints.organizationName],
                  onSubmitted: (_) => _irCampo(4),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _pacienteCtrl,
                  focusNode: _fieldFocus[4],
                  decoration: const InputDecoration(
                    labelText: AppStrings.campoDni,
                    border: OutlineInputBorder(),
                  ),
                  textInputAction: TextInputAction.next,
                  autofillHints: const [AutofillHints.username],
                  autocorrect: false,
                  onSubmitted: (_) => _irCampo(5),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _nombreCtrl,
                  focusNode: _fieldFocus[5],
                  decoration: const InputDecoration(
                    labelText: AppStrings.campoNombre,
                    border: OutlineInputBorder(),
                  ),
                  textInputAction: TextInputAction.next,
                  autofillHints: const [AutofillHints.name],
                  textCapitalization: TextCapitalization.words,
                  onSubmitted: (_) => _irCampo(6),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _emergCtrl,
                  focusNode: _fieldFocus[6],
                  decoration: const InputDecoration(
                    labelText: AppStrings.campoTelefonoEmergencias,
                    border: OutlineInputBorder(),
                  ),
                  keyboardType: TextInputType.phone,
                  textInputAction: TextInputAction.done,
                  autofillHints: const [AutofillHints.telephoneNumber],
                  onSubmitted: (_) => FocusScope.of(context).unfocus(),
                ),
              ],
            ),
          ),
          const SizedBox(height: 20),
          Text(
            AppStrings.cuentaRegresivaTitulo,
            style: Theme.of(context).textTheme.titleSmall,
          ),
          Text(
            AppStrings.cuentaRegresivaSub,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Colors.white54),
          ),
          Slider(
            value: _cuentaSegundos.toDouble(),
            min: 2,
            max: 8,
            divisions: 6,
            label: AppStrings.sliderSegundos(_cuentaSegundos),
            onChanged: (v) => setState(() => _cuentaSegundos = v.round()),
            onChangeEnd: (v) async {
              await AppSettings.setCountdownSeconds(v.round());
            },
          ),
          const SizedBox(height: 8),
          SwitchListTile(
            title: const Text(AppStrings.textoGrandeTitulo),
            subtitle: const Text(AppStrings.textoGrandeSub),
            value: _largeText,
            onChanged: (v) async {
              await AppSettings.setLargeText(v);
              appTextScaleNotifier.value = await AppSettings.getTextScaleFactor();
              if (mounted) setState(() => _largeText = v);
            },
          ),
          SwitchListTile(
            title: const Text(AppStrings.altoContrasteTitulo),
            subtitle: const Text(AppStrings.altoContrasteSub),
            value: _altoContraste,
            onChanged: (v) async {
              await AppSettings.setHighContrast(v);
              appHighContrastNotifier.value = v;
              if (mounted) setState(() => _altoContraste = v);
            },
          ),
          const SizedBox(height: 24),
          FilledButton(
            onPressed: () => _guardar(popRoute: canPop),
            child: const Text(AppStrings.guardar),
          ),
          if (_versionLabel != null) ...[
            const SizedBox(height: 16),
            Center(
              child: Text(
                AppStrings.versionEtiqueta(_versionLabel!),
                style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Colors.white38),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
