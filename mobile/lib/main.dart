import 'package:flutter/material.dart';

import 'core/di/service_locator.dart';
import 'core/theme/app_theme.dart';
import 'features/auth/presentation/login_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const SwimLapApp());
}

class SwimLapApp extends StatelessWidget {
  const SwimLapApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'SwimLap',
      theme: AppTheme.light,
      debugShowCheckedModeBanner: false,
      // MVP always starts at login. Session restoration is wired in
      // AuthRepository.restoreSession(); a splash gate is deferred (see docs).
      home: const LoginScreen(),
    );
  }
}
