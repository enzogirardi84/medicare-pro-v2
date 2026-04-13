import 'package:flutter_test/flutter_test.dart';
import 'package:medicare_paciente_alerta/services/pending_alert_queue.dart';
import 'package:medicare_paciente_alerta/services/pending_alerts_processor.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  test('cola vacia no envia ni falla', () async {
    final r = await procesarColaPendiente();
    expect(r.enviadas, 0);
    expect(r.fallidas, 0);
  });

  test('sin configuracion completa cuenta todo como fallido', () async {
    await PendingAlertQueue.encolar(
      sintomaLabel: 'Fiebre',
      nivelUrgencia: 'Verde',
    );
    final r = await procesarColaPendiente();
    expect(r.enviadas, 0);
    expect(r.fallidas, 1);
    expect(await PendingAlertQueue.cantidad(), 1);
  });
}
