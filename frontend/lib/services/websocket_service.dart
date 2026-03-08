import 'dart:async';
import 'dart:convert';
import 'package:web_socket_channel/web_socket_channel.dart';

class WebSocketService {
  static const String wsBaseUrl = 'ws://localhost:8000';
  WebSocketChannel? _dashboardChannel;
  WebSocketChannel? _signalsChannel;
  WebSocketChannel? _tradesChannel;

  final _dashboardController = StreamController<Map<String, dynamic>>.broadcast();
  final _signalsController = StreamController<Map<String, dynamic>>.broadcast();
  final _tradesController = StreamController<Map<String, dynamic>>.broadcast();

  Stream<Map<String, dynamic>> get dashboardStream => _dashboardController.stream;
  Stream<Map<String, dynamic>> get signalsStream => _signalsController.stream;
  Stream<Map<String, dynamic>> get tradesStream => _tradesController.stream;

  void connectDashboard() {
    _dashboardChannel = WebSocketChannel.connect(
      Uri.parse('$wsBaseUrl/ws/dashboard'),
    );
    _dashboardChannel!.stream.listen(
      (data) {
        final json = jsonDecode(data);
        _dashboardController.add(json);
      },
      onError: (error) {
        Future.delayed(const Duration(seconds: 5), connectDashboard);
      },
      onDone: () {
        Future.delayed(const Duration(seconds: 5), connectDashboard);
      },
    );
  }

  void connectSignals() {
    _signalsChannel = WebSocketChannel.connect(
      Uri.parse('$wsBaseUrl/ws/signals'),
    );
    _signalsChannel!.stream.listen(
      (data) {
        final json = jsonDecode(data);
        _signalsController.add(json);
      },
      onError: (error) {
        Future.delayed(const Duration(seconds: 5), connectSignals);
      },
    );
  }

  void connectTrades() {
    _tradesChannel = WebSocketChannel.connect(
      Uri.parse('$wsBaseUrl/ws/trades'),
    );
    _tradesChannel!.stream.listen(
      (data) {
        final json = jsonDecode(data);
        _tradesController.add(json);
      },
      onError: (error) {
        Future.delayed(const Duration(seconds: 5), connectTrades);
      },
    );
  }

  void connectAll() {
    connectDashboard();
    connectSignals();
    connectTrades();
  }

  void dispose() {
    _dashboardChannel?.sink.close();
    _signalsChannel?.sink.close();
    _tradesChannel?.sink.close();
    _dashboardController.close();
    _signalsController.close();
    _tradesController.close();
  }
}
