import 'package:flutter/material.dart';
import 'dart:math' as math;
import '../models/trade_models.dart';

class AIConfidenceCard extends StatelessWidget {
  final AIModelInfo aiModel;

  const AIConfidenceCard({super.key, required this.aiModel});

  @override
  Widget build(BuildContext context) {
    final accuracy = (aiModel.metrics['accuracy'] ?? 0).toDouble();
    final precision = (aiModel.metrics['precision'] ?? 0).toDouble();
    final recall = (aiModel.metrics['recall'] ?? 0).toDouble();
    final f1 = (aiModel.metrics['f1_score'] ?? 0).toDouble();

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Text(
                  'AI Model',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: Colors.white70),
                ),
                const Spacer(),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: const Color(0xFF7C4DFF).withAlpha(20),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Text(
                    aiModel.version.isEmpty ? 'N/A' : aiModel.version,
                    style: const TextStyle(color: Color(0xFF7C4DFF), fontSize: 11),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _buildGauge('Accuracy', accuracy, const Color(0xFF00E5FF)),
                _buildGauge('Precision', precision, Colors.greenAccent),
                _buildGauge('Recall', recall, Colors.amberAccent),
                _buildGauge('F1', f1, const Color(0xFF7C4DFF)),
              ],
            ),
            if (aiModel.metrics.containsKey('top_features')) ...[
              const SizedBox(height: 16),
              const Text(
                'Top Features',
                style: TextStyle(color: Colors.white38, fontSize: 12),
              ),
              const SizedBox(height: 8),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: _buildFeatureChips(),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildGauge(String label, double value, Color color) {
    return Column(
      children: [
        SizedBox(
          width: 56,
          height: 56,
          child: CustomPaint(
            painter: _GaugePainter(value: value, color: color),
            child: Center(
              child: Text(
                '${(value * 100).toStringAsFixed(0)}%',
                style: TextStyle(color: color, fontWeight: FontWeight.bold, fontSize: 12),
              ),
            ),
          ),
        ),
        const SizedBox(height: 6),
        Text(label, style: const TextStyle(color: Colors.white38, fontSize: 10)),
      ],
    );
  }

  List<Widget> _buildFeatureChips() {
    final features = aiModel.metrics['top_features'] as Map<String, dynamic>? ?? {};
    return features.entries.take(5).map((e) {
      return Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        decoration: BoxDecoration(
          color: Colors.white.withAlpha(8),
          borderRadius: BorderRadius.circular(6),
        ),
        child: Text(
          '${e.key}: ${(e.value * 100).toStringAsFixed(1)}%',
          style: const TextStyle(color: Colors.white54, fontSize: 10),
        ),
      );
    }).toList();
  }
}

class _GaugePainter extends CustomPainter {
  final double value;
  final Color color;

  _GaugePainter({required this.value, required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = size.width / 2 - 4;

    final bgPaint = Paint()
      ..color = Colors.white.withAlpha(10)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 5
      ..strokeCap = StrokeCap.round;

    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius),
      -math.pi / 2,
      2 * math.pi,
      false,
      bgPaint,
    );

    final fgPaint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 5
      ..strokeCap = StrokeCap.round;

    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius),
      -math.pi / 2,
      2 * math.pi * value,
      false,
      fgPaint,
    );
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => true;
}
