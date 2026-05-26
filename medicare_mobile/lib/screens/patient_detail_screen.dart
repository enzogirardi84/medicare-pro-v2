import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import 'package:medicare_mobile/models/patient.dart';
import 'package:medicare_mobile/providers/app_providers.dart';
import 'package:medicare_mobile/screens/evolution_form_screen.dart';
import 'package:medicare_mobile/screens/vitals_form_screen.dart';

class PatientDetailScreen extends StatelessWidget {
  final Patient patient;
  const PatientDetailScreen({super.key, required this.patient});

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final canEdit = auth.isAdmin || auth.isMedico;

    return Scaffold(
      appBar: AppBar(title: Text(patient.nombreCompleto)),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _InfoCard(patient: patient),
          const SizedBox(height: 16),
          if (canEdit) ...[
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: () => Navigator.of(context).push(
                  MaterialPageRoute(builder: (_) => EvolutionFormScreen(patientId: patient.id)),
                ),
                icon: const Icon(Icons.edit_note),
                label: const Text('Nueva evolución'),
              ),
            ),
            const SizedBox(height: 10),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: () => Navigator.of(context).push(
                  MaterialPageRoute(builder: (_) => VitalsFormScreen(patientId: patient.id)),
                ),
                icon: const Icon(Icons.monitor_heart_outlined),
                label: const Text('Registrar signos vitales'),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _InfoCard extends StatelessWidget {
  final Patient patient;
  const _InfoCard({required this.patient});

  String _calcularEdad(String dateStr) {
    try {
      final birth = DateFormat('yyyy-MM-dd').parse(dateStr);
      final now = DateTime.now();
      int edad = now.year - birth.year;
      if (now.month < birth.month || (now.month == birth.month && now.day < birth.day)) {
        edad--;
      }
      return '$edad años';
    } catch (_) {
      return dateStr;
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final edad = _calcularEdad(patient.fechaNacimiento);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                CircleAvatar(
                  radius: 28,
                  backgroundColor: theme.colorScheme.primaryContainer,
                  child: Text(
                    '${patient.nombre[0]}${patient.apellido[0]}'.toUpperCase(),
                    style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: theme.colorScheme.onPrimaryContainer),
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(patient.nombreCompleto, style: theme.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold)),
                      const SizedBox(height: 2),
                      Text(patient.dni, style: TextStyle(color: Colors.grey.shade600)),
                    ],
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: patient.estado == 'activo' ? Colors.green.shade50 : Colors.grey.shade100,
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(patient.estado, style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: patient.estado == 'activo' ? Colors.green.shade700 : Colors.grey.shade700,
                  )),
                ),
              ],
            ),
            const Divider(height: 28),
            _infoRow(Icons.calendar_today, 'Edad', edad),
            _infoRow(Icons.wc, 'Sexo', patient.sexo ?? 'No especificado'),
            _infoRow(Icons.email_outlined, 'Email', patient.email ?? '—'),
            _infoRow(Icons.phone_outlined, 'Teléfono', patient.telefono ?? '—'),
            _infoRow(Icons.health_and_safety, 'Obra social', patient.obraSocial ?? 'Sin cobertura'),
          ],
        ),
      ),
    );
  }

  Widget _infoRow(IconData icon, String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        children: [
          Icon(icon, size: 18, color: Colors.grey),
          const SizedBox(width: 12),
          SizedBox(width: 100, child: Text(label, style: TextStyle(color: Colors.grey.shade600, fontSize: 13))),
          Expanded(child: Text(value, style: const TextStyle(fontSize: 14))),
        ],
      ),
    );
  }
}
