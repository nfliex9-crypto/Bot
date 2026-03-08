import 'package:flutter/material.dart';

import 'screens/dashboard_screen.dart';

void main() {
  runApp(const TradingDashboardApp());
}

class TradingDashboardApp extends StatelessWidget {
  const TradingDashboardApp({super.key});

  @override
  Widget build(BuildContext context) {
    const seed = Color(0xFF111827);
    return MaterialApp(
      title: 'AI Trading Dashboard',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: seed, brightness: Brightness.dark),
        scaffoldBackgroundColor: const Color(0xFF0F172A),
        cardTheme: const CardTheme(
          color: Color(0xFF111827),
          surfaceTintColor: Colors.transparent,
        ),
        appBarTheme: const AppBarTheme(
          backgroundColor: Color(0xFF111827),
          surfaceTintColor: Colors.transparent,
        ),
      ),
      home: const DashboardScreen(),
    );
  }
}
