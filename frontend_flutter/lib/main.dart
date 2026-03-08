import 'package:flutter/material.dart';

import 'screens/dashboard_screen.dart';
import 'services/api_service.dart';

void main() {
  runApp(const TradingDashboardApp());
}

class TradingDashboardApp extends StatelessWidget {
  const TradingDashboardApp({super.key});

  @override
  Widget build(BuildContext context) {
    const backendBaseUrl = String.fromEnvironment(
      'API_BASE_URL',
      defaultValue: 'http://localhost:8000',
    );
    return MaterialApp(
      title: 'AI Trading Dashboard',
      theme: ThemeData(useMaterial3: true, colorSchemeSeed: Colors.blue),
      home: DashboardScreen(
        apiService: ApiService(baseUrl: backendBaseUrl),
      ),
    );
  }
}
