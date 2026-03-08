"""
Execution Engine

Orchestrates the full trade lifecycle: signal generation -> risk assessment ->
order placement -> monitoring -> TP/SL management -> position closure.
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from app.market_connectors.base import BaseMarketConnector
from app.market_connectors.mt5_connector import MT5Connector
from app.market_connectors.binance_connector import BinanceConnector
from app.strategy.strategy_engine import StrategyEngine
from app.strategy.pullback_entry import TradeSetup
from app.risk_engine.risk_manager import RiskManager, ActiveTradeRisk
from app.ai_layer.classifier import TradeClassifier
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class ExecutionEngine:
    """Main execution engine orchestrating the complete trading pipeline."""

    FOREX_SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "EURGBP"]
    CRYPTO_SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
    TIMEFRAMES = ["M15", "H1", "H4"]

    def __init__(self):
        self.settings = get_settings()
        self.strategy = StrategyEngine()
        self.risk_manager = RiskManager()
        self.classifier = TradeClassifier()
        self.mt5 = MT5Connector()
        self.binance = BinanceConnector()
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None

    async def initialize(self) -> dict:
        """Initialize all components and connections."""
        status = {"mt5": False, "binance": False, "ai_model": False}

        try:
            status["mt5"] = await self.mt5.connect()
        except Exception as e:
            logger.error("MT5 initialization failed", error=str(e))

        try:
            status["binance"] = await self.binance.connect()
        except Exception as e:
            logger.error("Binance initialization failed", error=str(e))

        try:
            loaded = self.classifier.load_model()
            if not loaded:
                self.classifier._create_default_model()
            status["ai_model"] = True
        except Exception as e:
            logger.error("AI model initialization failed", error=str(e))

        account = await self._get_primary_account_info()
        self.risk_manager.initialize(account.get("equity", 10000))

        logger.info("Execution engine initialized", status=status)
        return status

    async def shutdown(self) -> None:
        """Gracefully shut down all connections."""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
        await self.mt5.disconnect()
        await self.binance.disconnect()
        logger.info("Execution engine shut down")

    async def scan_markets(self) -> list[dict]:
        """Scan all configured markets for trade setups."""
        all_signals = []

        forex_tasks = [
            self._scan_symbol(symbol, "forex") for symbol in self.FOREX_SYMBOLS
        ]
        crypto_tasks = [
            self._scan_symbol(symbol, "crypto") for symbol in self.CRYPTO_SYMBOLS
        ]

        results = await asyncio.gather(*forex_tasks, *crypto_tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                logger.error("Scan failed", error=str(result))
                continue
            all_signals.extend(result)

        all_signals.sort(key=lambda x: x.get("confidence", 0), reverse=True)
        logger.info("Market scan complete", signals_found=len(all_signals))
        return all_signals

    async def _scan_symbol(self, symbol: str, market_type: str) -> list[dict]:
        """Scan a single symbol across timeframes."""
        connector = self.mt5 if market_type == "forex" else self.binance
        signals = []

        for tf in self.TIMEFRAMES:
            try:
                df = await connector.get_ohlcv(symbol, tf, 500)
                if df.empty:
                    continue

                setups = await self.strategy.analyze(df, symbol, tf)

                for setup in setups:
                    ai_score = self.classifier.score_setup(
                        df, setup.direction, setup.strategy_name, setup.confidence
                    )
                    setup.confidence = ai_score

                    signals.append({
                        "symbol": symbol,
                        "market_type": market_type,
                        "timeframe": tf,
                        "direction": setup.direction,
                        "entry_price": setup.entry_price,
                        "stop_loss": setup.stop_loss,
                        "take_profit_1": setup.take_profit_1,
                        "take_profit_2": setup.take_profit_2,
                        "take_profit_3": setup.take_profit_3,
                        "confidence": setup.confidence,
                        "risk_reward": setup.risk_reward_ratio,
                        "strategy": setup.strategy_name,
                        "details": setup.details,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
            except Exception as e:
                logger.error("Symbol scan failed", symbol=symbol, tf=tf, error=str(e))

        return signals

    async def execute_signal(self, signal: dict) -> dict:
        """Execute a trading signal after risk assessment."""
        market_type = signal["market_type"]
        connector = self.mt5 if market_type == "forex" else self.binance

        setup = TradeSetup(
            direction=signal["direction"],
            entry_price=signal["entry_price"],
            stop_loss=signal["stop_loss"],
            take_profit_1=signal["take_profit_1"],
            take_profit_2=signal["take_profit_2"],
            take_profit_3=signal["take_profit_3"],
            risk_reward_ratio=signal["risk_reward"],
            confidence=signal["confidence"],
            strategy_name=signal["strategy"],
            timeframe=signal["timeframe"],
            symbol=signal["symbol"],
        )

        account = await connector.get_account_info()
        equity = account.get("equity", 10000)

        assessment = self.risk_manager.assess_trade(setup, equity, market_type)

        if not assessment.approved:
            logger.warning(
                "Signal rejected by risk manager",
                symbol=signal["symbol"], reason=assessment.rejection_reason,
            )
            return {
                "executed": False,
                "reason": assessment.rejection_reason,
                "risk_score": assessment.risk_score,
            }

        side = "buy" if setup.direction == "long" else "sell"
        lot_size = assessment.position_size.lot_size

        result = await connector.place_market_order(
            symbol=setup.symbol,
            side=side,
            volume=lot_size,
            stop_loss=setup.stop_loss,
            take_profit=setup.take_profit_1,
            comment=f"AI:{setup.strategy_name}:{setup.confidence:.0%}",
        )

        if result.get("success"):
            order_id = result["order_id"]
            active_trade = ActiveTradeRisk(
                order_id=order_id,
                symbol=setup.symbol,
                direction=setup.direction,
                entry_price=result.get("price", setup.entry_price),
                stop_loss=setup.stop_loss,
                take_profit_1=setup.take_profit_1,
                take_profit_2=setup.take_profit_2,
                take_profit_3=setup.take_profit_3,
                lot_size=lot_size,
            )
            self.risk_manager.register_trade(active_trade)

            logger.info(
                "Trade executed",
                order_id=order_id, symbol=setup.symbol,
                direction=setup.direction, lots=lot_size,
            )

            return {
                "executed": True,
                "order_id": order_id,
                "symbol": setup.symbol,
                "direction": setup.direction,
                "entry_price": result.get("price"),
                "stop_loss": setup.stop_loss,
                "take_profit_1": setup.take_profit_1,
                "take_profit_2": setup.take_profit_2,
                "take_profit_3": setup.take_profit_3,
                "lot_size": lot_size,
                "confidence": setup.confidence,
                "risk_amount": assessment.position_size.risk_amount,
                "risk_score": assessment.risk_score,
            }
        else:
            logger.error("Order placement failed", error=result.get("error"))
            return {
                "executed": False,
                "reason": f"Order failed: {result.get('error', 'unknown')}",
            }

    async def monitor_positions(self) -> list[dict]:
        """Monitor all active positions for TP/SL management."""
        actions_taken = []

        for order_id, trade in list(self.risk_manager.active_trades.items()):
            connector = self.mt5 if trade.symbol in self.FOREX_SYMBOLS else self.binance

            try:
                price_data = await connector.get_current_price(trade.symbol)
                current_price = price_data.get(
                    "bid" if trade.direction == "long" else "ask", 0
                )
                if current_price == 0:
                    continue

                actions = self.risk_manager.check_tp_levels(order_id, current_price)

                if actions.get("move_to_breakeven"):
                    await connector.modify_order(
                        order_id, stop_loss=actions["new_stop_loss"]
                    )
                    actions_taken.append({
                        "order_id": order_id,
                        "action": "break_even",
                        "new_sl": actions["new_stop_loss"],
                    })

                if actions.get("close_partial_1"):
                    await connector.close_position(
                        order_id, volume=actions["partial_volume_1"]
                    )
                    actions_taken.append({
                        "order_id": order_id,
                        "action": "partial_close_tp1",
                        "volume": actions["partial_volume_1"],
                    })

                if actions.get("close_partial_2"):
                    await connector.close_position(
                        order_id, volume=actions["partial_volume_2"]
                    )
                    if actions.get("trail_stop"):
                        await connector.modify_order(
                            order_id, stop_loss=actions["new_stop_loss"]
                        )
                    actions_taken.append({
                        "order_id": order_id,
                        "action": "partial_close_tp2",
                        "volume": actions["partial_volume_2"],
                    })

                if actions.get("close_remaining"):
                    await connector.close_position(order_id)
                    self.risk_manager.remove_trade(order_id)
                    actions_taken.append({
                        "order_id": order_id,
                        "action": "full_close_tp3",
                    })

            except Exception as e:
                logger.error("Position monitoring failed", order_id=order_id, error=str(e))

        return actions_taken

    async def start_auto_trading(self, scan_interval: int = 300) -> None:
        """Start the automated trading loop."""
        self._running = True
        logger.info("Auto trading started", interval=scan_interval)

        while self._running:
            try:
                await self.monitor_positions()
                signals = await self.scan_markets()

                for signal in signals:
                    if signal["confidence"] >= 0.6:
                        result = await self.execute_signal(signal)
                        if result.get("executed"):
                            break

                await asyncio.sleep(scan_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Auto trading loop error", error=str(e))
                await asyncio.sleep(60)

        logger.info("Auto trading stopped")

    async def stop_auto_trading(self) -> None:
        self._running = False

    async def train_ai_model(self, symbol: str = "EURUSD", timeframe: str = "H1") -> dict:
        """Train the AI model on historical data."""
        connector = self.mt5 if symbol in self.FOREX_SYMBOLS else self.binance
        df = await connector.get_ohlcv(symbol, timeframe, 5000)
        if df.empty:
            return {"error": "No data available for training"}
        return self.classifier.train(df)

    async def get_dashboard_data(self) -> dict:
        """Get comprehensive dashboard data."""
        mt5_account = await self.mt5.get_account_info()
        binance_account = await self.binance.get_account_info()

        mt5_equity = mt5_account.get("equity", 0)
        binance_equity = binance_account.get("equity", 0)
        total_equity = mt5_equity + binance_equity

        return {
            "equity": {
                "total": round(total_equity, 2),
                "forex": round(mt5_equity, 2),
                "crypto": round(binance_equity, 2),
            },
            "risk_status": self.risk_manager.get_status(total_equity),
            "active_trades": [
                {
                    "order_id": t.order_id,
                    "symbol": t.symbol,
                    "direction": t.direction,
                    "entry_price": t.entry_price,
                    "stop_loss": t.stop_loss,
                    "tp1": t.take_profit_1,
                    "tp2": t.take_profit_2,
                    "tp3": t.take_profit_3,
                    "tp1_hit": t.tp1_hit,
                    "tp2_hit": t.tp2_hit,
                    "break_even": t.break_even_set,
                }
                for t in self.risk_manager.active_trades.values()
            ],
            "ai_model": {
                "version": self.classifier.model_version,
                "metrics": self.classifier.metrics,
            },
            "connections": {
                "mt5": self.mt5._connected,
                "binance": self.binance._connected,
            },
        }

    async def _get_primary_account_info(self) -> dict:
        mt5_info = await self.mt5.get_account_info()
        if mt5_info.get("equity", 0) > 0:
            return mt5_info
        return await self.binance.get_account_info()
