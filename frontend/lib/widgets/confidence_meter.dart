import 'package:flutter/material.dart';
import 'dart:math' as math;

class ConfidenceMeter extends StatelessWidget {
  final double confidence;
  final double size;

  const ConfidenceMeter({
    super.key,
    required this.confidence,
    this.size = 120,
  });

  Color get _color {
    if (confidence >= 0.75) return const Color(0xFF00D4A0);
    if (confidence >= 0.65) return const Color(0xFFFFA502);
    return const Color(0xFFFF4757);
  }

  String get _label {
    if (confidence >= 0.80) return 'STRONG';
    if (confidence >= 0.70) return 'GOOD';
    if (confidence >= 0.65) return 'FAIR';
    return 'WEAK';
  }

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: size,
      height: size,
      child: Stack(
        alignment: Alignment.center,
        children: [
          CustomPaint(
            size: Size(size, size),
            painter: _ArcPainter(confidence: confidence, color: _color),
          ),
          Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                '${(confidence * 100).toStringAsFixed(0)}%',
                style: TextStyle(
                  color: _color,
                  fontSize: size * 0.22,
                  fontWeight: FontWeight.bold,
                ),
              ),
              Text(
                _label,
                style: TextStyle(
                  color: Colors.white54,
                  fontSize: size * 0.09,
                  letterSpacing: 1.2,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _ArcPainter extends CustomPainter {
  final double confidence;
  final Color color;

  _ArcPainter({required this.confidence, required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = size.width / 2 - 8;
    const startAngle = math.pi * 0.75;
    const sweepTotal = math.pi * 1.5;

    // Background arc
    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius),
      startAngle,
      sweepTotal,
      false,
      Paint()
        ..color = Colors.white12
        ..style = PaintingStyle.stroke
        ..strokeWidth = 8
        ..strokeCap = StrokeCap.round,
    );

    // Value arc
    final sweepAngle = sweepTotal * confidence;
    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius),
      startAngle,
      sweepAngle,
      false,
      Paint()
        ..color = color
        ..style = PaintingStyle.stroke
        ..strokeWidth = 8
        ..strokeCap = StrokeCap.round,
    );
  }

  @override
  bool shouldRepaint(covariant _ArcPainter old) =>
      old.confidence != confidence || old.color != color;
}

class ConfidenceBar extends StatelessWidget {
  final double confidence;
  final double width;

  const ConfidenceBar({
    super.key,
    required this.confidence,
    this.width = double.infinity,
  });

  Color get _color {
    if (confidence >= 0.75) return const Color(0xFF00D4A0);
    if (confidence >= 0.65) return const Color(0xFFFFA502);
    return const Color(0xFFFF4757);
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            const Text('AI Confidence', style: TextStyle(color: Colors.white54, fontSize: 11)),
            Text(
              '${(confidence * 100).toStringAsFixed(1)}%',
              style: TextStyle(color: _color, fontSize: 11, fontWeight: FontWeight.bold),
            ),
          ],
        ),
        const SizedBox(height: 4),
        SizedBox(
          width: width,
          child: ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: confidence,
              backgroundColor: Colors.white12,
              valueColor: AlwaysStoppedAnimation<Color>(_color),
              minHeight: 6,
            ),
          ),
        ),
      ],
    );
  }
}
