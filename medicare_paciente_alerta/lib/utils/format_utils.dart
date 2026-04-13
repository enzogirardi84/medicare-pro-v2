/// Formato local legible sin dependencia intl.
String formatearFechaHoraLocal(String? iso) {
  if (iso == null || iso.trim().isEmpty) return '';
  final parsed = DateTime.tryParse(iso.trim());
  if (parsed == null) return iso.trim();
  final l = parsed.toLocal();
  final d = '${l.day.toString().padLeft(2, '0')}/${l.month.toString().padLeft(2, '0')}/${l.year}';
  final t = '${l.hour.toString().padLeft(2, '0')}:${l.minute.toString().padLeft(2, '0')}';
  return '$d $t';
}
