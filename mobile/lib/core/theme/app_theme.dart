import 'package:flutter/material.dart';

class AppTheme {
  static ThemeData get light => ThemeData(
        useMaterial3: true,
        colorSchemeSeed: const Color(0xFF0072CE), // pool blue
        appBarTheme: const AppBarTheme(centerTitle: false),
      );
}
