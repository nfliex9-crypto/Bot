import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

void main() {
  runApp(const TradingApp());
}

class TradingApp extends StatelessWidget {
  const TradingApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'AI Trading Dashboard',
      theme: ThemeData(useMaterial3: true, colorSchemeSeed: Colors.blue),
      home: const DashboardScreen(),
    );
  }
}

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  final ApiService _api = ApiService(
    baseUrl: const String.fromEnvironment('API_URL', defaultValue: 'http://10.0.2.2:8000'),
  );

  List<dynamic> trades = [];
  List<dynamic> signals = [];
  List<dynamic> equity = [];
  bool loading = true;

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh() async {
    setState(() => loading = true);
    try {
      final results = await Future.wait([
        _api.getTrades(),
        _api.getSignals(),
        _api.getEquity(),
      ]);

      setState(() {
        trades = results[0];
        signals = results[1];
        equity = results[2];
      });
    } finally {
      setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final latestEquity = equity.isNotEmpty ? (equity.first['equity'] as num).toDouble() : 0.0;
    final avgConfidence = signals.isEmpty
        ? 0.0
        : signals.map((e) => (e['confidence'] as num).toDouble()).reduce((a, b) => a + b) /
            signals.length;

    return Scaffold(
      appBar: AppBar(
        title: const Text('AI Trading Dashboard'),
        actions: [
          IconButton(onPressed: _refresh, icon: const Icon(Icons.refresh)),
        ],
      ),
      body: loading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _refresh,
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  _MetricCard(title: 'Equity', value: latestEquity.toStringAsFixed(2)),
                  _MetricCard(
                    title: 'AI Confidence',
                    value: '${(avgConfidence * 100).toStringAsFixed(1)}%',
                  ),
                  _MetricCard(title: 'Live Signals', value: signals.length.toString()),
                  _MetricCard(title: 'Trade History', value: trades.length.toString()),
                  const SizedBox(height: 12),
                  const Text(
                    'Latest Signals',
                    style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18),
                  ),
                  const SizedBox(height: 8),
                  ...signals.take(10).map(
                    (s) => Card(
                      child: ListTile(
                        title: Text('${s['market']} ${s['symbol']} ${s['side']}'),
                        subtitle: Text('Reason: ${s['reason']}'),
                        trailing: Text('${((s['confidence'] as num) * 100).toStringAsFixed(1)}%'),
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  const Text(
                    'Latest Trades',
                    style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18),
                  ),
                  const SizedBox(height: 8),
                  ...trades.take(10).map(
                    (t) => Card(
                      child: ListTile(
                        title: Text('${t['market']} ${t['symbol']} ${t['side']}'),
                        subtitle: Text('Entry ${t['entry_price']} | SL ${t['stop_loss']} | TP1 ${t['tp1']}'),
                        trailing: Text(t['status']),
                      ),
                    ),
                  ),
                ],
              ),
            ),
    );
  }
}

class _MetricCard extends StatelessWidget {
  final String title;
  final String value;

  const _MetricCard({required this.title, required this.value});

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: ListTile(
        title: Text(title),
        trailing: Text(value, style: const TextStyle(fontWeight: FontWeight.bold)),
      ),
    );
  }
}

class ApiService {
  final String baseUrl;

  ApiService({required this.baseUrl});

  Future<List<dynamic>> getTrades() async {
    final res = await http.get(Uri.parse('$baseUrl/dashboard/trades'));
    return _decodeList(res);
  }

  Future<List<dynamic>> getSignals() async {
    final res = await http.get(Uri.parse('$baseUrl/dashboard/signals/live'));
    return _decodeList(res);
  }

  Future<List<dynamic>> getEquity() async {
    final res = await http.get(Uri.parse('$baseUrl/dashboard/equity'));
    return _decodeList(res);
  }

  List<dynamic> _decodeList(http.Response response) {
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw Exception('API error ${response.statusCode}');
    }
    final decoded = jsonDecode(response.body);
    return decoded is List ? decoded : [];
  }
}
