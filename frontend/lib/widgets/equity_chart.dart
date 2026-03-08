import 'package:flutter/material.dart';

import '../models/dashboard_models.dart';

class EquityChart extends StatelessWidget {
  const EquityChart({super.key, required this.snapshots});

  final List<EquitySnapshot> snapshots;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Equity Trend',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 12),
            SizedBox(
              height: 180,
              child: snapshots.length < 2
                  ? const Center(child: Text('Waiting for enough data points'))
                  : CustomPaint(
                      painter: _EquityChartPainter(snapshots),
                      child: const SizedBox.expand(),
                    ),
            ),
          ],
        ),
      ),
    );
  }
}

class _EquityChartPainter extends CustomPainter {
  _EquityChartPainter(this.snapshots);

  final List<EquitySnapshot> snapshots;

  @override
  void paint(Canvas canvas, Size size) {
    final values = snapshots.map((item) => item.equity).toList();
    final minValue = values.reduce((a, b) => a < b ? a : b);
    final maxValue = values.reduce((a, b) => a > b ? a : b);
    final range = (maxValue - minValue).abs() < 1 ? 1.0 : maxValue - minValue;

    final gridPaint = Paint()
      ..color = Colors.white12
      ..strokeWidth = 1;
    for (var i = 0; i < 4; i++) {
      final y = size.height * i / 3;
      canvas.drawLine(Offset(0, y), Offset(size.width, y), gridPaint);
    }

    final path = Path();
    for (var i = 0; i < values.length; i++) {
      final x = i * (size.width / (values.length - 1));
      final normalized = (values[i] - minValue) / range;
      final y = size.height - (normalized * size.height);
      if (i == 0) {
        path.moveTo(x, y);
      } else {
        path.lineTo(x, y);
      }
    }

    final linePaint = Paint()
      ..color = const Color(0xFF00D084)
      ..strokeWidth = 3
      ..style = PaintingStyle.stroke;
    canvas.drawPath(path, linePaint);
  }

  @override
  bool shouldRepaint(covariant _EquityChartPainter oldDelegate) {
    return oldDelegate.snapshots != snapshots;
  }
}
