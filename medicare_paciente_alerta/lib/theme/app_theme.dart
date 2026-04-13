import 'package:flutter/material.dart';

ThemeData buildMedicareTheme({required bool highContrast}) {
  const seed = Color(0xFF0D9488);
  final base = ColorScheme.fromSeed(seedColor: seed, brightness: Brightness.dark);
  final scheme = highContrast
      ? base.copyWith(
          surface: const Color(0xFF000000),
          surfaceContainerHighest: const Color(0xFF1A1A1A),
          onSurface: Colors.white,
          onSurfaceVariant: const Color(0xFFE8E8E8),
          outline: const Color(0xFFFFFFFF),
          primary: const Color(0xFF2DD4BF),
          onPrimary: Colors.black,
        )
      : base;

  return ThemeData(
    colorScheme: scheme,
    useMaterial3: true,
    focusColor: highContrast ? scheme.primary : null,
    scaffoldBackgroundColor: highContrast ? Colors.black : const Color(0xFF0B1120),
    appBarTheme: AppBarTheme(
      centerTitle: true,
      elevation: 0,
      scrolledUnderElevation: 0,
      backgroundColor: highContrast ? Colors.black : null,
      foregroundColor: highContrast ? Colors.white : null,
    ),
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      backgroundColor: highContrast ? const Color(0xFF1A1A1A) : const Color(0xFF1E293B),
      contentTextStyle: const TextStyle(color: Color(0xFFE2E8F0)),
    ),
    progressIndicatorTheme: ProgressIndicatorThemeData(
      color: scheme.primary,
      circularTrackColor: highContrast ? Colors.white24 : const Color(0xFF334155),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
        minimumSize: const Size(48, 48),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        minimumSize: const Size(48, 48),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(
        minimumSize: const Size(48, 40),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: BorderSide(
          color: highContrast ? Colors.white70 : const Color(0xFF475569),
        ),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: BorderSide(
          color: highContrast ? Colors.white54 : const Color(0xFF475569),
        ),
      ),
    ),
    cardTheme: CardThemeData(
      elevation: highContrast ? 0 : 2,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: highContrast ? const BorderSide(color: Colors.white54, width: 1) : BorderSide.none,
      ),
    ),
    dialogTheme: DialogThemeData(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      backgroundColor: highContrast ? const Color(0xFF1A1A1A) : const Color(0xFF1E293B),
    ),
  );
}
