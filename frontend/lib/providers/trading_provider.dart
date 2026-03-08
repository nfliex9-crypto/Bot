import 'dart:async';
import 'package:flutter/foundation.dart';
import '../models/account.dart';
import '../models/trade.dart';
import '../models/signal.dart';
import '../services/api_service.dart';

class TradingProvider extends ChangeNotifier {
  final ApiService _api;

  AccountSummary _account = AccountSummary.empty();
  TradeStats _stats = TradeStats.empty();
  List<Trade> _openTrades = [];
  List<Trade> _tradeHistory = [];
  List<Signal> _activeSignals = [];
  List<EquitySnapshot> _equityCurve = [];
  Map<String, dynamic> _modelInfo = {};
  List<Map<String, dynamic>> _confidenceHistory = [];

  bool _isLoading = false;
  String? _error;

  Timer? _accountTimer;
  Timer? _signalTimer;
  Timer? _equityTimer;

  TradingProvider(this._api);

  // Getters
  AccountSummary get account => _account;
  TradeStats get stats => _stats;
  List<Trade> get openTrades => _openTrades;
  List<Trade> get tradeHistory => _tradeHistory;
  List<Signal> get activeSignals => _activeSignals;
  List<EquitySnapshot> get equityCurve => _equityCurve;
  Map<String, dynamic> get modelInfo => _modelInfo;
  List<Map<String, dynamic>> get confidenceHistory => _confidenceHistory;
  bool get isLoading => _isLoading;
  String? get error => _error;

  void startAutoRefresh() {
    loadAll();
    _accountTimer = Timer.periodic(const Duration(seconds: 30), (_) => _refreshAccount());
    _signalTimer = Timer.periodic(const Duration(seconds: 15), (_) => _refreshSignals());
    _equityTimer = Timer.periodic(const Duration(minutes: 2), (_) => _refreshEquity());
  }

  void stopAutoRefresh() {
    _accountTimer?.cancel();
    _signalTimer?.cancel();
    _equityTimer?.cancel();
  }

  Future<void> loadAll() async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    await Future.wait([
      _refreshAccount(),
      _refreshSignals(),
      _refreshEquity(),
      _refreshTrades(),
      _refreshModelInfo(),
    ]);

    _isLoading = false;
    notifyListeners();
  }

  Future<void> _refreshAccount() async {
    try {
      _account = await _api.getAccountSummary();
      _stats = await _api.getTradeStats();
      notifyListeners();
    } catch (e) {
      _error = 'Failed to load account: $e';
      notifyListeners();
    }
  }

  Future<void> _refreshSignals() async {
    try {
      _activeSignals = await _api.getActiveSignals();
      notifyListeners();
    } catch (e) {
      debugPrint('Signal refresh error: $e');
    }
  }

  Future<void> _refreshEquity() async {
    try {
      _equityCurve = await _api.getEquityCurve(limit: 200);
      notifyListeners();
    } catch (e) {
      debugPrint('Equity refresh error: $e');
    }
  }

  Future<void> _refreshTrades() async {
    try {
      _openTrades = await _api.getOpenTrades();
      _tradeHistory = await _api.getTrades(status: 'CLOSED', limit: 100);
      notifyListeners();
    } catch (e) {
      debugPrint('Trades refresh error: $e');
    }
  }

  Future<void> _refreshModelInfo() async {
    try {
      _modelInfo = await _api.getModelInfo();
      _confidenceHistory = await _api.getConfidenceHistory(limit: 50);
      notifyListeners();
    } catch (e) {
      debugPrint('Model info refresh error: $e');
    }
  }

  void addLiveSignal(Signal signal) {
    _activeSignals.insert(0, signal);
    if (_activeSignals.length > 20) _activeSignals.removeLast();
    notifyListeners();
  }

  @override
  void dispose() {
    stopAutoRefresh();
    super.dispose();
  }
}
