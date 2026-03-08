"""
Trade Manager Service

Orchestrates the full trade lifecycle:
1. Signal scanning and generation
2. AI confidence scoring
3. Risk engine validation
4. Order execution
5. Real-time position monitoring (break-even, trailing stop, TP management)
6. Trade recording to database
"""

import logging
import asyncio
from typing import List, Optional, Dict
from datetime import datetime, timezone, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.config import settings
from app.strategy.signal_generator import SignalGenerator
from app.risk.engine import RiskEngine
from app.ai.classifier import TradingClassifier
from app.execution.mt5_executor import MT5Executor
from app.execution.binance_executor import BinanceExecutor
from app.services.market_data import MarketDataService
from app.models.trade import Trade, TradeStatus, TradeDirection, Market
from app.models.signal import Signal, SignalStatus
from app.models.account import Account, EquitySnapshot, BrokerType

logger = logging.getLogger(__name__)

FOREX_SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "XAUUSD"]
CRYPTO_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
TIMEFRAME = "H1"


class TradeManager:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.risk_engine = RiskEngine(
            risk_per_trade_pct=settings.RISK_PER_TRADE_PCT,
            max_drawdown_pct=settings.MAX_DRAWDOWN_PCT,
            max_trades_per_session=settings.MAX_TRADES_PER_SESSION,
            tp1_ratio=settings.TP1_RATIO,
            tp2_ratio=settings.TP2_RATIO,
            tp3_ratio=settings.TP3_RATIO,
        )
        self.classifier = TradingClassifier(model_path=settings.MODEL_PATH)
        self.market_data = MarketDataService()
        self.mt5 = MT5Executor(
            login=settings.MT5_LOGIN,
            password=settings.MT5_PASSWORD,
            server=settings.MT5_SERVER,
        )
        self.binance = BinanceExecutor(
            api_key=settings.BINANCE_API_KEY,
            api_secret=settings.BINANCE_API_SECRET,
            testnet=settings.BINANCE_TESTNET,
        )
        self._running = False
        self._ws_broadcast_callback = None

    def set_broadcast_callback(self, callback):
        """Register a callback for WebSocket signal broadcasting."""
        self._ws_broadcast_callback = callback

    async def initialize(self):
        await self.market_data.initialize()
        await self.mt5.connect()
        logger.info("TradeManager initialized")

    async def scan_and_generate_signals(self) -> List[dict]:
        """Run the full signal scanning pipeline across all symbols."""
        now = datetime.now(timezone.utc)
        hour = now.hour

        # Only trade during active market hours
        if not (settings.SESSION_START_HOUR <= hour < settings.SESSION_END_HOUR):
            logger.debug("Outside trading session hours, skipping scan")
            return []

        signals = []
        all_data = await self.market_data.scan_all(FOREX_SYMBOLS, CRYPTO_SYMBOLS, TIMEFRAME)

        for key, df in all_data.items():
            if df is None:
                continue

            market, symbol = key.split(":", 1)

            try:
                generator = SignalGenerator(
                    symbol=symbol,
                    market=market,
                    timeframe=TIMEFRAME,
                    tp1_ratio=settings.TP1_RATIO,
                    tp2_ratio=settings.TP2_RATIO,
                    tp3_ratio=settings.TP3_RATIO,
                )
                raw_signal = generator.generate(df)

                if raw_signal is None:
                    continue

                # AI scoring
                confidence, feature_importance = self.classifier.predict(df, raw_signal)
                raw_signal["confidence_score"] = round(confidence, 4)
                raw_signal["feature_importance"] = feature_importance
                raw_signal["model_version"] = self.classifier.model_version

                # Save to DB
                signal_record = await self._save_signal(raw_signal)
                raw_signal["signal_id"] = signal_record.id

                # Broadcast via WebSocket
                if self._ws_broadcast_callback:
                    await self._ws_broadcast_callback(raw_signal)

                # Only execute if confidence meets threshold
                if confidence >= settings.MIN_CONFIDENCE_THRESHOLD:
                    await self._process_signal_for_execution(raw_signal, signal_record, df)

                signals.append(raw_signal)
                logger.info(f"Signal: {symbol} {raw_signal['direction']} | Confidence: {confidence:.2%}")

            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}", exc_info=True)

        return signals

    async def _process_signal_for_execution(
        self,
        signal: dict,
        signal_record: Signal,
        df,
    ):
        """Validate with risk engine and execute if approved."""
        account = await self._get_or_create_account(signal["market"])
        if account is None:
            return

        validation = self.risk_engine.validate_trade(
            account_balance=account.current_balance,
            account_equity=account.equity or account.current_balance,
            peak_equity=account.peak_equity or account.current_balance,
            session_trades_today=account.session_trades_today,
            session_date=account.session_date or "",
            entry_price=signal["entry_price"],
            stop_loss=signal["stop_loss"],
            direction=signal["direction"],
            symbol=signal["symbol"],
            market=signal["market"],
            confidence_score=signal["confidence_score"],
            min_confidence=settings.MIN_CONFIDENCE_THRESHOLD,
        )

        if not validation.approved:
            logger.info(f"Trade rejected: {validation.rejection_reason}")
            signal_record.status = SignalStatus.REJECTED
            signal_record.notes = validation.rejection_reason
            await self.db.commit()
            return

        # Execute the order
        today = date.today().isoformat()
        session_trade_num = account.session_trades_today + 1

        result = await self._execute_order(
            symbol=signal["symbol"],
            market=signal["market"],
            direction=signal["direction"],
            lot_size=validation.lot_size,
            entry_price=signal["entry_price"],
            stop_loss=validation.stop_loss,
            tp1=validation.tp1,
            tp2=validation.tp2,
            tp3=validation.tp3,
        )

        if result["success"]:
            trade = Trade(
                symbol=signal["symbol"],
                market=Market(signal["market"]),
                direction=TradeDirection(signal["direction"]),
                status=TradeStatus.OPEN,
                entry_price=result.get("entry_price", signal["entry_price"]),
                lot_size=validation.lot_size,
                risk_amount=validation.risk_amount,
                stop_loss=validation.stop_loss,
                tp1=validation.tp1,
                tp2=validation.tp2,
                tp3=validation.tp3,
                atr_value=signal.get("atr_value"),
                broker_order_id=result.get("order_id"),
                confidence_score=signal["confidence_score"],
                signal_id=signal_record.id,
                session_date=today,
                session_trade_number=session_trade_num,
                opened_at=datetime.now(timezone.utc),
            )
            self.db.add(trade)

            # Update signal status
            signal_record.status = SignalStatus.EXECUTED
            signal_record.executed_at = datetime.now(timezone.utc)

            # Update account session count
            account.session_trades_today = session_trade_num
            account.session_date = today

            await self.db.commit()
            logger.info(f"Trade opened: {signal['symbol']} {signal['direction']} @ {result.get('entry_price')}")
        else:
            logger.error(f"Order execution failed: {result.get('error')}")

    async def _execute_order(
        self, symbol: str, market: str, direction: str,
        lot_size: float, entry_price: float, stop_loss: float,
        tp1: float, tp2: float, tp3: float,
    ) -> dict:
        try:
            if market.upper() == "FOREX":
                order = await self.mt5.place_market_order(
                    symbol=symbol, direction=direction, lot_size=lot_size,
                    stop_loss=stop_loss, tp1=tp1, tp2=tp2, tp3=tp3,
                )
                return {
                    "success": order.success,
                    "order_id": order.order_id,
                    "entry_price": order.entry_price,
                    "error": order.error,
                }
            elif market.upper() == "CRYPTO":
                result = await self.binance.place_market_order(
                    symbol=symbol, direction=direction, quantity=lot_size,
                    stop_loss=stop_loss, tp1=tp1, tp2=tp2, tp3=tp3,
                )
                return result
        except Exception as e:
            logger.error(f"Execute order error: {e}")
            return {"success": False, "error": str(e)}

    async def monitor_open_trades(self):
        """
        Check all open trades for:
        - Break-even trigger (when TP1 reached)
        - TP2/TP3 management
        - Stop out detection
        """
        stmt = select(Trade).where(Trade.status == TradeStatus.OPEN)
        result = await self.db.execute(stmt)
        open_trades = result.scalars().all()

        for trade in open_trades:
            try:
                price_info = await self.market_data.get_price(trade.symbol, trade.market.value)
                if not price_info:
                    continue

                current_price = price_info["bid"] if trade.direction == TradeDirection.LONG else price_info["ask"]

                # Check break-even
                if not trade.break_even_triggered:
                    be_result = self.risk_engine.check_break_even(
                        entry_price=trade.entry_price,
                        current_price=current_price,
                        tp1=trade.tp1,
                        current_stop=trade.stop_loss,
                        direction=trade.direction.value,
                        tp1_already_hit=trade.tp_hit is not None and trade.tp_hit >= 1,
                    )
                    if be_result.triggered:
                        trade.stop_loss = be_result.new_stop_loss
                        trade.break_even_triggered = True
                        trade.notes = (trade.notes or "") + f"\n{be_result.reason}"

                        # Update broker SL
                        if trade.broker_order_id:
                            if trade.market == Market.FOREX:
                                await self.mt5.modify_position(trade.broker_order_id, be_result.new_stop_loss)
                            logger.info(f"Break-even triggered for trade {trade.id}: SL -> {be_result.new_stop_loss:.5f}")

                # Check if stop hit
                direction = trade.direction.value
                sl_hit = (
                    (direction == "LONG" and current_price <= trade.stop_loss) or
                    (direction == "SHORT" and current_price >= trade.stop_loss)
                )
                if sl_hit:
                    await self._close_trade(trade, current_price, reason="STOP_LOSS")
                    continue

                # Check TP2
                if trade.tp_hit == 1:
                    tp2_hit = (
                        (direction == "LONG" and current_price >= trade.tp2) or
                        (direction == "SHORT" and current_price <= trade.tp2)
                    )
                    if tp2_hit:
                        trade.tp_hit = 2
                        await self.db.commit()
                        logger.info(f"TP2 hit for trade {trade.id}")

                # Check TP3 (close full position)
                if trade.tp_hit == 2:
                    tp3_hit = (
                        (direction == "LONG" and current_price >= trade.tp3) or
                        (direction == "SHORT" and current_price <= trade.tp3)
                    )
                    if tp3_hit:
                        await self._close_trade(trade, current_price, reason="TP3")
                        continue

                # Check TP1
                if trade.tp_hit is None:
                    tp1_hit = (
                        (direction == "LONG" and current_price >= trade.tp1) or
                        (direction == "SHORT" and current_price <= trade.tp1)
                    )
                    if tp1_hit:
                        trade.tp_hit = 1
                        await self.db.commit()
                        logger.info(f"TP1 hit for trade {trade.id}")

            except Exception as e:
                logger.error(f"Error monitoring trade {trade.id}: {e}")

        await self.db.commit()

    async def _close_trade(self, trade: Trade, close_price: float, reason: str = ""):
        """Mark a trade as closed and calculate PnL."""
        direction = trade.direction.value
        if direction == "LONG":
            pnl_raw = (close_price - trade.entry_price) * trade.lot_size
        else:
            pnl_raw = (trade.entry_price - close_price) * trade.lot_size

        trade.status = TradeStatus.CLOSED
        trade.close_price = close_price
        trade.pnl = round(pnl_raw, 2)
        trade.pnl_pct = round((pnl_raw / trade.risk_amount) * 100, 2) if trade.risk_amount else 0
        trade.closed_at = datetime.now(timezone.utc)
        trade.notes = (trade.notes or "") + f"\nClosed: {reason} @ {close_price}"

        await self._update_account_after_close(trade)
        await self.db.commit()
        logger.info(f"Trade {trade.id} closed: {reason} | PnL: {trade.pnl:.2f}")

    async def _get_or_create_account(self, market: str) -> Optional[Account]:
        broker = BrokerType.MT5 if market.upper() == "FOREX" else BrokerType.BINANCE
        stmt = select(Account).where(
            and_(Account.broker == broker, Account.is_active == True)
        )
        result = await self.db.execute(stmt)
        account = result.scalar_one_or_none()

        if account is None:
            account = Account(
                broker=broker,
                account_name=f"{broker.value} Trading Account",
                initial_balance=10000.0,
                current_balance=10000.0,
                equity=10000.0,
                peak_equity=10000.0,
            )
            self.db.add(account)
            await self.db.commit()
            await self.db.refresh(account)

        return account

    async def _update_account_after_close(self, trade: Trade):
        account = await self._get_or_create_account(trade.market.value)
        if account is None:
            return

        account.total_trades += 1
        account.total_pnl = (account.total_pnl or 0) + (trade.pnl or 0)
        account.current_balance += (trade.pnl or 0)

        if (trade.pnl or 0) > 0:
            account.winning_trades += 1
        else:
            account.losing_trades += 1

        # Update drawdown
        if account.current_balance > (account.peak_equity or account.initial_balance):
            account.peak_equity = account.current_balance

        if account.peak_equity and account.peak_equity > 0:
            dd = ((account.peak_equity - account.current_balance) / account.peak_equity) * 100
            account.current_drawdown_pct = round(dd, 2)
            account.max_drawdown_pct = max(account.max_drawdown_pct or 0, dd)

        await self.db.commit()

    async def snapshot_equity(self):
        """Periodically snapshot account equity for the equity curve."""
        accounts_query = select(Account).where(Account.is_active == True)
        result = await self.db.execute(accounts_query)
        accounts = result.scalars().all()

        open_trades_query = select(Trade).where(Trade.status == TradeStatus.OPEN)
        open_result = await self.db.execute(open_trades_query)
        open_count = len(open_result.scalars().all())

        for account in accounts:
            snapshot = EquitySnapshot(
                account_id=account.id,
                broker=account.broker.value,
                equity=account.equity or account.current_balance,
                balance=account.current_balance,
                drawdown_pct=account.current_drawdown_pct or 0.0,
                open_trades=open_count,
            )
            self.db.add(snapshot)

        await self.db.commit()
