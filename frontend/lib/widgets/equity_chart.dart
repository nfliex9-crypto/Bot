import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:intl/intl.dart';
import '../models/account.dart';

class EquityChart extends StatelessWidget {
  final List<EquitySnapshot> snapshots;
  final double height;

  const EquityChart({
    super.key,
    required this.snapshots,
    this.height = 220,
  });

  @override
  Widget build(BuildContext context) {
    if (snapshots.isEmpty) {
      return SizedBox(
        height: height,
        child: const Center(
          child: Text('No equity data yet', style: TextStyle(color: Colors.white38)),
        ),
      );
    }

    final spots = snapshots.asMap().entries.map((e) {
      return FlSpot(e.key.toDouble(), e.value.equity);
    }).toList();

    final minY = spots.map((s) => s.y).reduce((a, b) => a < b ? a : b) * 0.998;
    final maxY = spots.map((s) => s.y).reduce((a, b) => a > b ? a : b) * 1.002;
    final isProfit = spots.last.y >= spots.first.y;
    final lineColor = isProfit ? const Color(0xFF00D4A0) : const Color(0xFFFF4757);

    return SizedBox(
      height: height,
      child: LineChart(
        LineChartData(
          minX: 0,
          maxX: (spots.length - 1).toDouble(),
          minY: minY,
          maxY: maxY,
          gridData: FlGridData(
            show: true,
            drawHorizontalLine: true,
            drawVerticalLine: false,
            horizontalInterval: (maxY - minY) / 4,
            getDrawingHorizontalLine: (_) => FlLine(
              color: Colors.white.withOpacity(0.06),
              strokeWidth: 1,
            ),
          ),
          borderData: FlBorderData(show: false),
          titlesData: FlTitlesData(
            leftTitles: AxisTitles(
              sideTitles: SideTitles(
                showTitles: true,
                reservedSize: 60,
                getTitlesWidget: (value, meta) => Text(
                  '\$${NumberFormat.compact().format(value)}',
                  style: const TextStyle(color: Colors.white38, fontSize: 10),
                ),
              ),
            ),
            bottomTitles: AxisTitles(sideTitles: SideTitles(showTitles: false)),
            rightTitles: AxisTitles(sideTitles: SideTitles(showTitles: false)),
            topTitles: AxisTitles(sideTitles: SideTitles(showTitles: false)),
          ),
          lineBarsData: [
            LineChartBarData(
              spots: spots,
              isCurved: true,
              curveSmoothness: 0.3,
              color: lineColor,
              barWidth: 2,
              isStrokeCapRound: true,
              dotData: const FlDotData(show: false),
              belowBarData: BarAreaData(
                show: true,
                gradient: LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: [
                    lineColor.withOpacity(0.3),
                    lineColor.withOpacity(0.0),
                  ],
                ),
              ),
            ),
          ],
          lineTouchData: LineTouchData(
            touchTooltipData: LineTouchTooltipData(
              getTooltipItems: (touchedSpots) {
                return touchedSpots.map((s) {
                  final idx = s.x.toInt();
                  final snap = snapshots[idx];
                  return LineTooltipItem(
                    '\$${NumberFormat('#,##0.00').format(snap.equity)}\n',
                    TextStyle(color: lineColor, fontWeight: FontWeight.bold, fontSize: 12),
                    children: [
                      TextSpan(
                        text: DateFormat('MMM d HH:mm').format(snap.timestamp),
                        style: const TextStyle(color: Colors.white54, fontSize: 10),
                      ),
                    ],
                  );
                }).toList();
              },
            ),
          ),
        ),
        duration: const Duration(milliseconds: 300),
      ),
    );
  }
}
