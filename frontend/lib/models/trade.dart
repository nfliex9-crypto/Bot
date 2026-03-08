class Trade {
  final int id;
  final String symbol;
  final String market;
  final String direction;
  final String status;
  final double entryPrice;
  final double lotSize;
  final double riskAmount;
  final double stopLoss;
  final double tp1;
  final double tp2;
  final double tp3;
  final double? atrValue;
  final bool breakEvenTriggered;
  final double? closePrice;
  final double? pnl;
  final double? pnlPct;
  final int? tpHit;
  final double? confidenceScore;
  final String? sessionDate;
  final DateTime? createdAt;
  final DateTime? openedAt;
  final DateTime? closedAt;

  const Trade({
    required this.id,
    required this.symbol,
    required this.market,
    required this.direction,
    required this.status,
    required this.entryPrice,
    required this.lotSize,
    required this.riskAmount,
    required this.stopLoss,
    required this.tp1,
    required this.tp2,
    required this.tp3,
    this.atrValue,
    required this.breakEvenTriggered,
    this.closePrice,
    this.pnl,
    this.pnlPct,
    this.tpHit,
    this.confidenceScore,
    this.sessionDate,
    this.createdAt,
    this.openedAt,
    this.closedAt,
  });

  factory Trade.fromJson(Map<String, dynamic> json) {
    return Trade(
      id: json['id'] as int,
      symbol: json['symbol'] as String,
      market: json['market'] as String,
      direction: json['direction'] as String,
      status: json['status'] as String,
      entryPrice: (json['entry_price'] as num).toDouble(),
      lotSize: (json['lot_size'] as num).toDouble(),
      riskAmount: (json['risk_amount'] as num).toDouble(),
      stopLoss: (json['stop_loss'] as num).toDouble(),
      tp1: (json['tp1'] as num).toDouble(),
      tp2: (json['tp2'] as num).toDouble(),
      tp3: (json['tp3'] as num).toDouble(),
      atrValue: json['atr_value'] != null ? (json['atr_value'] as num).toDouble() : null,
      breakEvenTriggered: json['break_even_triggered'] as bool? ?? false,
      closePrice: json['close_price'] != null ? (json['close_price'] as num).toDouble() : null,
      pnl: json['pnl'] != null ? (json['pnl'] as num).toDouble() : null,
      pnlPct: json['pnl_pct'] != null ? (json['pnl_pct'] as num).toDouble() : null,
      tpHit: json['tp_hit'] as int?,
      confidenceScore: json['confidence_score'] != null ? (json['confidence_score'] as num).toDouble() : null,
      sessionDate: json['session_date'] as String?,
      createdAt: json['created_at'] != null ? DateTime.parse(json['created_at'] as String) : null,
      openedAt: json['opened_at'] != null ? DateTime.parse(json['opened_at'] as String) : null,
      closedAt: json['closed_at'] != null ? DateTime.parse(json['closed_at'] as String) : null,
    );
  }

  bool get isOpen => status == 'OPEN';
  bool get isClosed => status == 'CLOSED';
  bool get isLong => direction == 'LONG';
  bool get isProfitable => (pnl ?? 0) > 0;
}

class TradeStats {
  final int totalTrades;
  final int winningTrades;
  final int losingTrades;
  final double winRate;
  final double totalPnl;
  final double avgPnl;
  final double bestTrade;
  final double worstTrade;
  final double avgConfidence;

  const TradeStats({
    required this.totalTrades,
    required this.winningTrades,
    required this.losingTrades,
    required this.winRate,
    required this.totalPnl,
    required this.avgPnl,
    required this.bestTrade,
    required this.worstTrade,
    required this.avgConfidence,
  });

  factory TradeStats.fromJson(Map<String, dynamic> json) {
    return TradeStats(
      totalTrades: json['total_trades'] as int,
      winningTrades: json['winning_trades'] as int,
      losingTrades: json['losing_trades'] as int,
      winRate: (json['win_rate'] as num).toDouble(),
      totalPnl: (json['total_pnl'] as num).toDouble(),
      avgPnl: (json['avg_pnl'] as num).toDouble(),
      bestTrade: (json['best_trade'] as num).toDouble(),
      worstTrade: (json['worst_trade'] as num).toDouble(),
      avgConfidence: (json['avg_confidence'] as num).toDouble(),
    );
  }

  factory TradeStats.empty() => const TradeStats(
    totalTrades: 0, winningTrades: 0, losingTrades: 0,
    winRate: 0, totalPnl: 0, avgPnl: 0, bestTrade: 0, worstTrade: 0, avgConfidence: 0,
  );
}
