import 'package:flutter_test/flutter_test.dart';
import 'package:medicare_paciente_alerta/services/pending_alert_queue.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  test('encolar incrementa cantidad y persiste campos', () async {
    expect(await PendingAlertQueue.cantidad(), 0);
    await PendingAlertQueue.encolar(
      sintomaLabel: 'Fiebre',
      nivelUrgencia: 'Verde',
      latitud: -34.6,
      longitud: -58.4,
      precisionM: 12,
    );
    expect(await PendingAlertQueue.cantidad(), 1);
    final todos = await PendingAlertQueue.leerTodos();
    expect(todos, hasLength(1));
    expect(todos.single['sintoma'], 'Fiebre');
    expect(todos.single['nivel_urgencia'], 'Verde');
    expect(todos.single['latitud'], -34.6);
    expect(todos.single['longitud'], -58.4);
    expect(todos.single['precision_m'], 12);
    expect(todos.single['enqueued_at'], isNotEmpty);
  });

  test('respeta maxItems eliminando las mas antiguas', () async {
    for (var i = 0; i < 20; i++) {
      await PendingAlertQueue.encolar(
        sintomaLabel: 's$i',
        nivelUrgencia: 'Verde',
      );
    }
    final todos = await PendingAlertQueue.leerTodos();
    expect(todos, hasLength(PendingAlertQueue.maxItems));
    expect(todos.first['sintoma'], 's5');
    expect(todos.last['sintoma'], 's19');
  });

  test('limpiar vacia la cola', () async {
    await PendingAlertQueue.encolar(sintomaLabel: 'x', nivelUrgencia: 'Rojo');
    await PendingAlertQueue.limpiar();
    expect(await PendingAlertQueue.cantidad(), 0);
    expect(await PendingAlertQueue.leerTodos(), isEmpty);
  });

  test('JSON corrupto devuelve lista vacia sin tirar', () async {
    SharedPreferences.setMockInitialValues({
      'pending_alerts_queue_v1': '{no json',
    });
    expect(await PendingAlertQueue.leerTodos(), isEmpty);
  });
}
