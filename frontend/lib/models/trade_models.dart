class DashboardData {
  final EquityData equity;
  final RiskStatus riskStatus;
  final List<ActiveTrade> activeTrades;
  final AIModelInfo aiModel;
  final ConnectionStatus connections;

  DashboardData({
    required this.equity,
    required this.riskStatus,
    required this.activeTrades,
    required this.aiModel,
    required this.connections,
  });

  factory DashboardData.fromJson(Map<String, dynamic> json) {
    return DashboardData(
      equity: EquityData.fromJson(json['equity'] ?? {}),
      riskStatus: RiskStatus.fromJson(json['risk_status'] ?? {}),
      activeTrades: (json['active_trades'] as List? ?? [])
          .map((t) => ActiveTrade.fromJson(t))
          .toList(),
      aiModel: AIModelInfo.fromJson(json['ai_model'] ?? {}),
      connections: ConnectionStatus.fromJson(json['connections'] ?? {}),
    );
  }
}

class EquityData {
  final double total;
  final double forex;
  final double crypto;

  EquityData({required this.total, required this.forex, required this.crypto});

  factory EquityData.fromJson(Map<String, dynamic> json) {
    return EquityData(
      total: (json['total'] ?? 0).toDouble(),
      forex: (json['forex'] ?? 0).toDouble(),
      crypto: (json['crypto'] ?? 0).toDouble(),
    );
  }
}

class RiskStatus {
  final int activeTrades;
  final int sessionTrades;
  final int maxTradesPerSession;
  final double currentDrawdown;
  final double maxDrawdown;
  final double peakEquity;
  final double currentEquity;
  final double riskPerTrade;
  final bool canTrade;

  RiskStatus({
    required this.activeTrades,
    required this.sessionTrades,
    required this.maxTradesPerSession,
    required this.currentDrawdown,
    required this.maxDrawdown,
    required this.peakEquity,
    required this.currentEquity,
    required this.riskPerTrade,
    required this.canTrade,
  });

  factory RiskStatus.fromJson(Map<String, dynamic> json) {
    return RiskStatus(
      activeTrades: json['active_trades'] ?? 0,
      sessionTrades: json['session_trades'] ?? 0,
      maxTradesPerSession: json['max_trades_per_session'] ?? 3,
      currentDrawdown: (json['current_drawdown'] ?? 0).toDouble(),
      maxDrawdown: (json['max_drawdown'] ?? 15).toDouble(),
      peakEquity: (json['peak_equity'] ?? 0).toDouble(),
      currentEquity: (json['current_equity'] ?? 0).toDouble(),
      riskPerTrade: (json['risk_per_trade'] ?? 0.75).toDouble(),
      canTrade: json['can_trade'] ?? false,
    );
  }
}

class ActiveTrade {
  final String orderId;
  final String symbol;
  final String direction;
  final double entryPrice;
  final double stopLoss;
  final double tp1;
  final double tp2;
  final double tp3;
  final bool tp1Hit;
  final bool tp2Hit;
  final bool breakEven;

  ActiveTrade({
    required this.orderId,
    required this.symbol,
    required this.direction,
    required this.entryPrice,
    required this.stopLoss,
    required this.tp1,
    required this.tp2,
    required this.tp3,
    required this.tp1Hit,
    required this.tp2Hit,
    required this.breakEven,
  });

  factory ActiveTrade.fromJson(Map<String, dynamic> json) {
    return ActiveTrade(
      orderId: json['order_id'] ?? '',
      symbol: json['symbol'] ?? '',
      direction: json['direction'] ?? '',
      entryPrice: (json['entry_price'] ?? 0).toDouble(),
      stopLoss: (json['stop_loss'] ?? 0).toDouble(),
      tp1: (json['tp1'] ?? 0).toDouble(),
      tp2: (json['tp2'] ?? 0).toDouble(),
      tp3: (json['tp3'] ?? 0).toDouble(),
      tp1Hit: json['tp1_hit'] ?? false,
      tp2Hit: json['tp2_hit'] ?? false,
      breakEven: json['break_even'] ?? false,
    );
  }
}

class AIModelInfo {
  final String version;
  final Map<String, dynamic> metrics;

  AIModelInfo({required this.version, required this.metrics});

  factory AIModelInfo.fromJson(Map<String, dynamic> json) {
    return AIModelInfo(
      version: json['version'] ?? 'N/A',
      metrics: json['metrics'] ?? {},
    );
  }
}

class ConnectionStatus {
  final bool mt5;
  final bool binance;

  ConnectionStatus({required this.mt5, required this.binance});

  factory ConnectionStatus.fromJson(Map<String, dynamic> json) {
    return ConnectionStatus(
      mt5: json['mt5'] ?? false,
      binance: json['binance'] ?? false,
    );
  }
}

class TradeSignal {
  final String symbol;
  final String marketType;
  final String timeframe;
  final String direction;
  final double entryPrice;
  final double stopLoss;
  final double tp1;
  final double tp2;
  final double tp3;
  final double confidence;
  final double riskReward;
  final String strategy;
  final String timestamp;

  TradeSignal({
    required this.symbol,
    required this.marketType,
    required this.timeframe,
    required this.direction,
    required this.entryPrice,
    required this.stopLoss,
    required this.tp1,
    required this.tp2,
    required this.tp3,
    required this.confidence,
    required this.riskReward,
    required this.strategy,
    required this.timestamp,
  });

  factory TradeSignal.fromJson(Map<String, dynamic> json) {
    return TradeSignal(
      symbol: json['symbol'] ?? '',
      marketType: json['market_type'] ?? '',
      timeframe: json['timeframe'] ?? '',
      direction: json['direction'] ?? '',
      entryPrice: (json['entry_price'] ?? 0).toDouble(),
      stopLoss: (json['stop_loss'] ?? 0).toDouble(),
      tp1: (json['take_profit_1'] ?? 0).toDouble(),
      tp2: (json['take_profit_2'] ?? 0).toDouble(),
      tp3: (json['take_profit_3'] ?? 0).toDouble(),
      confidence: (json['confidence'] ?? 0).toDouble(),
      riskReward: (json['risk_reward'] ?? 0).toDouble(),
      strategy: json['strategy'] ?? '',
      timestamp: json['timestamp'] ?? '',
    );
  }
}

class TradeHistory {
  final String id;
  final String symbol;
  final String marketType;
  final String side;
  final String status;
  final double entryPrice;
  final double? exitPrice;
  final double lotSize;
  final double? pnl;
  final double? pnlPercent;
  final double? aiConfidence;
  final String openedAt;
  final String? closedAt;

  TradeHistory({
    required this.id,
    required this.symbol,
    required this.marketType,
    required this.side,
    required this.status,
    required this.entryPrice,
    this.exitPrice,
    required this.lotSize,
    this.pnl,
    this.pnlPercent,
    this.aiConfidence,
    required this.openedAt,
    this.closedAt,
  });

  factory TradeHistory.fromJson(Map<String, dynamic> json) {
    return TradeHistory(
      id: json['id'] ?? '',
      symbol: json['symbol'] ?? '',
      marketType: json['market_type'] ?? '',
      side: json['side'] ?? '',
      status: json['status'] ?? '',
      entryPrice: (json['entry_price'] ?? 0).toDouble(),
      exitPrice: json['exit_price']?.toDouble(),
      lotSize: (json['lot_size'] ?? 0).toDouble(),
      pnl: json['pnl']?.toDouble(),
      pnlPercent: json['pnl_percent']?.toDouble(),
      aiConfidence: json['ai_confidence']?.toDouble(),
      openedAt: json['opened_at'] ?? '',
      closedAt: json['closed_at'],
    );
  }
}
