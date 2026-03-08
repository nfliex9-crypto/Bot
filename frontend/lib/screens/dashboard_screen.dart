import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../models/dashboard_models.dart';
import '../services/api_service.dart';
import '../widgets/equity_chart.dart';
import '../widgets/metric_card.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  final ApiService _apiService = ApiService();
  late Future<_DashboardData> _future;
  final NumberFormat _money = NumberFormat.currency(symbol: '\$');
  final DateFormat _dateTime = DateFormat('MMM d, HH:mm');

  @override
  void initState() {
    super.initState();
    _future = _loadData();
  }

  Future<_DashboardData> _loadData() async {
    final overview = await _apiService.fetchDashboardOverview();
    final equityCurve = await _apiService.fetchEquityCurve();
    return _DashboardData(overview: overview, equityCurve: equityCurve);
  }

  Future<void> _refresh() async {
    final refreshed = _loadData();
    setState(() {
      _future = refreshed;
    });
    await refreshed;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('AI Trading Dashboard'),
        actions: [
          IconButton(
            onPressed: _refresh,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: FutureBuilder<_DashboardData>(
          future: _future,
          builder: (context, snapshot) {
            if (snapshot.connectionState != ConnectionState.done) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snapshot.hasError) {
              return ListView(
                children: [
                  Padding(
                    padding: const EdgeInsets.all(24),
                    child: Text(
                      'Unable to load dashboard data.\n${snapshot.error}',
                      style: Theme.of(context).textTheme.bodyLarge,
                    ),
                  ),
                ],
              );
            }

            final data = snapshot.data!;
            final latestEquity = data.overview.latestEquity;
            return ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Wrap(
                  spacing: 12,
                  runSpacing: 12,
                  children: [
                    SizedBox(
                      width: 220,
                      child: MetricCard(
                        label: 'Equity',
                        value: latestEquity == null ? '--' : _money.format(latestEquity.equity),
                        icon: Icons.account_balance_wallet,
                      ),
                    ),
                    SizedBox(
                      width: 220,
                      child: MetricCard(
                        label: 'Balance',
                        value: latestEquity == null ? '--' : _money.format(latestEquity.balance),
                        icon: Icons.savings,
                      ),
                    ),
                    SizedBox(
                      width: 220,
                      child: MetricCard(
                        label: 'AI Win Rate',
                        value: '${(data.overview.winRate * 100).toStringAsFixed(1)}%',
                        icon: Icons.psychology,
                      ),
                    ),
                    SizedBox(
                      width: 220,
                      child: MetricCard(
                        label: 'Total PnL',
                        value: _money.format(data.overview.totalPnl),
                        icon: Icons.trending_up,
                        valueColor: data.overview.totalPnl >= 0 ? Colors.greenAccent : Colors.redAccent,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                EquityChart(snapshots: data.equityCurve),
                const SizedBox(height: 16),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Live Signals',
                          style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
                        ),
                        const SizedBox(height: 12),
                        ...data.overview.liveSignals.map(_buildSignalTile),
                        if (data.overview.liveSignals.isEmpty)
                          const Text('No signals available yet.'),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Trade History',
                          style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
                        ),
                        const SizedBox(height: 12),
                        ...data.overview.recentTrades.map(_buildTradeTile),
                        if (data.overview.recentTrades.isEmpty)
                          const Text('No trades have been executed yet.'),
                      ],
                    ),
                  ),
                ),
              ],
            );
          },
        ),
      ),
    );
  }

  Widget _buildSignalTile(SignalItem signal) {
    final color = signal.side == 'long' ? Colors.greenAccent : Colors.redAccent;
    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: CircleAvatar(
        backgroundColor: color.withOpacity(0.2),
        child: Icon(signal.side == 'long' ? Icons.arrow_upward : Icons.arrow_downward, color: color),
      ),
      title: Text('${signal.symbol} • ${signal.market.toUpperCase()} • ${signal.timeframe}'),
      subtitle: Text(
        'Entry ${signal.entryPrice.toStringAsFixed(4)} | SL ${signal.stopLoss.toStringAsFixed(4)}'
        ' | TP1 ${signal.tp1.toStringAsFixed(4)}\n${signal.rationale}',
      ),
      trailing: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Text('${(signal.confidence * 100).toStringAsFixed(0)}%', style: TextStyle(color: color)),
          Text(_dateTime.format(signal.createdAt.toLocal())),
        ],
      ),
    );
  }

  Widget _buildTradeTile(TradeItem trade) {
    final pnlColor = trade.pnl >= 0 ? Colors.greenAccent : Colors.redAccent;
    return ListTile(
      contentPadding: EdgeInsets.zero,
      title: Text('${trade.symbol} • ${trade.side.toUpperCase()} • ${trade.broker}'),
      subtitle: Text(
        'Risk ${_money.format(trade.riskAmount)} | Session ${trade.sessionName}'
        ' | Confidence ${(trade.confidence * 100).toStringAsFixed(0)}%\n'
        'Opened ${_dateTime.format(trade.openedAt.toLocal())}',
      ),
      trailing: Text(
        _money.format(trade.pnl),
        style: TextStyle(fontWeight: FontWeight.bold, color: pnlColor),
      ),
    );
  }
}

class _DashboardData {
  const _DashboardData({required this.overview, required this.equityCurve});

  final DashboardOverview overview;
  final List<EquitySnapshot> equityCurve;
}
