import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';
import '../models/trade_models.dart';

class EquityCard extends StatelessWidget {
  final EquityData equity;

  const EquityCard({super.key, required this.equity});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text(
                  'Total Equity',
                  style: TextStyle(color: Colors.white54, fontSize: 14),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: Colors.greenAccent.withAlpha(20),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: const Text(
                    'LIVE',
                    style: TextStyle(color: Colors.greenAccent, fontSize: 10, fontWeight: FontWeight.bold),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              '\$${equity.total.toStringAsFixed(2)}',
              style: const TextStyle(
                fontSize: 32,
                fontWeight: FontWeight.bold,
                color: Colors.white,
              ),
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: _subEquity('Forex (MT5)', equity.forex, const Color(0xFF2979FF)),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: _subEquity('Crypto (Binance)', equity.crypto, const Color(0xFFFFAB00)),
                ),
              ],
            ),
            const SizedBox(height: 16),
            SizedBox(
              height: 80,
              child: _buildMiniChart(),
            ),
          ],
        ),
      ),
    );
  }

  Widget _subEquity(String label, double value, Color color) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withAlpha(15),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: TextStyle(color: color.withAlpha(180), fontSize: 11)),
          const SizedBox(height: 4),
          Text(
            '\$${value.toStringAsFixed(2)}',
            style: TextStyle(color: color, fontWeight: FontWeight.bold, fontSize: 16),
          ),
        ],
      ),
    );
  }

  Widget _buildMiniChart() {
    return LineChart(
      LineChartData(
        gridData: const FlGridData(show: false),
        titlesData: const FlTitlesData(show: false),
        borderData: FlBorderData(show: false),
        lineBarsData: [
          LineChartBarData(
            spots: List.generate(
              20,
              (i) => FlSpot(i.toDouble(), equity.total + (i * 10 - 100) + (i % 3) * 20),
            ),
            isCurved: true,
            color: const Color(0xFF00E5FF),
            barWidth: 2,
            isStrokeCapRound: true,
            dotData: const FlDotData(show: false),
            belowBarData: BarAreaData(
              show: true,
              color: const Color(0xFF00E5FF).withAlpha(25),
            ),
          ),
        ],
      ),
    );
  }
}
