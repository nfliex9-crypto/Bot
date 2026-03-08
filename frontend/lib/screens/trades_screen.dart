import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import '../providers/trading_provider.dart';
import '../widgets/trade_card.dart';

class TradesScreen extends StatefulWidget {
  const TradesScreen({super.key});

  @override
  State<TradesScreen> createState() => _TradesScreenState();
}

class _TradesScreenState extends State<TradesScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0D0F1C),
      appBar: AppBar(
        backgroundColor: const Color(0xFF0D0F1C),
        elevation: 0,
        title: const Text('Trade History', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
        bottom: TabBar(
          controller: _tabController,
          labelColor: const Color(0xFF00D4A0),
          unselectedLabelColor: Colors.white38,
          indicatorColor: const Color(0xFF00D4A0),
          indicatorWeight: 2,
          tabs: const [
            Tab(text: 'OPEN'),
            Tab(text: 'HISTORY'),
          ],
        ),
      ),
      body: Column(
        children: [
          _StatsBar(),
          Expanded(
            child: TabBarView(
              controller: _tabController,
              children: [
                _OpenTradesList(),
                _HistoryList(),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _StatsBar extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Consumer<TradingProvider>(
      builder: (_, p, __) {
        final stats = p.stats;
        return Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          color: const Color(0xFF141627),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              _Mini(label: 'TOTAL', value: '${stats.totalTrades}', color: Colors.white70),
              _Mini(label: 'WINS', value: '${stats.winningTrades}', color: const Color(0xFF00D4A0)),
              _Mini(label: 'LOSSES', value: '${stats.losingTrades}', color: const Color(0xFFFF4757)),
              _Mini(
                label: 'WIN RATE',
                value: '${stats.winRate.toStringAsFixed(1)}%',
                color: stats.winRate >= 50 ? const Color(0xFF00D4A0) : const Color(0xFFFF4757),
              ),
              _Mini(
                label: 'NET P&L',
                value: '${stats.totalPnl >= 0 ? '+' : ''}\$${stats.totalPnl.toStringAsFixed(0)}',
                color: stats.totalPnl >= 0 ? const Color(0xFF00D4A0) : const Color(0xFFFF4757),
              ),
            ],
          ),
        );
      },
    );
  }
}

class _Mini extends StatelessWidget {
  final String label;
  final String value;
  final Color color;

  const _Mini({required this.label, required this.value, required this.color});

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(value, style: TextStyle(color: color, fontWeight: FontWeight.bold, fontSize: 14)),
        Text(label, style: const TextStyle(color: Colors.white24, fontSize: 9)),
      ],
    );
  }
}

class _OpenTradesList extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Consumer<TradingProvider>(
      builder: (_, p, __) {
        if (p.openTrades.isEmpty) {
          return const Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(Icons.hourglass_empty, color: Colors.white24, size: 48),
                SizedBox(height: 12),
                Text('No open positions', style: TextStyle(color: Colors.white38)),
              ],
            ),
          );
        }

        return ListView.builder(
          itemCount: p.openTrades.length,
          itemBuilder: (_, i) => TradeCard(trade: p.openTrades[i]),
        );
      },
    );
  }
}

class _HistoryList extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Consumer<TradingProvider>(
      builder: (_, p, __) {
        if (p.tradeHistory.isEmpty) {
          return const Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(Icons.history, color: Colors.white24, size: 48),
                SizedBox(height: 12),
                Text('No trade history yet', style: TextStyle(color: Colors.white38)),
              ],
            ),
          );
        }

        return ListView.builder(
          itemCount: p.tradeHistory.length,
          itemBuilder: (_, i) => TradeCard(trade: p.tradeHistory[i]),
        );
      },
    );
  }
}
