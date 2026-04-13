import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'app_entry.dart';
import 'app_text_scale_notifier.dart';
import 'config/app_settings.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
  ]);
  appTextScaleNotifier.value = await AppSettings.getTextScaleFactor();
  runApp(const MedicarePacienteAlertaApp());
}

class MedicarePacienteAlertaApp extends StatelessWidget {
  const MedicarePacienteAlertaApp({super.key});

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<double>(
      valueListenable: appTextScaleNotifier,
      builder: (context, scale, _) {
        return MaterialApp(
          title: 'MediCare Alerta',
          debugShowCheckedModeBanner: false,
          theme: ThemeData(
            colorScheme: ColorScheme.fromSeed(
              seedColor: const Color(0xFF0D9488),
              brightness: Brightness.dark,
            ),
            useMaterial3: true,
          ),
          builder: (context, child) {
            final mq = MediaQuery.of(context);
            return MediaQuery(
              data: mq.copyWith(textScaler: TextScaler.linear(scale)),
              child: child ?? const SizedBox.shrink(),
            );
          },
          home: const AppEntry(),
        );
      },
    );
  }
}
