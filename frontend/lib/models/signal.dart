class Signal {
  final int id;
  final String symbol;
  final String market;
  final String timeframe;
  final String direction;
  final String status;
  final double? entryZoneLow;
  final double? entryZoneHigh;
  final double? stopLoss;
  final double? tp1;
  final double? tp2;
  final double? tp3;
  final bool liquiditySweepDetected;
  final bool bosDetected;
  final bool pullbackConfirmed;
  final double? sweepLevel;
  final double? bosLevel;
  final double? atrValue;
  final double? confidenceScore;
  final Map<String, dynamic>? featureImportance;
  final String? marketStructure;
  final String? session;
  final DateTime? createdAt;

  const Signal({
    required this.id,
    required this.symbol,
    required this.market,
    required this.timeframe,
    required this.direction,
    required this.status,
    this.entryZoneLow,
    this.entryZoneHigh,
    this.stopLoss,
    this.tp1,
    this.tp2,
    this.tp3,
    required this.liquiditySweepDetected,
    required this.bosDetected,
    required this.pullbackConfirmed,
    this.sweepLevel,
    this.bosLevel,
    this.atrValue,
    this.confidenceScore,
    this.featureImportance,
    this.marketStructure,
    this.session,
    this.createdAt,
  });

  factory Signal.fromJson(Map<String, dynamic> json) {
    return Signal(
      id: json['id'] as int,
      symbol: json['symbol'] as String,
      market: json['market'] as String,
      timeframe: json['timeframe'] as String,
      direction: json['direction'] as String,
      status: json['status'] as String,
      entryZoneLow: json['entry_zone_low'] != null ? (json['entry_zone_low'] as num).toDouble() : null,
      entryZoneHigh: json['entry_zone_high'] != null ? (json['entry_zone_high'] as num).toDouble() : null,
      stopLoss: json['stop_loss'] != null ? (json['stop_loss'] as num).toDouble() : null,
      tp1: json['tp1'] != null ? (json['tp1'] as num).toDouble() : null,
      tp2: json['tp2'] != null ? (json['tp2'] as num).toDouble() : null,
      tp3: json['tp3'] != null ? (json['tp3'] as num).toDouble() : null,
      liquiditySweepDetected: json['liquidity_sweep_detected'] as bool? ?? false,
      bosDetected: json['bos_detected'] as bool? ?? false,
      pullbackConfirmed: json['pullback_confirmed'] as bool? ?? false,
      sweepLevel: json['sweep_level'] != null ? (json['sweep_level'] as num).toDouble() : null,
      bosLevel: json['bos_level'] != null ? (json['bos_level'] as num).toDouble() : null,
      atrValue: json['atr_value'] != null ? (json['atr_value'] as num).toDouble() : null,
      confidenceScore: json['confidence_score'] != null ? (json['confidence_score'] as num).toDouble() : null,
      featureImportance: json['feature_importance'] as Map<String, dynamic>?,
      marketStructure: json['market_structure'] as String?,
      session: json['session'] as String?,
      createdAt: json['created_at'] != null ? DateTime.parse(json['created_at'] as String) : null,
    );
  }

  bool get isLong => direction == 'LONG';
  bool get isActive => status == 'ACTIVE';
  bool get isHighConfidence => (confidenceScore ?? 0) >= 0.75;
  int get confluenceCount =>
      (liquiditySweepDetected ? 1 : 0) +
      (bosDetected ? 1 : 0) +
      (pullbackConfirmed ? 1 : 0);
}
