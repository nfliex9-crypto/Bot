class EquitySnapshot {
  const EquitySnapshot({
    required this.id,
    required this.balance,
    required this.equity,
    required this.drawdown,
    required this.openRisk,
    required this.createdAt,
  });

  final int id;
  final double balance;
  final double equity;
  final double drawdown;
  final double openRisk;
  final DateTime createdAt;

  factory EquitySnapshot.fromJson(Map<String, dynamic> json) {
    return EquitySnapshot(
      id: json['id'] as int,
      balance: (json['balance'] as num).toDouble(),
      equity: (json['equity'] as num).toDouble(),
      drawdown: (json['drawdown'] as num).toDouble(),
      openRisk: (json['open_risk'] as num).toDouble(),
      createdAt: DateTime.parse(json['created_at'] as String),
    );
  }
}

class SignalItem {
  const SignalItem({
    required this.id,
    required this.symbol,
    required this.market,
    required this.timeframe,
    required this.side,
    required this.confidence,
    required this.entryPrice,
    required this.stopLoss,
    required this.tp1,
    required this.tp2,
    required this.tp3,
    required this.status,
    required this.rationale,
    required this.createdAt,
  });

  final int id;
  final String symbol;
  final String market;
  final String timeframe;
  final String side;
  final double confidence;
  final double entryPrice;
  final double stopLoss;
  final double tp1;
  final double tp2;
  final double tp3;
  final String status;
  final String rationale;
  final DateTime createdAt;

  factory SignalItem.fromJson(Map<String, dynamic> json) {
    return SignalItem(
      id: json['id'] as int,
      symbol: json['symbol'] as String,
      market: json['market'] as String,
      timeframe: json['timeframe'] as String,
      side: json['side'] as String,
      confidence: (json['confidence'] as num).toDouble(),
      entryPrice: (json['entry_price'] as num).toDouble(),
      stopLoss: (json['stop_loss'] as num).toDouble(),
      tp1: (json['tp1'] as num).toDouble(),
      tp2: (json['tp2'] as num).toDouble(),
      tp3: (json['tp3'] as num).toDouble(),
      status: json['status'] as String,
      rationale: json['rationale'] as String,
      createdAt: DateTime.parse(json['created_at'] as String),
    );
  }
}

class TradeItem {
  const TradeItem({
    required this.id,
    required this.symbol,
    required this.market,
    required this.side,
    required this.quantity,
    required this.riskAmount,
    required this.entryPrice,
    required this.stopLoss,
    required this.tp1,
    required this.tp2,
    required this.tp3,
    required this.confidence,
    required this.broker,
    required this.status,
    required this.pnl,
    required this.sessionName,
    required this.openedAt,
  });

  final int id;
  final String symbol;
  final String market;
  final String side;
  final double quantity;
  final double riskAmount;
  final double entryPrice;
  final double stopLoss;
  final double tp1;
  final double tp2;
  final double tp3;
  final double confidence;
  final String broker;
  final String status;
  final double pnl;
  final String sessionName;
  final DateTime openedAt;

  factory TradeItem.fromJson(Map<String, dynamic> json) {
    return TradeItem(
      id: json['id'] as int,
      symbol: json['symbol'] as String,
      market: json['market'] as String,
      side: json['side'] as String,
      quantity: (json['quantity'] as num).toDouble(),
      riskAmount: (json['risk_amount'] as num).toDouble(),
      entryPrice: (json['entry_price'] as num).toDouble(),
      stopLoss: (json['stop_loss'] as num).toDouble(),
      tp1: (json['tp1'] as num).toDouble(),
      tp2: (json['tp2'] as num).toDouble(),
      tp3: (json['tp3'] as num).toDouble(),
      confidence: (json['confidence'] as num).toDouble(),
      broker: json['broker'] as String,
      status: json['status'] as String,
      pnl: (json['pnl'] as num).toDouble(),
      sessionName: json['session_name'] as String,
      openedAt: DateTime.parse(json['opened_at'] as String),
    );
  }
}

class DashboardOverview {
  const DashboardOverview({
    required this.latestEquity,
    required this.liveSignals,
    required this.recentTrades,
    required this.winRate,
    required this.totalPnl,
  });

  final EquitySnapshot? latestEquity;
  final List<SignalItem> liveSignals;
  final List<TradeItem> recentTrades;
  final double winRate;
  final double totalPnl;

  factory DashboardOverview.fromJson(Map<String, dynamic> json) {
    return DashboardOverview(
      latestEquity: json['latest_equity'] == null
          ? null
          : EquitySnapshot.fromJson(json['latest_equity'] as Map<String, dynamic>),
      liveSignals: (json['live_signals'] as List<dynamic>)
          .map((item) => SignalItem.fromJson(item as Map<String, dynamic>))
          .toList(),
      recentTrades: (json['recent_trades'] as List<dynamic>)
          .map((item) => TradeItem.fromJson(item as Map<String, dynamic>))
          .toList(),
      winRate: (json['win_rate'] as num).toDouble(),
      totalPnl: (json['total_pnl'] as num).toDouble(),
    );
  }
}
