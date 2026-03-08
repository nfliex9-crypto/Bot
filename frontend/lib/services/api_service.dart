import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/dashboard_models.dart';

class ApiService {
  ApiService({http.Client? client}) : _client = client ?? http.Client();

  static const String baseUrl =
      String.fromEnvironment('API_BASE_URL', defaultValue: 'http://localhost:8000/api');

  final http.Client _client;

  Future<DashboardOverview> fetchDashboardOverview() async {
    final response = await _client.get(Uri.parse('$baseUrl/dashboard/overview'));
    if (response.statusCode != 200) {
      throw Exception('Failed to load dashboard overview');
    }
    return DashboardOverview.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
  }

  Future<List<EquitySnapshot>> fetchEquityCurve() async {
    final response = await _client.get(Uri.parse('$baseUrl/dashboard/equity'));
    if (response.statusCode != 200) {
      throw Exception('Failed to load equity curve');
    }
    final payload = jsonDecode(response.body) as List<dynamic>;
    return payload
        .map((item) => EquitySnapshot.fromJson(item as Map<String, dynamic>))
        .toList();
  }
}
