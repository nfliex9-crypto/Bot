import 'package:flutter/material.dart';
import '../models/trade_models.dart';

class ActiveTradesCard extends StatelessWidget {
  final List<ActiveTrade> trades;

  const ActiveTradesCard({super.key, required this.trades});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Text(
                  'Active Trades',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: Colors.white70),
                ),
                const Spacer(),
                Text(
                  '${trades.length}',
                  style: const TextStyle(color: Color(0xFF00E5FF), fontWeight: FontWeight.bold),
                ),
              ],
            ),
            const SizedBox(height: 12),
            if (trades.isEmpty)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 20),
                child: Center(
                  child: Text('No active trades', style: TextStyle(color: Colors.white24)),
                ),
              )
            else
              ...trades.map((trade) => _tradeRow(trade)),
          ],
        ),
      ),
    );
  }

  Widget _tradeRow(ActiveTrade trade) {
    final isLong = trade.direction == 'long';
    final color = isLong ? Colors.greenAccent : Colors.redAccent;

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white.withAlpha(5),
        borderRadius: BorderRadius.circular(10),
        border: Border(
          left: BorderSide(color: color, width: 3),
        ),
      ),
      child: Column(
        children: [
          Row(
            children: [
              Text(
                trade.symbol,
                style: const TextStyle(fontWeight: FontWeight.bold, color: Colors.white, fontSize: 14),
              ),
              const SizedBox(width: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: color.withAlpha(20),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  trade.direction.toUpperCase(),
                  style: TextStyle(color: color, fontSize: 10, fontWeight: FontWeight.bold),
                ),
              ),
              const Spacer(),
              if (trade.breakEven)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: Colors.amberAccent.withAlpha(20),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: const Text(
                    'BE',
                    style: TextStyle(color: Colors.amberAccent, fontSize: 10, fontWeight: FontWeight.bold),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _tpIndicator('TP1', trade.tp1Hit),
              _tpIndicator('TP2', trade.tp2Hit),
              _tpIndicator('TP3', false),
              Text(
                'Entry: ${trade.entryPrice.toStringAsFixed(5)}',
                style: const TextStyle(color: Colors.white38, fontSize: 10),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _tpIndicator(String label, bool hit) {
    return Row(
      children: [
        Icon(
          hit ? Icons.check_circle : Icons.circle_outlined,
          size: 14,
          color: hit ? Colors.greenAccent : Colors.white24,
        ),
        const SizedBox(width: 4),
        Text(
          label,
          style: TextStyle(
            color: hit ? Colors.greenAccent : Colors.white38,
            fontSize: 11,
          ),
        ),
      ],
    );
  }
}
