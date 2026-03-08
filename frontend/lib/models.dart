class EquityPoint {
  EquityPoint({
    required this.timestamp,
    required this.equity,
    required this.balance,
    required this.drawdown,
  });

  final DateTime timestamp;
  final double equity;
  final double balance;
  final double drawdown;

  factory EquityPoint.fromJson(Map<String, dynamic> json) => EquityPoint(
        timestamp: DateTime.parse(json["timestamp"] as String),
        equity: (json["equity"] as num).toDouble(),
        balance: (json["balance"] as num).toDouble(),
        drawdown: (json["drawdown"] as num).toDouble(),
      );
}

class EquityResponse {
  EquityResponse({
    required this.currentEquity,
    required this.currentBalance,
    required this.maxDrawdown,
    required this.points,
  });

  final double currentEquity;
  final double currentBalance;
  final double maxDrawdown;
  final List<EquityPoint> points;

  factory EquityResponse.fromJson(Map<String, dynamic> json) => EquityResponse(
        currentEquity: (json["current_equity"] as num).toDouble(),
        currentBalance: (json["current_balance"] as num).toDouble(),
        maxDrawdown: (json["max_drawdown"] as num).toDouble(),
        points: (json["points"] as List<dynamic>)
            .map((item) => EquityPoint.fromJson(item as Map<String, dynamic>))
            .toList(),
      );
}

class Trade {
  Trade({
    required this.id,
    required this.market,
    required this.symbol,
    required this.side,
    required this.status,
    required this.confidence,
    required this.entryPrice,
    required this.pnl,
    required this.openedAt,
  });

  final int id;
  final String market;
  final String symbol;
  final String side;
  final String status;
  final double confidence;
  final double entryPrice;
  final double pnl;
  final DateTime openedAt;

  factory Trade.fromJson(Map<String, dynamic> json) => Trade(
        id: json["id"] as int,
        market: json["market"] as String,
        symbol: json["symbol"] as String,
        side: json["side"] as String,
        status: json["status"] as String,
        confidence: (json["confidence"] as num).toDouble(),
        entryPrice: (json["entry_price"] as num).toDouble(),
        pnl: (json["pnl"] as num).toDouble(),
        openedAt: DateTime.parse(json["opened_at"] as String),
      );
}

class Signal {
  Signal({
    required this.id,
    required this.market,
    required this.symbol,
    required this.side,
    required this.confidence,
    required this.status,
    required this.entryPrice,
  });

  final int id;
  final String market;
  final String symbol;
  final String side;
  final double confidence;
  final String status;
  final double entryPrice;

  factory Signal.fromJson(Map<String, dynamic> json) => Signal(
        id: json["id"] as int,
        market: json["market"] as String,
        symbol: json["symbol"] as String,
        side: json["side"] as String,
        confidence: (json["confidence"] as num).toDouble(),
        status: json["status"] as String,
        entryPrice: (json["entry_price"] as num).toDouble(),
      );
}
