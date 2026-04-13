import 'package:flutter/foundation.dart';

/// Alto contraste: se sincroniza con [AppSettings] al iniciar y desde Configuracion.
final ValueNotifier<bool> appHighContrastNotifier = ValueNotifier<bool>(false);
