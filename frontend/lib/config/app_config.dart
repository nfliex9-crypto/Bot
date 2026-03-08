class AppConfig {
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://localhost:8000',
  );

  static String get apiUrl => '$baseUrl/api/v1';
  static String get wsUrl => baseUrl.replaceFirst('http', 'ws') + '/ws';

  // Refresh intervals
  static const Duration signalRefreshInterval = Duration(seconds: 15);
  static const Duration accountRefreshInterval = Duration(seconds: 30);
  static const Duration equityRefreshInterval = Duration(minutes: 1);
}
