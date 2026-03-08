import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/trading_provider.dart';
import '../providers/auth_provider.dart';
import '../widgets/equity_card.dart';
import '../widgets/risk_status_card.dart';
import '../widgets/active_trades_card.dart';
import '../widgets/ai_confidence_card.dart';
import 'signals_screen.dart';
import 'trades_screen.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  int _selectedIndex = 0;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<TradingProvider>().loadDashboard();
      context.read<TradingProvider>().initWebSocket();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'AI Trading',
          style: TextStyle(fontWeight: FontWeight.bold, fontSize: 24),
        ),
        actions: [
          Consumer<TradingProvider>(
            builder: (context, provider, _) {
              return IconButton(
                icon: Icon(
                  provider.autoTrading ? Icons.stop_circle : Icons.play_circle,
                  color: provider.autoTrading ? Colors.redAccent : const Color(0xFF00E5FF),
                  size: 28,
                ),
                onPressed: () => provider.toggleAutoTrading(),
                tooltip: provider.autoTrading ? 'Stop Auto Trading' : 'Start Auto Trading',
              );
            },
          ),
          IconButton(
            icon: const Icon(Icons.refresh, color: Colors.white70),
            onPressed: () => context.read<TradingProvider>().loadDashboard(),
          ),
          IconButton(
            icon: const Icon(Icons.logout, color: Colors.white70),
            onPressed: () => context.read<AuthProvider>().logout(),
          ),
        ],
      ),
      body: IndexedStack(
        index: _selectedIndex,
        children: const [
          _DashboardTab(),
          SignalsScreen(),
          TradesScreen(),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        backgroundColor: const Color(0xFF0F1329),
        selectedIndex: _selectedIndex,
        onDestinationSelected: (i) => setState(() => _selectedIndex = i),
        indicatorColor: const Color(0xFF00E5FF).withAlpha(40),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.dashboard_outlined, color: Colors.white54),
            selectedIcon: Icon(Icons.dashboard, color: Color(0xFF00E5FF)),
            label: 'Dashboard',
          ),
          NavigationDestination(
            icon: Icon(Icons.signal_cellular_alt_outlined, color: Colors.white54),
            selectedIcon: Icon(Icons.signal_cellular_alt, color: Color(0xFF00E5FF)),
            label: 'Signals',
          ),
          NavigationDestination(
            icon: Icon(Icons.history_outlined, color: Colors.white54),
            selectedIcon: Icon(Icons.history, color: Color(0xFF00E5FF)),
            label: 'Trades',
          ),
        ],
      ),
    );
  }
}

class _DashboardTab extends StatelessWidget {
  const _DashboardTab();

  @override
  Widget build(BuildContext context) {
    return Consumer<TradingProvider>(
      builder: (context, provider, _) {
        if (provider.isLoading && provider.dashboard == null) {
          return const Center(
            child: CircularProgressIndicator(color: Color(0xFF00E5FF)),
          );
        }

        final dashboard = provider.dashboard;

        return RefreshIndicator(
          onRefresh: () => provider.loadDashboard(),
          color: const Color(0xFF00E5FF),
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              if (dashboard != null) ...[
                EquityCard(equity: dashboard.equity),
                const SizedBox(height: 12),
                RiskStatusCard(riskStatus: dashboard.riskStatus),
                const SizedBox(height: 12),
                AIConfidenceCard(aiModel: dashboard.aiModel),
                const SizedBox(height: 12),
                ActiveTradesCard(trades: dashboard.activeTrades),
                const SizedBox(height: 12),
                _ConnectionStatusCard(connections: dashboard.connections),
              ] else ...[
                const Center(
                  child: Padding(
                    padding: EdgeInsets.all(48),
                    child: Text(
                      'Pull to refresh or tap refresh button',
                      style: TextStyle(color: Colors.white54),
                    ),
                  ),
                ),
              ],
            ],
          ),
        );
      },
    );
  }
}

class _ConnectionStatusCard extends StatelessWidget {
  final dynamic connections;
  const _ConnectionStatusCard({required this.connections});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Connections',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
                color: Colors.white70,
              ),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                _statusDot(connections.mt5),
                const SizedBox(width: 8),
                const Text('MetaTrader 5 (Forex)', style: TextStyle(color: Colors.white70)),
                const Spacer(),
                _statusDot(connections.binance),
                const SizedBox(width: 8),
                const Text('Binance (Crypto)', style: TextStyle(color: Colors.white70)),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _statusDot(bool connected) {
    return Container(
      width: 10,
      height: 10,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: connected ? Colors.greenAccent : Colors.redAccent,
        boxShadow: [
          BoxShadow(
            color: (connected ? Colors.greenAccent : Colors.redAccent).withAlpha(100),
            blurRadius: 6,
          ),
        ],
      ),
    );
  }
}
