import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../models/trade.dart';
import 'confidence_meter.dart';

class TradeCard extends StatelessWidget {
  final Trade trade;
  final VoidCallback? onTap;

  const TradeCard({super.key, required this.trade, this.onTap});

  Color get _directionColor =>
      trade.isLong ? const Color(0xFF00D4A0) : const Color(0xFFFF4757);

  Color get _pnlColor {
    if (trade.pnl == null) return Colors.white54;
    return (trade.pnl! >= 0) ? const Color(0xFF00D4A0) : const Color(0xFFFF4757);
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 5),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: const Color(0xFF1A1D2E),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: Colors.white.withOpacity(0.06)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  width: 4,
                  height: 36,
                  decoration: BoxDecoration(
                    color: _directionColor,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
                const SizedBox(width: 10),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      trade.symbol,
                      style: const TextStyle(
                        color: Colors.white,
                        fontWeight: FontWeight.bold,
                        fontSize: 15,
                      ),
                    ),
                    Row(
                      children: [
                        Text(
                          trade.direction,
                          style: TextStyle(color: _directionColor, fontSize: 11),
                        ),
                        const Text(' · ', style: TextStyle(color: Colors.white24)),
                        Text(
                          trade.market,
                          style: const TextStyle(color: Colors.white38, fontSize: 11),
                        ),
                        if (trade.breakEvenTriggered) ...[
                          const Text(' · ', style: TextStyle(color: Colors.white24)),
                          const Text('BE', style: TextStyle(color: Color(0xFFFFA502), fontSize: 10)),
                        ],
                      ],
                    ),
                  ],
                ),
                const Spacer(),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    if (trade.pnl != null)
                      Text(
                        '${trade.pnl! >= 0 ? '+' : ''}\$${trade.pnl!.toStringAsFixed(2)}',
                        style: TextStyle(
                          color: _pnlColor,
                          fontWeight: FontWeight.bold,
                          fontSize: 15,
                        ),
                      ),
                    if (trade.pnlPct != null)
                      Text(
                        '${trade.pnlPct! >= 0 ? '+' : ''}${trade.pnlPct!.toStringAsFixed(1)}%',
                        style: TextStyle(color: _pnlColor.withOpacity(0.7), fontSize: 11),
                      ),
                    _StatusBadge(status: trade.status, tpHit: trade.tpHit),
                  ],
                ),
              ],
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                _TradeDetail(label: 'Entry', value: _fmtPrice(trade.entryPrice)),
                const SizedBox(width: 12),
                _TradeDetail(label: 'SL', value: _fmtPrice(trade.stopLoss)),
                const SizedBox(width: 12),
                _TradeDetail(label: 'TP1', value: _fmtPrice(trade.tp1)),
                const SizedBox(width: 12),
                _TradeDetail(label: 'TP2', value: _fmtPrice(trade.tp2)),
                const Spacer(),
                if (trade.confidenceScore != null)
                  ConfidenceBar(confidence: trade.confidenceScore!, width: 80),
              ],
            ),
            if (trade.openedAt != null || trade.closedAt != null) ...[
              const SizedBox(height: 6),
              Text(
                trade.isClosed
                    ? 'Closed ${DateFormat('MMM d, HH:mm').format(trade.closedAt!)}'
                    : 'Opened ${DateFormat('MMM d, HH:mm').format(trade.openedAt!)}',
                style: const TextStyle(color: Colors.white24, fontSize: 10),
              ),
            ],
          ],
        ),
      ),
    );
  }

  String _fmtPrice(double v) {
    if (v >= 1000) return v.toStringAsFixed(2);
    if (v >= 10) return v.toStringAsFixed(4);
    return v.toStringAsFixed(5);
  }
}

class _StatusBadge extends StatelessWidget {
  final String status;
  final int? tpHit;

  const _StatusBadge({required this.status, this.tpHit});

  Color get _color {
    switch (status) {
      case 'OPEN':
        return const Color(0xFF5C6BC0);
      case 'CLOSED':
        return Colors.white38;
      case 'CANCELLED':
        return Colors.white24;
      default:
        return Colors.white38;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: _color.withOpacity(0.2),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        tpHit != null ? '$status · TP$tpHit' : status,
        style: TextStyle(color: _color, fontSize: 9, fontWeight: FontWeight.bold),
      ),
    );
  }
}

class _TradeDetail extends StatelessWidget {
  final String label;
  final String value;

  const _TradeDetail({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(color: Colors.white24, fontSize: 9)),
        Text(value, style: const TextStyle(color: Colors.white70, fontSize: 11)),
      ],
    );
  }
}
