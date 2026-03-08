import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import '../providers/trading_provider.dart';
import '../services/websocket_service.dart';
import '../widgets/equity_chart.dart';
import '../widgets/confidence_meter.dart';
import '../widgets/signal_card.dart';
import '../widgets/trade_card.dart';

class DashboardScreen extends StatelessWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0D0F1C),
      body: RefreshIndicator(
        color: const Color(0xFF00D4A0),
        backgroundColor: const Color(0xFF1A1D2E),
        onRefresh: () => context.read<TradingProvider>().loadAll(),
        child: CustomScrollView(
          slivers: [
            _DashboardAppBar(),
            SliverToBoxAdapter(child: _AccountSummaryCards()),
            SliverToBoxAdapter(child: _EquitySection()),
            SliverToBoxAdapter(child: _OpenTradesSection()),
            SliverToBoxAdapter(child: _LiveSignalsSection()),
            SliverToBoxAdapter(child: _AISection()),
            const SliverToBoxAdapter(child: SizedBox(height: 32)),
          ],
        ),
      ),
    );
  }
}

class _DashboardAppBar extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return SliverAppBar(
      backgroundColor: const Color(0xFF0D0F1C),
      floating: true,
      pinned: false,
      elevation: 0,
      title: Row(
        children: [
          Container(
            width: 32,
            height: 32,
            decoration: BoxDecoration(
              color: const Color(0xFF00D4A0).withOpacity(0.2),
              borderRadius: BorderRadius.circular(8),
            ),
            child: const Icon(Icons.auto_graph, color: Color(0xFF00D4A0), size: 18),
          ),
          const SizedBox(width: 10),
          const Text(
            'AI Trading',
            style: TextStyle(
              color: Colors.white,
              fontWeight: FontWeight.bold,
              fontSize: 18,
            ),
          ),
        ],
      ),
      actions: [
        Consumer<WebSocketService>(
          builder: (_, ws, __) {
            final color = ws.status == WsStatus.connected
                ? const Color(0xFF00D4A0)
                : ws.status == WsStatus.connecting
                    ? const Color(0xFFFFA502)
                    : const Color(0xFFFF4757);
            return Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              child: Row(
                children: [
                  Container(
                    width: 8,
                    height: 8,
                    decoration: BoxDecoration(color: color, shape: BoxShape.circle),
                  ),
                  const SizedBox(width: 6),
                  Text(
                    ws.status == WsStatus.connected ? 'LIVE' : 'OFFLINE',
                    style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.bold),
                  ),
                ],
              ),
            );
          },
        ),
      ],
    );
  }
}

class _AccountSummaryCards extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Consumer<TradingProvider>(
      builder: (_, p, __) {
        final acc = p.account;
        final stats = p.stats;
        final fmt = NumberFormat('#,##0.00');
        final pnlColor = acc.totalPnl >= 0 ? const Color(0xFF00D4A0) : const Color(0xFFFF4757);

        return Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            children: [
              // Primary equity card
              Container(
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    colors: [Color(0xFF1A1D2E), Color(0xFF141627)],
                  ),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: Colors.white.withOpacity(0.08)),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('TOTAL EQUITY', style: TextStyle(color: Colors.white38, fontSize: 11, letterSpacing: 1.5)),
                    const SizedBox(height: 8),
                    Text(
                      '\$${fmt.format(acc.totalEquity)}',
                      style: const TextStyle(color: Colors.white, fontSize: 32, fontWeight: FontWeight.bold),
                    ),
                    const SizedBox(height: 4),
                    Row(
                      children: [
                        Icon(
                          acc.totalPnl >= 0 ? Icons.trending_up : Icons.trending_down,
                          color: pnlColor,
                          size: 16,
                        ),
                        const SizedBox(width: 4),
                        Text(
                          '${acc.totalPnl >= 0 ? '+' : ''}\$${fmt.format(acc.totalPnl)}',
                          style: TextStyle(color: pnlColor, fontWeight: FontWeight.bold),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          'All Time',
                          style: const TextStyle(color: Colors.white38, fontSize: 12),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 12),
              // Stats row
              Row(
                children: [
                  Expanded(child: _StatCard(
                    label: 'WIN RATE',
                    value: '${stats.winRate.toStringAsFixed(1)}%',
                    icon: Icons.emoji_events,
                    color: const Color(0xFF00D4A0),
                  )),
                  const SizedBox(width: 8),
                  Expanded(child: _StatCard(
                    label: 'OPEN',
                    value: '${acc.openTrades}',
                    icon: Icons.bar_chart,
                    color: const Color(0xFF5C6BC0),
                  )),
                  const SizedBox(width: 8),
                  Expanded(child: _StatCard(
                    label: 'DRAWDOWN',
                    value: '-${acc.maxDrawdownPct.toStringAsFixed(1)}%',
                    icon: Icons.waterfall_chart,
                    color: const Color(0xFFFF4757),
                  )),
                  const SizedBox(width: 8),
                  Expanded(child: _StatCard(
                    label: 'TRADES',
                    value: '${stats.totalTrades}',
                    icon: Icons.receipt_long,
                    color: const Color(0xFFFFA502),
                  )),
                ],
              ),
            ],
          ),
        );
      },
    );
  }
}

class _StatCard extends StatelessWidget {
  final String label;
  final String value;
  final IconData icon;
  final Color color;

  const _StatCard({
    required this.label,
    required this.value,
    required this.icon,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFF1A1D2E),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: color.withOpacity(0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: color, size: 16),
          const SizedBox(height: 6),
          Text(value, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 14)),
          Text(label, style: const TextStyle(color: Colors.white38, fontSize: 9, letterSpacing: 0.8)),
        ],
      ),
    );
  }
}

class _EquitySection extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _SectionHeader(title: 'EQUITY CURVE', icon: Icons.show_chart),
          const SizedBox(height: 12),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: const Color(0xFF1A1D2E),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: Colors.white.withOpacity(0.06)),
            ),
            child: Consumer<TradingProvider>(
              builder: (_, p, __) => EquityChart(snapshots: p.equityCurve),
            ),
          ),
        ],
      ),
    );
  }
}

class _OpenTradesSection extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Consumer<TradingProvider>(
      builder: (_, p, __) {
        if (p.openTrades.isEmpty) return const SizedBox.shrink();

        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 20, 16, 8),
              child: _SectionHeader(
                title: 'OPEN POSITIONS (${p.openTrades.length})',
                icon: Icons.timer,
                color: const Color(0xFF5C6BC0),
              ),
            ),
            ...p.openTrades.take(3).map((t) => TradeCard(trade: t)),
          ],
        );
      },
    );
  }
}

class _LiveSignalsSection extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Consumer2<TradingProvider, WebSocketService>(
      builder: (_, p, ws, __) {
        final signals = [...ws.liveSignals, ...p.activeSignals];
        final unique = <int, dynamic>{};
        for (final s in signals) {
          unique[s.id] ??= s;
        }
        final displaySignals = unique.values.take(5).toList();

        if (displaySignals.isEmpty) {
          return Padding(
            padding: const EdgeInsets.fromLTRB(16, 20, 16, 0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _SectionHeader(title: 'LIVE SIGNALS', icon: Icons.bolt, color: const Color(0xFFFFA502)),
                const SizedBox(height: 12),
                Container(
                  padding: const EdgeInsets.all(24),
                  decoration: BoxDecoration(
                    color: const Color(0xFF1A1D2E),
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: const Center(
                    child: Text('Scanning markets...', style: TextStyle(color: Colors.white38)),
                  ),
                ),
              ],
            ),
          );
        }

        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 20, 16, 4),
              child: _SectionHeader(
                title: 'LIVE SIGNALS',
                icon: Icons.bolt,
                color: const Color(0xFFFFA502),
              ),
            ),
            ...displaySignals.map((s) => SignalCard(signal: s)),
          ],
        );
      },
    );
  }
}

class _AISection extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Consumer<TradingProvider>(
      builder: (_, p, __) {
        final history = p.confidenceHistory;
        if (history.isEmpty) return const SizedBox.shrink();

        final avgConfidence = history.isEmpty
            ? 0.0
            : history.map((h) => (h['confidence'] as num?)?.toDouble() ?? 0.0).reduce((a, b) => a + b) / history.length;

        return Padding(
          padding: const EdgeInsets.fromLTRB(16, 20, 16, 0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _SectionHeader(title: 'AI ENGINE', icon: Icons.psychology, color: const Color(0xFF9C27B0)),
              const SizedBox(height: 12),
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: const Color(0xFF1A1D2E),
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: Colors.white.withOpacity(0.06)),
                ),
                child: Row(
                  children: [
                    ConfidenceMeter(confidence: avgConfidence, size: 100),
                    const SizedBox(width: 20),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text('AVERAGE CONFIDENCE', style: TextStyle(color: Colors.white38, fontSize: 10, letterSpacing: 1)),
                          const SizedBox(height: 6),
                          Text(
                            '${(avgConfidence * 100).toStringAsFixed(1)}%',
                            style: const TextStyle(color: Colors.white, fontSize: 24, fontWeight: FontWeight.bold),
                          ),
                          const SizedBox(height: 8),
                          if (p.modelInfo.isNotEmpty) ...[
                            Text(
                              'Model v${p.modelInfo['model_version'] ?? '1.0'}',
                              style: const TextStyle(color: Colors.white38, fontSize: 11),
                            ),
                            Text(
                              '${p.modelInfo['feature_count'] ?? 30} features',
                              style: const TextStyle(color: Colors.white38, fontSize: 11),
                            ),
                          ],
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

class _SectionHeader extends StatelessWidget {
  final String title;
  final IconData icon;
  final Color color;

  const _SectionHeader({
    required this.title,
    required this.icon,
    this.color = Colors.white54,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(icon, color: color, size: 14),
        const SizedBox(width: 6),
        Text(
          title,
          style: TextStyle(
            color: color,
            fontSize: 11,
            fontWeight: FontWeight.bold,
            letterSpacing: 1.5,
          ),
        ),
      ],
    );
  }
}
