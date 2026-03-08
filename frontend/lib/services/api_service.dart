import 'package:dio/dio.dart';
import '../config/app_config.dart';
import '../models/trade.dart';
import '../models/signal.dart';
import '../models/account.dart';

class ApiService {
  late final Dio _dio;

  ApiService() {
    _dio = Dio(BaseOptions(
      baseUrl: AppConfig.apiUrl,
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 15),
      headers: {'Content-Type': 'application/json'},
    ));

    _dio.interceptors.add(LogInterceptor(
      requestBody: false,
      responseBody: false,
      error: true,
    ));
  }

  // === Account ===

  Future<AccountSummary> getAccountSummary() async {
    final response = await _dio.get('/account/summary');
    return AccountSummary.fromJson(response.data as Map<String, dynamic>);
  }

  Future<List<EquitySnapshot>> getEquityCurve({int limit = 500}) async {
    final response = await _dio.get('/account/equity-curve', queryParameters: {'limit': limit});
    final list = response.data as List<dynamic>;
    return list.map((e) => EquitySnapshot.fromJson(e as Map<String, dynamic>)).toList();
  }

  // === Trades ===

  Future<List<Trade>> getTrades({
    int skip = 0,
    int limit = 50,
    String? status,
    String? symbol,
  }) async {
    final response = await _dio.get('/trades', queryParameters: {
      'skip': skip,
      'limit': limit,
      if (status != null) 'status': status,
      if (symbol != null) 'symbol': symbol,
    });
    final list = response.data as List<dynamic>;
    return list.map((e) => Trade.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<List<Trade>> getOpenTrades() async {
    final response = await _dio.get('/trades/open');
    final list = response.data as List<dynamic>;
    return list.map((e) => Trade.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<TradeStats> getTradeStats() async {
    final response = await _dio.get('/trades/stats');
    return TradeStats.fromJson(response.data as Map<String, dynamic>);
  }

  // === Signals ===

  Future<List<Signal>> getSignals({
    int skip = 0,
    int limit = 50,
    String? status,
    double? minConfidence,
  }) async {
    final response = await _dio.get('/signals', queryParameters: {
      'skip': skip,
      'limit': limit,
      if (status != null) 'status': status,
      if (minConfidence != null) 'min_confidence': minConfidence,
    });
    final list = response.data as List<dynamic>;
    return list.map((e) => Signal.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<List<Signal>> getActiveSignals() async {
    final response = await _dio.get('/signals/active');
    final list = response.data as List<dynamic>;
    return list.map((e) => Signal.fromJson(e as Map<String, dynamic>)).toList();
  }

  // === AI ===

  Future<Map<String, dynamic>> getModelInfo() async {
    final response = await _dio.get('/ai/model/info');
    return response.data as Map<String, dynamic>;
  }

  Future<List<Map<String, dynamic>>> getConfidenceHistory({int limit = 100}) async {
    final response = await _dio.get('/ai/confidence/history', queryParameters: {'limit': limit});
    return (response.data as List<dynamic>).cast<Map<String, dynamic>>();
  }

  // === Health ===
  Future<bool> checkHealth() async {
    try {
      final response = await _dio.get(
        '/health',
        options: Options(baseUrl: AppConfig.baseUrl),
      );
      return response.statusCode == 200;
    } catch (_) {
      return false;
    }
  }
}
