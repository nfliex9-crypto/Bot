class SignalModel {
  final String direction;
  final bool liquiditySweep;
  final bool breakOfStructure;
  final bool pullbackEntry;
  final String reason;

  const SignalModel({
    required this.direction,
    required this.liquiditySweep,
    required this.breakOfStructure,
    required this.pullbackEntry,
    required this.reason,
  });

  factory SignalModel.fromJson(Map<String, dynamic> json) {
    return SignalModel(
      direction: json['direction'] as String? ?? 'none',
      liquiditySweep: json['liquidity_sweep'] as bool? ?? false,
      breakOfStructure: json['break_of_structure'] as bool? ?? false,
      pullbackEntry: json['pullback_entry'] as bool? ?? false,
      reason: json['reason'] as String? ?? '',
    );
  }
}

class EquityPoint {
  final DateTime timestamp;
  final double equity;

  const EquityPoint({required this.timestamp, required this.equity});

  factory EquityPoint.fromJson(Map<String, dynamic> json) {
    return EquityPoint(
      timestamp: DateTime.parse(json['timestamp'] as String),
      equity: (json['equity'] as num).toDouble(),
    );
  }
}

class TradeModel {
  final int id;
  final String market;
  final String symbol;
  final String side;
  final double entryPrice;
  final double confidence;
  final String status;

  const TradeModel({
    required this.id,
    required this.market,
    required this.symbol,
    required this.side,
    required this.entryPrice,
    required this.confidence,
    required this.status,
  });

  factory TradeModel.fromJson(Map<String, dynamic> json) {
    return TradeModel(
      id: json['id'] as int,
      market: json['market'] as String,
      symbol: json['symbol'] as String,
      side: json['side'] as String,
      entryPrice: (json['entry_price'] as num).toDouble(),
      confidence: (json['confidence'] as num).toDouble(),
      status: json['status'] as String,
    );
  }
}

class DashboardModel {
  final List<EquityPoint> equity;
  final List<TradeModel> tradeHistory;
  final double aiConfidence;
  final SignalModel liveSignal;

  const DashboardModel({
    required this.equity,
    required this.tradeHistory,
    required this.aiConfidence,
    required this.liveSignal,
  });

  factory DashboardModel.fromJson(Map<String, dynamic> json) {
    return DashboardModel(
      equity: ((json['equity'] ?? []) as List<dynamic>)
          .map((e) => EquityPoint.fromJson(e as Map<String, dynamic>))
          .toList(),
      tradeHistory: ((json['trade_history'] ?? []) as List<dynamic>)
          .map((e) => TradeModel.fromJson(e as Map<String, dynamic>))
          .toList(),
      aiConfidence: (json['ai_confidence'] as num?)?.toDouble() ?? 0.0,
      liveSignal: SignalModel.fromJson(json['live_signal'] as Map<String, dynamic>),
    );
  }
}
