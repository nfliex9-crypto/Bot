import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../config/app_config.dart';
import '../services/api_service.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  bool _isCheckingHealth = false;
  bool? _isHealthy;
  String _serverStatus = 'Unknown';

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0D0F1C),
      appBar: AppBar(
        backgroundColor: const Color(0xFF0D0F1C),
        elevation: 0,
        title: const Text('Settings', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
      ),
      body: ListView(
        children: [
          _Section(
            title: 'CONNECTION',
            children: [
              _InfoTile(
                icon: Icons.dns,
                label: 'API Endpoint',
                value: AppConfig.apiUrl,
              ),
              _InfoTile(
                icon: Icons.wifi,
                label: 'WebSocket',
                value: AppConfig.wsUrl,
              ),
              _ActionTile(
                icon: Icons.health_and_safety,
                label: 'Server Health',
                subtitle: _serverStatus,
                trailing: _isCheckingHealth
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2, color: Color(0xFF00D4A0)),
                      )
                    : Icon(
                        _isHealthy == null
                            ? Icons.help_outline
                            : _isHealthy!
                                ? Icons.check_circle
                                : Icons.error,
                        color: _isHealthy == null
                            ? Colors.white38
                            : _isHealthy!
                                ? const Color(0xFF00D4A0)
                                : const Color(0xFFFF4757),
                        size: 20,
                      ),
                onTap: _checkHealth,
              ),
            ],
          ),
          _Section(
            title: 'RISK MANAGEMENT',
            children: [
              _InfoTile(icon: Icons.percent, label: 'Risk Per Trade', value: '0.75%'),
              _InfoTile(icon: Icons.trending_down, label: 'Max Drawdown', value: '15%'),
              _InfoTile(icon: Icons.swap_horiz, label: 'Max Trades/Session', value: '3'),
              _InfoTile(icon: Icons.bar_chart, label: 'TP Ratios', value: '1.5 / 2.5 / 4.0'),
            ],
          ),
          _Section(
            title: 'STRATEGY',
            children: [
              _InfoTile(icon: Icons.wave, label: 'Signal Sources', value: 'Liquidity Sweep + BOS + Pullback'),
              _InfoTile(icon: Icons.access_time, label: 'Timeframe', value: 'H1'),
              _InfoTile(icon: Icons.public, label: 'Forex Pairs', value: 'EURUSD, GBPUSD, USDJPY, AUDUSD, XAUUSD'),
              _InfoTile(icon: Icons.currency_bitcoin, label: 'Crypto Pairs', value: 'BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT'),
            ],
          ),
          _Section(
            title: 'AI MODEL',
            children: [
              _InfoTile(icon: Icons.psychology, label: 'Algorithm', value: 'Random Forest Classifier'),
              _InfoTile(icon: Icons.analytics, label: 'Features', value: '30 engineered features'),
              _InfoTile(icon: Icons.threshold, label: 'Min Confidence', value: '65%'),
            ],
          ),
          const SizedBox(height: 40),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Text(
              'AI Trading System v1.0.0\nBuilt with FastAPI + Flutter',
              textAlign: TextAlign.center,
              style: const TextStyle(color: Colors.white24, fontSize: 11),
            ),
          ),
          const SizedBox(height: 20),
        ],
      ),
    );
  }

  Future<void> _checkHealth() async {
    setState(() {
      _isCheckingHealth = true;
      _serverStatus = 'Checking...';
    });

    try {
      final api = ApiService();
      final healthy = await api.checkHealth();
      setState(() {
        _isHealthy = healthy;
        _serverStatus = healthy ? 'Online' : 'Unreachable';
      });
    } catch (e) {
      setState(() {
        _isHealthy = false;
        _serverStatus = 'Error: $e';
      });
    } finally {
      setState(() => _isCheckingHealth = false);
    }
  }
}

class _Section extends StatelessWidget {
  final String title;
  final List<Widget> children;

  const _Section({required this.title, required this.children});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 24, 16, 8),
          child: Text(
            title,
            style: const TextStyle(
              color: Colors.white38,
              fontSize: 11,
              fontWeight: FontWeight.bold,
              letterSpacing: 1.5,
            ),
          ),
        ),
        Container(
          margin: const EdgeInsets.symmetric(horizontal: 16),
          decoration: BoxDecoration(
            color: const Color(0xFF1A1D2E),
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: Colors.white.withOpacity(0.06)),
          ),
          child: Column(children: children),
        ),
      ],
    );
  }
}

class _InfoTile extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;

  const _InfoTile({required this.icon, required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return ListTile(
      leading: Icon(icon, color: Colors.white38, size: 20),
      title: Text(label, style: const TextStyle(color: Colors.white70, fontSize: 14)),
      subtitle: Text(value, style: const TextStyle(color: Colors.white38, fontSize: 12)),
    );
  }
}

class _ActionTile extends StatelessWidget {
  final IconData icon;
  final String label;
  final String subtitle;
  final Widget trailing;
  final VoidCallback? onTap;

  const _ActionTile({
    required this.icon,
    required this.label,
    required this.subtitle,
    required this.trailing,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return ListTile(
      onTap: onTap,
      leading: Icon(icon, color: Colors.white38, size: 20),
      title: Text(label, style: const TextStyle(color: Colors.white70, fontSize: 14)),
      subtitle: Text(subtitle, style: const TextStyle(color: Colors.white38, fontSize: 12)),
      trailing: trailing,
    );
  }
}
