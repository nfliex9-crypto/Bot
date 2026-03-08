import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/trading_provider.dart';
import '../services/websocket_service.dart';
import '../models/signal.dart';
import '../widgets/signal_card.dart';
import '../widgets/confidence_meter.dart';

class SignalsScreen extends StatefulWidget {
  const SignalsScreen({super.key});

  @override
  State<SignalsScreen> createState() => _SignalsScreenState();
}

class _SignalsScreenState extends State<SignalsScreen> {
  double _minConfidence = 0.0;
  String? _marketFilter;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0D0F1C),
      appBar: AppBar(
        backgroundColor: const Color(0xFF0D0F1C),
        elevation: 0,
        title: const Text('Live Signals', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
        actions: [
          IconButton(
            icon: const Icon(Icons.filter_list, color: Colors.white54),
            onPressed: _showFilterSheet,
          ),
        ],
      ),
      body: Column(
        children: [
          _LiveHeader(),
          if (_marketFilter != null || _minConfidence > 0)
            _FilterChips(
              marketFilter: _marketFilter,
              minConfidence: _minConfidence,
              onClear: () => setState(() {
                _marketFilter = null;
                _minConfidence = 0.0;
              }),
            ),
          Expanded(child: _SignalsList(
            minConfidence: _minConfidence,
            marketFilter: _marketFilter,
          )),
        ],
      ),
    );
  }

  void _showFilterSheet() {
    showModalBottomSheet(
      context: context,
      backgroundColor: const Color(0xFF1A1D2E),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (_) => StatefulBuilder(
        builder: (ctx, setState) => Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('FILTER SIGNALS', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, letterSpacing: 1.5)),
              const SizedBox(height: 20),
              const Text('Market', style: TextStyle(color: Colors.white54, fontSize: 12)),
              const SizedBox(height: 8),
              Row(
                children: ['ALL', 'FOREX', 'CRYPTO'].map((m) {
                  final selected = m == 'ALL' ? _marketFilter == null : _marketFilter == m;
                  return Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: ChoiceChip(
                      label: Text(m),
                      selected: selected,
                      onSelected: (_) {
                        setState(() => _marketFilter = m == 'ALL' ? null : m);
                        this.setState(() => _marketFilter = m == 'ALL' ? null : m);
                      },
                      selectedColor: const Color(0xFF00D4A0).withOpacity(0.3),
                      backgroundColor: const Color(0xFF141627),
                      labelStyle: TextStyle(
                        color: selected ? const Color(0xFF00D4A0) : Colors.white54,
                        fontSize: 12,
                      ),
                    ),
                  );
                }).toList(),
              ),
              const SizedBox(height: 16),
              const Text('Min Confidence', style: TextStyle(color: Colors.white54, fontSize: 12)),
              Slider(
                value: _minConfidence,
                min: 0.0,
                max: 0.9,
                divisions: 9,
                activeColor: const Color(0xFF00D4A0),
                inactiveColor: Colors.white12,
                label: '${(_minConfidence * 100).toInt()}%',
                onChanged: (v) {
                  setState(() => _minConfidence = v);
                  this.setState(() => _minConfidence = v);
                },
              ),
              const SizedBox(height: 16),
            ],
          ),
        ),
      ),
    );
  }
}

class _LiveHeader extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Consumer<WebSocketService>(
      builder: (_, ws, __) {
        return Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
          color: const Color(0xFF141627),
          child: Row(
            children: [
              Container(
                width: 8,
                height: 8,
                decoration: BoxDecoration(
                  color: ws.status == WsStatus.connected
                      ? const Color(0xFF00D4A0)
                      : const Color(0xFFFF4757),
                  shape: BoxShape.circle,
                ),
              ),
              const SizedBox(width: 8),
              Text(
                ws.status == WsStatus.connected ? 'Live feed active' : 'Connecting...',
                style: const TextStyle(color: Colors.white54, fontSize: 12),
              ),
              const Spacer(),
              Consumer<TradingProvider>(
                builder: (_, p, __) => Text(
                  '${p.activeSignals.length} active',
                  style: const TextStyle(color: Colors.white38, fontSize: 12),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

class _FilterChips extends StatelessWidget {
  final String? marketFilter;
  final double minConfidence;
  final VoidCallback onClear;

  const _FilterChips({
    required this.marketFilter,
    required this.minConfidence,
    required this.onClear,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(
        children: [
          if (marketFilter != null)
            _Chip(label: marketFilter!),
          if (minConfidence > 0)
            _Chip(label: '≥${(minConfidence * 100).toInt()}% conf'),
          const Spacer(),
          GestureDetector(
            onTap: onClear,
            child: const Text('Clear', style: TextStyle(color: Color(0xFF00D4A0), fontSize: 12)),
          ),
        ],
      ),
    );
  }
}

class _Chip extends StatelessWidget {
  final String label;
  const _Chip({required this.label});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(right: 6),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: const Color(0xFF00D4A0).withOpacity(0.15),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(label, style: const TextStyle(color: Color(0xFF00D4A0), fontSize: 11)),
    );
  }
}

class _SignalsList extends StatelessWidget {
  final double minConfidence;
  final String? marketFilter;

  const _SignalsList({required this.minConfidence, required this.marketFilter});

  @override
  Widget build(BuildContext context) {
    return Consumer2<TradingProvider, WebSocketService>(
      builder: (_, p, ws, __) {
        var all = [...ws.liveSignals, ...p.activeSignals];

        // Deduplicate
        final seen = <int>{};
        all = all.where((s) => seen.add(s.id)).toList();

        // Filter
        if (minConfidence > 0) {
          all = all.where((s) => (s.confidenceScore ?? 0) >= minConfidence).toList();
        }
        if (marketFilter != null) {
          all = all.where((s) => s.market == marketFilter).toList();
        }

        if (all.isEmpty) {
          return const Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(Icons.search_off, color: Colors.white24, size: 48),
                SizedBox(height: 12),
                Text('No signals match filters', style: TextStyle(color: Colors.white38)),
                SizedBox(height: 6),
                Text('Markets are being scanned every 5 minutes', style: TextStyle(color: Colors.white24, fontSize: 12)),
              ],
            ),
          );
        }

        return RefreshIndicator(
          color: const Color(0xFF00D4A0),
          backgroundColor: const Color(0xFF1A1D2E),
          onRefresh: () => p.loadAll(),
          child: ListView.builder(
            itemCount: all.length,
            itemBuilder: (_, i) => SignalCard(signal: all[i]),
          ),
        );
      },
    );
  }
}
