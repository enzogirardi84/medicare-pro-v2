import 'dart:ui';

import 'package:flutter/material.dart';

/// Permite arrastrar listas con mouse / trackpad (util en escritorio o web).
class MedicareScrollBehavior extends MaterialScrollBehavior {
  const MedicareScrollBehavior();

  @override
  Set<PointerDeviceKind> get dragDevices => {
        PointerDeviceKind.touch,
        PointerDeviceKind.mouse,
        PointerDeviceKind.stylus,
        PointerDeviceKind.trackpad,
      };
}
