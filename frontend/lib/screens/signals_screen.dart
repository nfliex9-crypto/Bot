import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/trading_provider.dart';
import '../models/trade_models.dart';

class SignalsScreen extends StatefulWidget {
  const SignalsScreen({super.key});

  @override
  State<SignalsScreen> createState() => _SignalsScreenState();
}

class _SignalsScreenState extends State<SignalsScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<TradingProvider>().loadSignals();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Consumer<TradingProvider>(
      builder: (context, provider, _) {
        return RefreshIndicator(
          onRefresh: () => provider.loadSignals(),
          color: const Color(0xFF00E5FF),
          child: provider.signals.isEmpty
              ? ListView(
                  children: const [
                    SizedBox(height: 200),
                    Center(
                      child: Column(
                        children: [
                          Icon(Icons.signal_cellular_alt, size: 64, color: Colors.white24),
                          SizedBox(height: 16),
                          Text('No signals yet', style: TextStyle(color: Colors.white38, fontSize: 16)),
                          SizedBox(height: 8),
                          Text('Pull down to scan markets', style: TextStyle(color: Colors.white24)),
                        ],
                      ),
                    ),
                  ],
                )
              : ListView.builder(
                  padding: const EdgeInsets.all(16),
                  itemCount: provider.signals.length,
                  itemBuilder: (context, index) {
                    return _SignalCard(
                      signal: provider.signals[index],
                      onExecute: () async {
                        final success = await provider.executeSignal(provider.signals[index]);
                        if (context.mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(
                              content: Text(success ? 'Trade executed!' : 'Execution failed'),
                              backgroundColor: success ? Colors.green : Colors.red,
                            ),
                          );
                        }
                      },
                    );
                  },
                ),
        );
      },
    );
  }
}

class _SignalCard extends StatelessWidget {
  final TradeSignal signal;
  final VoidCallback onExecute;

  const _SignalCard({required this.signal, required this.onExecute});

  @override
  Widget build(BuildContext context) {
    final isLong = signal.direction == 'long';
    final dirColor = isLong ? Colors.greenAccent : Colors.redAccent;

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: dirColor.withAlpha(30),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(
                    signal.direction.toUpperCase(),
                    style: TextStyle(color: dirColor, fontWeight: FontWeight.bold, fontSize: 12),
                  ),
                ),
                const SizedBox(width: 8),
                Text(
                  signal.symbol,
                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18, color: Colors.white),
                ),
                const Spacer(),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: Colors.white.withAlpha(10),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Text(
                    signal.timeframe,
                    style: const TextStyle(color: Colors.white54, fontSize: 12),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                _infoChip('Confidence', '${(signal.confidence * 100).toStringAsFixed(1)}%',
                    _confidenceColor(signal.confidence)),
                const SizedBox(width: 8),
                _infoChip('R:R', signal.riskReward.toStringAsFixed(1), Colors.white70),
                const SizedBox(width: 8),
                Flexible(
                  child: _infoChip('Strategy', signal.strategy.replaceAll('_', ' '), Colors.white54),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                _priceLabel('Entry', signal.entryPrice),
                _priceLabel('SL', signal.stopLoss),
                _priceLabel('TP1', signal.tp1),
                _priceLabel('TP2', signal.tp2),
              ],
            ),
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: signal.confidence >= 0.5 ? onExecute : null,
                style: ElevatedButton.styleFrom(
                  backgroundColor: dirColor.withAlpha(30),
                  foregroundColor: dirColor,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                ),
                child: Text(signal.confidence >= 0.5 ? 'Execute Trade' : 'Low Confidence'),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _infoChip(String label, String value, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withAlpha(15),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text('$label: $value', style: TextStyle(color: color, fontSize: 11)),
    );
  }

  Widget _priceLabel(String label, double price) {
    return Column(
      children: [
        Text(label, style: const TextStyle(color: Colors.white38, fontSize: 10)),
        Text(price.toStringAsFixed(5), style: const TextStyle(color: Colors.white70, fontSize: 12)),
      ],
    );
  }

  Color _confidenceColor(double confidence) {
    if (confidence >= 0.7) return Colors.greenAccent;
    if (confidence >= 0.5) return Colors.amberAccent;
    return Colors.redAccent;
  }
}
