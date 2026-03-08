import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../models/dashboard_models.dart';
import '../services/api_service.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key, required this.apiService});

  final ApiService apiService;

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  DashboardModel? _dashboard;
  String _signalDirection = 'none';
  String _signalReason = 'No signal yet';
  String? _error;
  bool _loading = true;
  WebSocketChannel? _channel;
  StreamSubscription? _signalSubscription;

  @override
  void initState() {
    super.initState();
    _load();
    _subscribeSignals();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final data = await widget.apiService.fetchDashboard();
      setState(() {
        _dashboard = data;
        _signalDirection = data.liveSignal.direction;
        _signalReason = data.liveSignal.reason;
        _error = null;
      });
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  void _subscribeSignals() {
    _channel = widget.apiService.connectSignals();
    _signalSubscription = _channel!.stream.listen((message) {
      final data = jsonDecode(message as String) as Map<String, dynamic>;
      setState(() {
        _signalDirection = data['direction'] as String? ?? 'none';
        _signalReason = data['reason'] as String? ?? '';
      });
    });
  }

  @override
  void dispose() {
    _signalSubscription?.cancel();
    _channel?.sink.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('AI Trading Dashboard')),
      body: RefreshIndicator(
        onRefresh: _load,
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : _error != null
                ? ListView(
                    children: [
                      Padding(
                        padding: const EdgeInsets.all(16),
                        child: Text(_error!, style: const TextStyle(color: Colors.red)),
                      ),
                    ],
                  )
                : ListView(
                    padding: const EdgeInsets.all(12),
                    children: [
                      Card(
                        child: ListTile(
                          title: const Text('Equity'),
                          subtitle: Text(
                            _dashboard!.equity.isNotEmpty
                                ? _dashboard!.equity.last.equity.toStringAsFixed(2)
                                : 'N/A',
                          ),
                        ),
                      ),
                      Card(
                        child: ListTile(
                          title: const Text('AI Confidence'),
                          subtitle: Text(
                            (_dashboard!.aiConfidence * 100).toStringAsFixed(2) + '%',
                          ),
                        ),
                      ),
                      Card(
                        child: ListTile(
                          title: const Text('Live Signal'),
                          subtitle: Text('$_signalDirection\n$_signalReason'),
                        ),
                      ),
                      const SizedBox(height: 8),
                      const Text(
                        'Trade History',
                        style: TextStyle(fontWeight: FontWeight.bold),
                      ),
                      const SizedBox(height: 8),
                      ..._dashboard!.tradeHistory.map(
                        (trade) => Card(
                          child: ListTile(
                            title: Text('${trade.market.toUpperCase()} ${trade.symbol}'),
                            subtitle: Text(
                              '${trade.side.toUpperCase()} @ ${trade.entryPrice.toStringAsFixed(4)}',
                            ),
                            trailing: Text(
                              '${(trade.confidence * 100).toStringAsFixed(0)}%',
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
      ),
    );
  }
}
