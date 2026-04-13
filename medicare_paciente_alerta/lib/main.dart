import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'app_entry.dart';
import 'app_scroll_behavior.dart';
import 'app_text_scale_notifier.dart';
import 'app_theme_notifier.dart';
import 'config/app_settings.dart';
import 'l10n/app_strings.dart';
import 'theme/app_theme.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
  ]);
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarBrightness: Brightness.dark,
      statusBarIconBrightness: Brightness.light,
      systemNavigationBarColor: Color(0xFF0B1120),
      systemNavigationBarIconBrightness: Brightness.light,
    ),
  );
  appTextScaleNotifier.value = await AppSettings.getTextScaleFactor();
  appHighContrastNotifier.value = await AppSettings.getHighContrast();
  runApp(const MedicarePacienteAlertaApp());
}

class MedicarePacienteAlertaApp extends StatelessWidget {
  const MedicarePacienteAlertaApp({super.key});

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<double>(
      valueListenable: appTextScaleNotifier,
      builder: (context, scale, _) {
        return ValueListenableBuilder<bool>(
          valueListenable: appHighContrastNotifier,
          builder: (context, highContrast, _) {
            return MaterialApp(
              title: AppStrings.appTitle,
              debugShowCheckedModeBanner: false,
              scrollBehavior: const MedicareScrollBehavior(),
              theme: buildMedicareTheme(highContrast: highContrast),
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
      },
    );
  }
}
