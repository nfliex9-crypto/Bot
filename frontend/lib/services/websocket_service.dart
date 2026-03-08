import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import '../config/app_config.dart';
import '../models/signal.dart';

enum WsStatus { disconnected, connecting, connected, error }

class WebSocketService extends ChangeNotifier {
  WebSocketChannel? _channel;
  WsStatus _status = WsStatus.disconnected;
  Timer? _reconnectTimer;
  Timer? _pingTimer;

  final List<Signal> _liveSignals = [];
  final StreamController<Signal> _signalController = StreamController.broadcast();

  WsStatus get status => _status;
  List<Signal> get liveSignals => List.unmodifiable(_liveSignals);
  Stream<Signal> get signalStream => _signalController.stream;

  void connect() {
    if (_status == WsStatus.connected || _status == WsStatus.connecting) return;
    _setStatus(WsStatus.connecting);

    try {
      _channel = WebSocketChannel.connect(Uri.parse(AppConfig.wsUrl));
      _setStatus(WsStatus.connected);

      _channel!.stream.listen(
        _onMessage,
        onError: _onError,
        onDone: _onDone,
      );

      // Start ping timer
      _pingTimer = Timer.periodic(const Duration(seconds: 25), (_) {
        _send({'type': 'ping'});
      });
    } catch (e) {
      debugPrint('WebSocket connect error: $e');
      _setStatus(WsStatus.error);
      _scheduleReconnect();
    }
  }

  void disconnect() {
    _pingTimer?.cancel();
    _reconnectTimer?.cancel();
    _channel?.sink.close();
    _channel = null;
    _setStatus(WsStatus.disconnected);
  }

  void _onMessage(dynamic message) {
    try {
      final Map<String, dynamic> data = jsonDecode(message as String);
      final type = data['type'] as String?;

      if (type == 'signal') {
        final signalData = data['data'] as Map<String, dynamic>;
        // Convert live signal format to Signal model
        final signal = _parseLiveSignal(signalData);
        if (signal != null) {
          _liveSignals.insert(0, signal);
          if (_liveSignals.length > 50) _liveSignals.removeLast();
          _signalController.add(signal);
          notifyListeners();
        }
      } else if (type == 'heartbeat') {
        debugPrint('WS heartbeat received');
      }
    } catch (e) {
      debugPrint('WS message parse error: $e');
    }
  }

  Signal? _parseLiveSignal(Map<String, dynamic> data) {
    try {
      return Signal(
        id: DateTime.now().millisecondsSinceEpoch,
        symbol: data['symbol'] as String,
        market: data['market'] as String,
        timeframe: data['timeframe'] as String? ?? 'H1',
        direction: data['direction'] as String,
        status: 'ACTIVE',
        entryZoneLow: data['entry_zone_low'] != null ? (data['entry_zone_low'] as num).toDouble() : null,
        entryZoneHigh: data['entry_zone_high'] != null ? (data['entry_zone_high'] as num).toDouble() : null,
        stopLoss: data['stop_loss'] != null ? (data['stop_loss'] as num).toDouble() : null,
        tp1: data['tp1'] != null ? (data['tp1'] as num).toDouble() : null,
        tp2: data['tp2'] != null ? (data['tp2'] as num).toDouble() : null,
        tp3: data['tp3'] != null ? (data['tp3'] as num).toDouble() : null,
        liquiditySweepDetected: data['liquidity_sweep_detected'] as bool? ?? false,
        bosDetected: data['bos_detected'] as bool? ?? false,
        pullbackConfirmed: data['pullback_confirmed'] as bool? ?? false,
        confidenceScore: data['confidence_score'] != null ? (data['confidence_score'] as num).toDouble() : null,
        marketStructure: data['market_structure'] as String?,
        session: data['session'] as String?,
        createdAt: DateTime.now(),
      );
    } catch (_) {
      return null;
    }
  }

  void _onError(dynamic error) {
    debugPrint('WebSocket error: $error');
    _setStatus(WsStatus.error);
    _scheduleReconnect();
  }

  void _onDone() {
    debugPrint('WebSocket closed');
    if (_status != WsStatus.disconnected) {
      _setStatus(WsStatus.error);
      _scheduleReconnect();
    }
  }

  void _scheduleReconnect() {
    _pingTimer?.cancel();
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(const Duration(seconds: 5), connect);
  }

  void _send(Map<String, dynamic> data) {
    if (_status == WsStatus.connected) {
      try {
        _channel?.sink.add(jsonEncode(data));
      } catch (_) {}
    }
  }

  void _setStatus(WsStatus status) {
    _status = status;
    notifyListeners();
  }

  @override
  void dispose() {
    disconnect();
    _signalController.close();
    super.dispose();
  }
}
