import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

class ApiService {
  static const String baseUrl = 'http://localhost:8000/api/v1';
  static String? _token;

  static Future<String?> get token async {
    if (_token != null) return _token;
    final prefs = await SharedPreferences.getInstance();
    _token = prefs.getString('auth_token');
    return _token;
  }

  static Future<void> setToken(String token) async {
    _token = token;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('auth_token', token);
  }

  static Future<void> clearToken() async {
    _token = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('auth_token');
  }

  static Future<Map<String, String>> _headers() async {
    final t = await token;
    return {
      'Content-Type': 'application/json',
      if (t != null) 'Authorization': 'Bearer $t',
    };
  }

  static Future<Map<String, dynamic>> login(String email, String password) async {
    final response = await http.post(
      Uri.parse('$baseUrl/auth/login'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'email': email, 'password': password}),
    );
    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      await setToken(data['access_token']);
      return data;
    }
    throw Exception('Login failed: ${response.body}');
  }

  static Future<Map<String, dynamic>> register(
      String email, String password, String? name) async {
    final response = await http.post(
      Uri.parse('$baseUrl/auth/register'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'email': email,
        'password': password,
        if (name != null) 'full_name': name,
      }),
    );
    if (response.statusCode == 201) {
      return jsonDecode(response.body);
    }
    throw Exception('Registration failed: ${response.body}');
  }

  static Future<Map<String, dynamic>> getDashboard() async {
    final response = await http.get(
      Uri.parse('$baseUrl/trading/dashboard'),
      headers: await _headers(),
    );
    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }
    throw Exception('Failed to load dashboard');
  }

  static Future<List<dynamic>> getSignals() async {
    final response = await http.get(
      Uri.parse('$baseUrl/trading/signals'),
      headers: await _headers(),
    );
    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }
    throw Exception('Failed to load signals');
  }

  static Future<List<dynamic>> getTrades({int limit = 50}) async {
    final response = await http.get(
      Uri.parse('$baseUrl/trading/trades?limit=$limit'),
      headers: await _headers(),
    );
    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }
    throw Exception('Failed to load trades');
  }

  static Future<Map<String, dynamic>> executeSignal(
      Map<String, dynamic> signal) async {
    final response = await http.post(
      Uri.parse('$baseUrl/trading/execute'),
      headers: await _headers(),
      body: jsonEncode(signal),
    );
    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }
    throw Exception('Failed to execute signal');
  }

  static Future<Map<String, dynamic>> getRiskStatus() async {
    final response = await http.get(
      Uri.parse('$baseUrl/trading/risk-status'),
      headers: await _headers(),
    );
    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }
    throw Exception('Failed to load risk status');
  }

  static Future<Map<String, dynamic>> getAIMetrics() async {
    final response = await http.get(
      Uri.parse('$baseUrl/ai/metrics'),
      headers: await _headers(),
    );
    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }
    throw Exception('Failed to load AI metrics');
  }

  static Future<Map<String, dynamic>> trainModel(
      {String symbol = 'EURUSD', String timeframe = 'H1'}) async {
    final response = await http.post(
      Uri.parse('$baseUrl/ai/train'),
      headers: await _headers(),
      body: jsonEncode({'symbol': symbol, 'timeframe': timeframe}),
    );
    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }
    throw Exception('Failed to train model');
  }

  static Future<Map<String, dynamic>> predict(
      {String symbol = 'EURUSD', String timeframe = 'H1'}) async {
    final response = await http.post(
      Uri.parse('$baseUrl/ai/predict?symbol=$symbol&timeframe=$timeframe'),
      headers: await _headers(),
    );
    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }
    throw Exception('Failed to get prediction');
  }

  static Future<void> startAutoTrading() async {
    await http.post(
      Uri.parse('$baseUrl/trading/auto-trade/start'),
      headers: await _headers(),
    );
  }

  static Future<void> stopAutoTrading() async {
    await http.post(
      Uri.parse('$baseUrl/trading/auto-trade/stop'),
      headers: await _headers(),
    );
  }

  static Future<List<dynamic>> getEquityHistory({int limit = 100}) async {
    final response = await http.get(
      Uri.parse('$baseUrl/equity/history?limit=$limit'),
      headers: await _headers(),
    );
    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    }
    throw Exception('Failed to load equity history');
  }
}
