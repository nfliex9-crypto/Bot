import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:web_socket_channel/web_socket_channel.dart';

import '../models/dashboard_models.dart';

class ApiService {
  ApiService({required this.baseUrl});

  final String baseUrl;

  Uri get _dashboardUri => Uri.parse('$baseUrl/api/v1/dashboard');

  Future<DashboardModel> fetchDashboard() async {
    final response = await http.get(_dashboardUri);
    if (response.statusCode >= 400) {
      throw Exception('Dashboard request failed: ${response.statusCode}');
    }
    return DashboardModel.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  WebSocketChannel connectSignals() {
    final wsUrl = baseUrl.replaceFirst('http', 'ws');
    return WebSocketChannel.connect(Uri.parse('$wsUrl/ws/signals'));
  }
}
