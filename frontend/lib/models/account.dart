class AccountSummary {
  final double totalBalance;
  final double totalEquity;
  final double totalPnl;
  final int openTrades;
  final double maxDrawdownPct;
  final List<BrokerAccount> accounts;

  const AccountSummary({
    required this.totalBalance,
    required this.totalEquity,
    required this.totalPnl,
    required this.openTrades,
    required this.maxDrawdownPct,
    required this.accounts,
  });

  factory AccountSummary.fromJson(Map<String, dynamic> json) {
    return AccountSummary(
      totalBalance: (json['total_balance'] as num).toDouble(),
      totalEquity: (json['total_equity'] as num).toDouble(),
      totalPnl: (json['total_pnl'] as num).toDouble(),
      openTrades: json['open_trades'] as int,
      maxDrawdownPct: (json['max_drawdown_pct'] as num).toDouble(),
      accounts: (json['accounts'] as List<dynamic>)
          .map((a) => BrokerAccount.fromJson(a as Map<String, dynamic>))
          .toList(),
    );
  }

  factory AccountSummary.empty() => const AccountSummary(
    totalBalance: 0, totalEquity: 0, totalPnl: 0,
    openTrades: 0, maxDrawdownPct: 0, accounts: [],
  );
}

class BrokerAccount {
  final int id;
  final String broker;
  final double balance;
  final double equity;
  final double drawdownPct;
  final double winRate;
  final int sessionTradesToday;

  const BrokerAccount({
    required this.id,
    required this.broker,
    required this.balance,
    required this.equity,
    required this.drawdownPct,
    required this.winRate,
    required this.sessionTradesToday,
  });

  factory BrokerAccount.fromJson(Map<String, dynamic> json) {
    return BrokerAccount(
      id: json['id'] as int,
      broker: json['broker'] as String,
      balance: (json['balance'] as num).toDouble(),
      equity: (json['equity'] as num).toDouble(),
      drawdownPct: (json['drawdown_pct'] as num).toDouble(),
      winRate: (json['win_rate'] as num).toDouble(),
      sessionTradesToday: json['session_trades_today'] as int,
    );
  }
}

class EquitySnapshot {
  final int id;
  final double equity;
  final double balance;
  final double drawdownPct;
  final int openTrades;
  final DateTime timestamp;

  const EquitySnapshot({
    required this.id,
    required this.equity,
    required this.balance,
    required this.drawdownPct,
    required this.openTrades,
    required this.timestamp,
  });

  factory EquitySnapshot.fromJson(Map<String, dynamic> json) {
    return EquitySnapshot(
      id: json['id'] as int,
      equity: (json['equity'] as num).toDouble(),
      balance: (json['balance'] as num).toDouble(),
      drawdownPct: (json['drawdown_pct'] as num).toDouble(),
      openTrades: json['open_trades'] as int,
      timestamp: DateTime.parse(json['timestamp'] as String),
    );
  }
}
