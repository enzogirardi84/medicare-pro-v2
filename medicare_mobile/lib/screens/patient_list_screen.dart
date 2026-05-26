import 'dart:async';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:medicare_mobile/models/patient.dart';
import 'package:medicare_mobile/services/api_service.dart';
import 'package:medicare_mobile/widgets/shared_widgets.dart';
import 'package:medicare_mobile/providers/app_providers.dart';
import 'package:medicare_mobile/screens/login_screen.dart';
import 'package:medicare_mobile/screens/patient_detail_screen.dart';

class PatientListScreen extends StatefulWidget {
  const PatientListScreen({super.key});

  @override
  State<PatientListScreen> createState() => _PatientListScreenState();
}

class _PatientListScreenState extends State<PatientListScreen> {
  final _searchCtrl = TextEditingController();
  List<Patient> _patients = [];
  bool _loading = true;
  String? _error;
  Timer? _debounce;

  @override
  void initState() {
    super.initState();
    _fetchPatients();
  }

  @override
  void dispose() {
    _searchCtrl.dispose();
    _debounce?.cancel();
    super.dispose();
  }

  Future<void> _fetchPatients({String? search}) async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final api = context.read<ApiService>();
      final patients = await api.getPatients(search: search);
      if (mounted) setState(() => _patients = patients);
    } on ApiException catch (e) {
      if (e.statusCode == 401) {
        await context.read<AuthProvider>().logout();
        if (!mounted) return;
        Navigator.of(context).pushReplacement(MaterialPageRoute(builder: (_) => const LoginScreen()));
        return;
      }
      if (mounted) setState(() => _error = 'Error al cargar pacientes');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _onSearchChanged(String value) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 350), () {
      if (value.length >= 2) _fetchPatients(search: value);
      if (value.isEmpty) _fetchPatients();
    });
  }

  Future<void> _logout() async {
    final confirmed = await AppConfirmDialog.show(
      context,
      title: 'Cerrar sesión',
      message: '¿Estás seguro de que querés salir?',
      confirmLabel: 'Salir',
      confirmColor: Colors.red,
    );
    if (!confirmed || !mounted) return;
    await context.read<AuthProvider>().logout();
    if (!mounted) return;
    Navigator.of(context).pushReplacement(MaterialPageRoute(builder: (_) => const LoginScreen()));
  }

  @override
  Widget build(BuildContext context) {
    final session = context.watch<AuthProvider>();
    final offline = context.watch<OfflineProvider>();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Pacientes'),
        actions: [
          if (!offline.isOnline)
            Padding(
              padding: const EdgeInsets.only(right: 4),
              child: Icon(Icons.wifi_off, size: 18, color: Colors.orange.shade400),
            ),
          if (offline.pendingSync > 0)
            Padding(
              padding: const EdgeInsets.only(right: 4),
              child: Badge(
                label: Text('${offline.pendingSync}'),
                child: Icon(Icons.sync, size: 18, color: Colors.orange.shade400),
              ),
            ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 4),
            child: Chip(
              visualDensity: VisualDensity.compact,
              label: Text(session.session?.rol.toUpperCase() ?? '', style: const TextStyle(fontSize: 10)),
            ),
          ),
          IconButton(icon: const Icon(Icons.logout), onPressed: _logout, tooltip: 'Cerrar sesión'),
        ],
      ),
      body: Column(
        children: [
          ConnectivityBanner(isOnline: offline.isOnline, pendingSync: offline.pendingSync),
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 8, 12, 4),
            child: TextField(
              controller: _searchCtrl,
              decoration: InputDecoration(
                hintText: 'Buscar por nombre o DNI...',
                prefixIcon: const Icon(Icons.search),
                suffixIcon: _searchCtrl.text.isNotEmpty
                    ? IconButton(
                        icon: const Icon(Icons.clear),
                        onPressed: () => _searchCtrl.clear(),
                      )
                    : null,
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
              ),
              onChanged: _onSearchChanged,
            ),
          ),
          Expanded(
            child: _loading
                ? const AppLoadingShimmer()
                : _error != null
                    ? AppError(message: _error!, onRetry: () => _fetchPatients())
                    : _patients.isEmpty
                        ? const EmptyState(
                            icon: Icons.person_search,
                            title: 'No se encontraron pacientes',
                            subtitle: 'Probá con otro término de búsqueda',
                          )
                        : RefreshIndicator(
                            onRefresh: () => _fetchPatients(search: _searchCtrl.text.isNotEmpty ? _searchCtrl.text : null),
                            child: ListView.builder(
                              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                              itemCount: _patients.length,
                              itemBuilder: (context, index) {
                                final p = _patients[index];
                                return _PatientCard(
                                  patient: p,
                                  onTap: () => Navigator.of(context).push(
                                    MaterialPageRoute(
                                      builder: (_) => PatientDetailScreen(patient: p),
                                    ),
                                  ),
                                );
                              },
                            ),
                          ),
          ),
        ],
      ),
    );
  }
}

class _PatientCard extends StatelessWidget {
  final Patient patient;
  final VoidCallback onTap;
  const _PatientCard({required this.patient, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 4),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              CircleAvatar(
                radius: 22,
                backgroundColor: theme.colorScheme.primaryContainer,
                child: Text(
                  '${patient.nombre[0]}${patient.apellido[0]}'.toUpperCase(),
                  style: TextStyle(
                    fontWeight: FontWeight.w600,
                    color: theme.colorScheme.onPrimaryContainer,
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(patient.nombreCompleto,
                      style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15)),
                    const SizedBox(height: 2),
                    Text('${patient.dni}  ·  ${patient.obraSocial ?? "Sin OS"}',
                      style: TextStyle(color: Colors.grey.shade600, fontSize: 13)),
                  ],
                ),
              ),
              Icon(Icons.chevron_right, color: Colors.grey.shade400),
            ],
          ),
        ),
      ),
    );
  }
}
