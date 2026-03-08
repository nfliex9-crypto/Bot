import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../models/signal.dart';
import 'confidence_meter.dart';

class SignalCard extends StatelessWidget {
  final Signal signal;
  final VoidCallback? onTap;

  const SignalCard({super.key, required this.signal, this.onTap});

  Color get _directionColor =>
      signal.isLong ? const Color(0xFF00D4A0) : const Color(0xFFFF4757);

  Color get _marketColor =>
      signal.market == 'FOREX' ? const Color(0xFF5C6BC0) : const Color(0xFFFFA502);

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: const Color(0xFF1A1D2E),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: _directionColor.withOpacity(0.3),
            width: 1,
          ),
          boxShadow: [
            BoxShadow(
              color: _directionColor.withOpacity(0.08),
              blurRadius: 12,
              spreadRadius: 1,
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header row
            Row(
              children: [
                // Symbol + direction badge
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: _directionColor.withOpacity(0.15),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Row(
                    children: [
                      Icon(
                        signal.isLong ? Icons.arrow_upward : Icons.arrow_downward,
                        color: _directionColor,
                        size: 14,
                      ),
                      const SizedBox(width: 4),
                      Text(
                        signal.direction,
                        style: TextStyle(
                          color: _directionColor,
                          fontWeight: FontWeight.bold,
                          fontSize: 12,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 8),
                Text(
                  signal.symbol,
                  style: const TextStyle(
                    color: Colors.white,
                    fontWeight: FontWeight.bold,
                    fontSize: 16,
                  ),
                ),
                const SizedBox(width: 8),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: _marketColor.withOpacity(0.2),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Text(
                    signal.market,
                    style: TextStyle(color: _marketColor, fontSize: 10),
                  ),
                ),
                const Spacer(),
                if (signal.confidenceScore != null)
                  _ConfidenceBadge(confidence: signal.confidenceScore!),
              ],
            ),

            const SizedBox(height: 12),

            // Entry and targets
            Row(
              children: [
                _PriceInfo(
                  label: 'ENTRY',
                  value: _formatPrice(signal.entryZoneLow, signal.entryZoneHigh),
                  color: Colors.white70,
                ),
                const SizedBox(width: 16),
                _PriceInfo(
                  label: 'SL',
                  value: signal.stopLoss != null ? _formatNum(signal.stopLoss!) : '-',
                  color: const Color(0xFFFF4757),
                ),
                const SizedBox(width: 16),
                _PriceInfo(
                  label: 'TP1',
                  value: signal.tp1 != null ? _formatNum(signal.tp1!) : '-',
                  color: const Color(0xFF00D4A0),
                ),
                const SizedBox(width: 16),
                _PriceInfo(
                  label: 'TP2',
                  value: signal.tp2 != null ? _formatNum(signal.tp2!) : '-',
                  color: const Color(0xFF00D4A0).withOpacity(0.7),
                ),
              ],
            ),

            const SizedBox(height: 12),

            // Confluence indicators
            Row(
              children: [
                _ConfluenceBadge(
                  label: 'SWEEP',
                  active: signal.liquiditySweepDetected,
                ),
                const SizedBox(width: 6),
                _ConfluenceBadge(
                  label: 'BOS',
                  active: signal.bosDetected,
                ),
                const SizedBox(width: 6),
                _ConfluenceBadge(
                  label: 'PULLBACK',
                  active: signal.pullbackConfirmed,
                ),
                const Spacer(),
                if (signal.session != null)
                  Text(
                    signal.session!.replaceAll('_', ' '),
                    style: const TextStyle(color: Colors.white38, fontSize: 10),
                  ),
              ],
            ),

            if (signal.createdAt != null) ...[
              const SizedBox(height: 8),
              Text(
                DateFormat('MMM d, HH:mm').format(signal.createdAt!),
                style: const TextStyle(color: Colors.white24, fontSize: 10),
              ),
            ],
          ],
        ),
      ),
    );
  }

  String _formatNum(double v) {
    if (v >= 1000) return v.toStringAsFixed(2);
    if (v >= 10) return v.toStringAsFixed(4);
    return v.toStringAsFixed(5);
  }

  String _formatPrice(double? low, double? high) {
    if (low == null && high == null) return '-';
    if (low == null || high == null) return _formatNum(low ?? high!);
    return '${_formatNum(low)} - ${_formatNum(high)}';
  }
}

class _ConfidenceBadge extends StatelessWidget {
  final double confidence;
  const _ConfidenceBadge({required this.confidence});

  Color get _color {
    if (confidence >= 0.75) return const Color(0xFF00D4A0);
    if (confidence >= 0.65) return const Color(0xFFFFA502);
    return const Color(0xFFFF4757);
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: _color.withOpacity(0.15),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: _color.withOpacity(0.4), width: 1),
      ),
      child: Row(
        children: [
          Icon(Icons.psychology, color: _color, size: 12),
          const SizedBox(width: 4),
          Text(
            '${(confidence * 100).toStringAsFixed(0)}%',
            style: TextStyle(color: _color, fontSize: 11, fontWeight: FontWeight.bold),
          ),
        ],
      ),
    );
  }
}

class _PriceInfo extends StatelessWidget {
  final String label;
  final String value;
  final Color color;

  const _PriceInfo({required this.label, required this.value, required this.color});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(color: Colors.white38, fontSize: 9)),
        Text(value, style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.w600)),
      ],
    );
  }
}

class _ConfluenceBadge extends StatelessWidget {
  final String label;
  final bool active;

  const _ConfluenceBadge({required this.label, required this.active});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
      decoration: BoxDecoration(
        color: active ? Colors.white.withOpacity(0.12) : Colors.transparent,
        borderRadius: BorderRadius.circular(4),
        border: Border.all(
          color: active ? Colors.white30 : Colors.white12,
          width: 1,
        ),
      ),
      child: Row(
        children: [
          Icon(
            active ? Icons.check_circle : Icons.radio_button_unchecked,
            color: active ? const Color(0xFF00D4A0) : Colors.white24,
            size: 10,
          ),
          const SizedBox(width: 3),
          Text(
            label,
            style: TextStyle(
              color: active ? Colors.white60 : Colors.white24,
              fontSize: 9,
            ),
          ),
        ],
      ),
    );
  }
}
