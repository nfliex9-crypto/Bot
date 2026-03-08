import 'package:flutter/material.dart';
import '../models/trade_models.dart';

class RiskStatusCard extends StatelessWidget {
  final RiskStatus riskStatus;

  const RiskStatusCard({super.key, required this.riskStatus});

  @override
  Widget build(BuildContext context) {
    final drawdownPct = riskStatus.currentDrawdown / riskStatus.maxDrawdown;
    final sessionPct = riskStatus.sessionTrades / riskStatus.maxTradesPerSession;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Text(
                  'Risk Management',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: Colors.white70),
                ),
                const Spacer(),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: riskStatus.canTrade
                        ? Colors.greenAccent.withAlpha(20)
                        : Colors.redAccent.withAlpha(20),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(
                    riskStatus.canTrade ? 'ACTIVE' : 'LOCKED',
                    style: TextStyle(
                      color: riskStatus.canTrade ? Colors.greenAccent : Colors.redAccent,
                      fontSize: 11,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            _buildProgressBar(
              'Drawdown',
              '${riskStatus.currentDrawdown.toStringAsFixed(1)}%',
              'Max: ${riskStatus.maxDrawdown.toStringAsFixed(0)}%',
              drawdownPct.clamp(0, 1),
              _drawdownColor(drawdownPct),
            ),
            const SizedBox(height: 14),
            _buildProgressBar(
              'Session Trades',
              '${riskStatus.sessionTrades}/${riskStatus.maxTradesPerSession}',
              'Per session',
              sessionPct.clamp(0, 1),
              const Color(0xFF00E5FF),
            ),
            const SizedBox(height: 14),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                _metricBox('Risk/Trade', '${riskStatus.riskPerTrade}%', const Color(0xFF2979FF)),
                _metricBox('Peak Equity', '\$${riskStatus.peakEquity.toStringAsFixed(0)}', Colors.amberAccent),
                _metricBox('Active', '${riskStatus.activeTrades}', const Color(0xFF00E5FF)),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildProgressBar(
    String label,
    String value,
    String subtitle,
    double progress,
    Color color,
  ) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(label, style: const TextStyle(color: Colors.white54, fontSize: 13)),
            Text(value, style: TextStyle(color: color, fontWeight: FontWeight.w600, fontSize: 13)),
          ],
        ),
        const SizedBox(height: 6),
        ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(
            value: progress,
            backgroundColor: Colors.white.withAlpha(10),
            valueColor: AlwaysStoppedAnimation<Color>(color),
            minHeight: 6,
          ),
        ),
        const SizedBox(height: 2),
        Text(subtitle, style: const TextStyle(color: Colors.white24, fontSize: 10)),
      ],
    );
  }

  Widget _metricBox(String label, String value, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: color.withAlpha(12),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Column(
        children: [
          Text(value, style: TextStyle(color: color, fontWeight: FontWeight.bold, fontSize: 14)),
          const SizedBox(height: 2),
          Text(label, style: const TextStyle(color: Colors.white38, fontSize: 10)),
        ],
      ),
    );
  }

  Color _drawdownColor(double pct) {
    if (pct < 0.5) return Colors.greenAccent;
    if (pct < 0.8) return Colors.amberAccent;
    return Colors.redAccent;
  }
}
