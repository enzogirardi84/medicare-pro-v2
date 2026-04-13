import '../config/app_settings.dart';
import '../models/triage_symptom.dart';
import 'alerta_paciente_edge_service.dart';
import 'pending_alert_queue.dart';

/// Reenvia la cola local con la configuracion actual.
Future<({int enviadas, int fallidas})> procesarColaPendiente() async {
  final list = await PendingAlertQueue.leerTodos();
  if (list.isEmpty) {
    return (enviadas: 0, fallidas: 0);
  }

  final pacienteId = (await AppSettings.getPatientToken()).trim();
  final empresa = (await AppSettings.getEmpresaClave()).trim();
  final url = (await AppSettings.getSupabaseProjectUrl()).trim();
  final anon = (await AppSettings.getSupabaseAnonKey()).trim();
  final secret = (await AppSettings.getIngestSecret()).trim();

  if (pacienteId.isEmpty || empresa.isEmpty || url.isEmpty || anon.isEmpty || secret.isEmpty) {
    return (enviadas: 0, fallidas: list.length);
  }

  final svc = AlertaPacienteEdgeService(
    projectUrl: url,
    anonKey: anon,
    ingestSecret: secret,
  );

  final remaining = <Map<String, dynamic>>[];
  var enviadas = 0;
  Map<String, dynamic>? ultimoEnviadoOk;

  for (final row in list) {
    final sintoma = str(row['sintoma']);
    final nivel = triageNivelDesdeEtiquetaApi(str(row['nivel_urgencia']));
    final lat = (row['latitud'] as num?)?.toDouble();
    final lon = (row['longitud'] as num?)?.toDouble();
    final prec = (row['precision_m'] as num?)?.toDouble();

    final res = await svc.enviar(
      pacienteId: pacienteId,
      sintomaLabel: sintoma,
      nivel: nivel,
      empresaClave: empresa,
      latitud: lat,
      longitud: lon,
      precisionM: prec,
    );

    if (res.ok) {
      enviadas++;
      ultimoEnviadoOk = row;
    } else {
      remaining.add(row);
    }
  }

  await PendingAlertQueue.reemplazar(remaining);

  if (ultimoEnviadoOk != null) {
    final s = str(ultimoEnviadoOk['sintoma']);
    final nivelTxt = str(ultimoEnviadoOk['nivel_urgencia']);
    final etiquetaNivel =
        nivelTxt.isNotEmpty ? nivelTxt : triageNivelDesdeEtiquetaApi(null).apiLabel;
    await AppSettings.setLastAlertSent(
      atIso: DateTime.now().toLocal().toIso8601String(),
      summary: '$s ($etiquetaNivel)',
    );
  }

  return (enviadas: enviadas, fallidas: remaining.length);
}

String str(dynamic v) => v == null ? '' : v.toString().trim();
