import 'dart:async';
import 'package:flutter/foundation.dart';
import '../models/trade_models.dart';
import '../services/api_service.dart';
import '../services/websocket_service.dart';

class TradingProvider extends ChangeNotifier {
  DashboardData? _dashboard;
  List<TradeSignal> _signals = [];
  List<TradeHistory> _trades = [];
  bool _isLoading = false;
  bool _autoTrading = false;
  String? _error;
  final WebSocketService _wsService = WebSocketService();

  DashboardData? get dashboard => _dashboard;
  List<TradeSignal> get signals => _signals;
  List<TradeHistory> get trades => _trades;
  bool get isLoading => _isLoading;
  bool get autoTrading => _autoTrading;
  String? get error => _error;

  void initWebSocket() {
    _wsService.connectAll();
    _wsService.dashboardStream.listen((data) {
      if (data['type'] == 'dashboard_update') {
        _dashboard = DashboardData.fromJson(data);
        notifyListeners();
      }
    });
    _wsService.signalsStream.listen((data) {
      if (data['type'] == 'signals_update') {
        _signals = (data['signals'] as List)
            .map((s) => TradeSignal.fromJson(s))
            .toList();
        notifyListeners();
      }
    });
  }

  Future<void> loadDashboard() async {
    _isLoading = true;
    notifyListeners();

    try {
      final data = await ApiService.getDashboard();
      _dashboard = DashboardData.fromJson(data);
      _error = null;
    } catch (e) {
      _error = e.toString();
    }

    _isLoading = false;
    notifyListeners();
  }

  Future<void> loadSignals() async {
    try {
      final data = await ApiService.getSignals();
      _signals = data.map((s) => TradeSignal.fromJson(s)).toList();
      _error = null;
    } catch (e) {
      _error = e.toString();
    }
    notifyListeners();
  }

  Future<void> loadTrades() async {
    try {
      final data = await ApiService.getTrades();
      _trades = data.map((t) => TradeHistory.fromJson(t)).toList();
      _error = null;
    } catch (e) {
      _error = e.toString();
    }
    notifyListeners();
  }

  Future<bool> executeSignal(TradeSignal signal) async {
    try {
      final result = await ApiService.executeSignal({
        'symbol': signal.symbol,
        'market_type': signal.marketType,
        'timeframe': signal.timeframe,
        'direction': signal.direction,
        'entry_price': signal.entryPrice,
        'stop_loss': signal.stopLoss,
        'take_profit_1': signal.tp1,
        'take_profit_2': signal.tp2,
        'take_profit_3': signal.tp3,
        'confidence': signal.confidence,
        'risk_reward': signal.riskReward,
        'strategy': signal.strategy,
      });
      return result['executed'] ?? false;
    } catch (e) {
      _error = e.toString();
      notifyListeners();
      return false;
    }
  }

  Future<void> toggleAutoTrading() async {
    try {
      if (_autoTrading) {
        await ApiService.stopAutoTrading();
      } else {
        await ApiService.startAutoTrading();
      }
      _autoTrading = !_autoTrading;
    } catch (e) {
      _error = e.toString();
    }
    notifyListeners();
  }

  @override
  void dispose() {
    _wsService.dispose();
    super.dispose();
  }
}
