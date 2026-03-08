import "dart:convert";

import "package:http/http.dart" as http;

import "models.dart";

class ApiService {
  ApiService({String? baseUrl})
      : baseUrl = baseUrl ??
            const String.fromEnvironment(
              "API_BASE_URL",
              defaultValue: "http://localhost:8000",
            );

  final String baseUrl;

  Future<EquityResponse> fetchEquity() async {
    final response = await http.get(Uri.parse("$baseUrl/dashboard/equity"));
    if (response.statusCode != 200) {
      throw Exception("Failed to load equity");
    }
    return EquityResponse.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
  }

  Future<List<Trade>> fetchTradeHistory() async {
    final response = await http.get(Uri.parse("$baseUrl/trades/history"));
    if (response.statusCode != 200) {
      throw Exception("Failed to load trade history");
    }
    final json = jsonDecode(response.body) as Map<String, dynamic>;
    return (json["items"] as List<dynamic>)
        .map((item) => Trade.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  Future<List<Signal>> fetchLiveSignals() async {
    final response = await http.get(Uri.parse("$baseUrl/signals/live"));
    if (response.statusCode != 200) {
      throw Exception("Failed to load signals");
    }
    final json = jsonDecode(response.body) as Map<String, dynamic>;
    return (json["items"] as List<dynamic>)
        .map((item) => Signal.fromJson(item as Map<String, dynamic>))
        .toList();
  }
}
