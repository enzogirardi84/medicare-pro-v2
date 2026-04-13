import 'package:flutter/foundation.dart';

/// Escala de texto global; se sincroniza con [AppSettings] al arrancar y al guardar en ajustes.
final appTextScaleNotifier = ValueNotifier<double>(1.0);
