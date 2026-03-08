import "package:flutter/material.dart";

import "api_service.dart";
import "models.dart";

void main() {
  runApp(const TradingDashboardApp());
}

class TradingDashboardApp extends StatelessWidget {
  const TradingDashboardApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: "AI Trading Dashboard",
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.indigo),
        useMaterial3: true,
      ),
      home: const DashboardPage(),
    );
  }
}

class DashboardPage extends StatefulWidget {
  const DashboardPage({super.key});

  @override
  State<DashboardPage> createState() => _DashboardPageState();
}

class _DashboardPageState extends State<DashboardPage> {
  final ApiService _api = ApiService();
  bool _loading = true;
  String? _error;
  EquityResponse? _equity;
  List<Trade> _trades = const [];
  List<Signal> _signals = const [];

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final results = await Future.wait([
        _api.fetchEquity(),
        _api.fetchTradeHistory(),
        _api.fetchLiveSignals(),
      ]);
      setState(() {
        _equity = results[0] as EquityResponse;
        _trades = results[1] as List<Trade>;
        _signals = results[2] as List<Signal>;
      });
    } catch (exc) {
      setState(() => _error = "$exc");
    } finally {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text("AI Automated Trading"),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _refresh,
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Text(_error!))
              : RefreshIndicator(
                  onRefresh: _refresh,
                  child: ListView(
                    padding: const EdgeInsets.all(16),
                    children: [
                      _buildEquityCard(),
                      const SizedBox(height: 16),
                      _buildSignalsCard(),
                      const SizedBox(height: 16),
                      _buildTradesCard(),
                    ],
                  ),
                ),
    );
  }

  Widget _buildEquityCard() {
    final equity = _equity;
    if (equity == null) {
      return const Card(child: ListTile(title: Text("No equity data")));
    }
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text("Equity", style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            Text("Current Equity: ${equity.currentEquity.toStringAsFixed(2)}"),
            Text("Current Balance: ${equity.currentBalance.toStringAsFixed(2)}"),
            Text("Max Drawdown: ${(equity.maxDrawdown * 100).toStringAsFixed(2)}%"),
          ],
        ),
      ),
    );
  }

  Widget _buildSignalsCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text("Live Signals + AI Confidence", style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            if (_signals.isEmpty) const Text("No live signals"),
            ..._signals.take(12).map(
                  (signal) => ListTile(
                    dense: true,
                    contentPadding: EdgeInsets.zero,
                    title: Text("${signal.symbol} (${signal.market}) - ${signal.side.toUpperCase()}"),
                    subtitle: Text("Status: ${signal.status}  |  Entry: ${signal.entryPrice.toStringAsFixed(5)}"),
                    trailing: Text("${(signal.confidence * 100).toStringAsFixed(1)}%"),
                  ),
                ),
          ],
        ),
      ),
    );
  }

  Widget _buildTradesCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text("Trade History", style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            if (_trades.isEmpty) const Text("No trades yet"),
            ..._trades.take(20).map(
                  (trade) => ListTile(
                    dense: true,
                    contentPadding: EdgeInsets.zero,
                    title: Text("${trade.symbol} ${trade.side.toUpperCase()} (${trade.status})"),
                    subtitle: Text("Entry: ${trade.entryPrice.toStringAsFixed(5)}  |  PnL: ${trade.pnl.toStringAsFixed(2)}"),
                    trailing: Text("${(trade.confidence * 100).toStringAsFixed(1)}%"),
                  ),
                ),
          ],
        ),
      ),
    );
  }
}
