import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/trading_provider.dart';
import '../models/trade_models.dart';

class TradesScreen extends StatefulWidget {
  const TradesScreen({super.key});

  @override
  State<TradesScreen> createState() => _TradesScreenState();
}

class _TradesScreenState extends State<TradesScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<TradingProvider>().loadTrades();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Consumer<TradingProvider>(
      builder: (context, provider, _) {
        return RefreshIndicator(
          onRefresh: () => provider.loadTrades(),
          color: const Color(0xFF00E5FF),
          child: provider.trades.isEmpty
              ? ListView(
                  children: const [
                    SizedBox(height: 200),
                    Center(
                      child: Column(
                        children: [
                          Icon(Icons.history, size: 64, color: Colors.white24),
                          SizedBox(height: 16),
                          Text('No trade history', style: TextStyle(color: Colors.white38, fontSize: 16)),
                        ],
                      ),
                    ),
                  ],
                )
              : ListView.builder(
                  padding: const EdgeInsets.all(16),
                  itemCount: provider.trades.length,
                  itemBuilder: (context, index) {
                    return _TradeCard(trade: provider.trades[index]);
                  },
                ),
        );
      },
    );
  }
}

class _TradeCard extends StatelessWidget {
  final TradeHistory trade;
  const _TradeCard({required this.trade});

  @override
  Widget build(BuildContext context) {
    final isBuy = trade.side == 'buy';
    final dirColor = isBuy ? Colors.greenAccent : Colors.redAccent;
    final pnlColor = (trade.pnl ?? 0) >= 0 ? Colors.greenAccent : Colors.redAccent;

    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: dirColor.withAlpha(25),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Text(
                    trade.side.toUpperCase(),
                    style: TextStyle(color: dirColor, fontWeight: FontWeight.bold, fontSize: 11),
                  ),
                ),
                const SizedBox(width: 8),
                Text(
                  trade.symbol,
                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: Colors.white),
                ),
                const Spacer(),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: _statusColor(trade.status).withAlpha(20),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Text(
                    trade.status.toUpperCase(),
                    style: TextStyle(color: _statusColor(trade.status), fontSize: 10),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                _info('Entry', trade.entryPrice.toStringAsFixed(5)),
                _info('Lots', trade.lotSize.toStringAsFixed(2)),
                if (trade.aiConfidence != null)
                  _info('AI', '${(trade.aiConfidence! * 100).toStringAsFixed(0)}%'),
                if (trade.pnl != null)
                  _info(
                    'P&L',
                    '\$${trade.pnl!.toStringAsFixed(2)}',
                    color: pnlColor,
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _info(String label, String value, {Color? color}) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(color: Colors.white38, fontSize: 10)),
        Text(value, style: TextStyle(color: color ?? Colors.white70, fontSize: 13)),
      ],
    );
  }

  Color _statusColor(String status) {
    switch (status) {
      case 'open':
        return const Color(0xFF00E5FF);
      case 'closed':
        return Colors.greenAccent;
      case 'cancelled':
        return Colors.white38;
      default:
        return Colors.amberAccent;
    }
  }
}
