import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:medicare_mobile/services/api_service.dart';
import 'package:medicare_mobile/services/auth_service.dart';
import 'package:medicare_mobile/services/offline_service.dart';
import 'package:medicare_mobile/providers/app_providers.dart';
import 'package:medicare_mobile/main.dart' as app;

void main() {
  testWidgets('App renders splash screen', (WidgetTester tester) async {
    final api = ApiService(baseUrl: 'http://test.local');
    final auth = AuthService(api: api);
    final offline = OfflineService(api: api);

    await tester.pumpWidget(
      MultiProvider(
        providers: [
          Provider<ApiService>.value(value: api),
          ChangeNotifierProvider<AuthProvider>(create: (_) => AuthProvider(auth)),
          ChangeNotifierProvider<OfflineProvider>(create: (_) => OfflineProvider(offline)),
        ],
        child: const app.MedicareApp(),
      ),
    );

    await tester.pump(const Duration(seconds: 1));
    await tester.pump(const Duration(seconds: 1));

    expect(find.text('MediCare Pro'), findsOneWidget);
    expect(find.text('v1.0.0'), findsOneWidget);
  });
}
