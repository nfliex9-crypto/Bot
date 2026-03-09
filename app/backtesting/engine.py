"""
Backtesting Engine.

Event-driven bar-by-bar backtester that replays historical data through
the full strategy pipeline (MTF analysis → AI scoring → execution → management).

Key features:
  - No lookahead bias (strict bar-by-bar slicing)
  - Realistic execution via MarketSimulator (spread, slippage, commission)
  - Full trade lifecycle (TP1 partial, TP2 partial, TP3, BE, SL)
  - Position management matching production TradeManager logic
  - Exportable results with equity curve and trade log
"""
import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Dict, Tuple
import pandas as pd
import numpy as np

from app.backtesting.simulator import MarketSimulator, SimulatedBar, ExecutionResult
from app.backtesting.metrics import BacktestMetrics, TradeStats
from app.core.strategy.multi_timeframe import MultiTimeframeAnalyzer
from app.core.ai.classifier import TradeClassifier
from app.core.risk_manager import RiskManager
from app.core.session_filter import SessionFilter
from app.utils.indicators import add_all_indicators
from app.utils.logger import get_logger

logger = get_logger("backtest_engine")

UTC = timezone.utc


@dataclass
class BacktestConfig:
    symbol: str
    market_type: str = "forex"
    initial_balance: float = 3000.0
    risk_per_trade: float = 0.0075
    max_drawdown_stop: float = 0.20        # Stop backtest if DD exceeds this
    max_trades_per_session: int = 5
    min_ai_confidence: float = 0.60
    use_session_filter: bool = True
    spread_multiplier: float = 1.0
    slippage_factor: float = 0.3
    commission_per_lot: float = 3.5
    warmup_bars: int = 100
    scan_every_n_bars: int = 3             # Scan every N M5 bars (~15 min)
    tp1_ratio: float = 1.0
    tp2_ratio: float = 1.5
    tp3_ratio: float = 2.0
    random_seed: int = 42


@dataclass
class OpenPosition:
    trade_id: int
    symbol: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    take_profit_3: float
    lot_size: float
    entry_bar: int
    remaining_lots: float
    tp1_hit: bool = False
    tp2_hit: bool = False
    breakeven_moved: bool = False
    mae: float = 0.0
    mfe: float = 0.0
    total_pnl: float = 0.0
    total_commission: float = 0.0


@dataclass
class BacktestResult:
    config: BacktestConfig
    metrics: dict
    trade_log: List[dict]
    equity_curve: List[dict]
    open_at_end: int = 0
    duration_seconds: float = 0.0
    error: Optional[str] = None


class BacktestEngine:
    """
    Runs a full backtest of the Sweep+BOS+Pullback strategy.
    """

    def __init__(self, config: BacktestConfig):
        self.config = config
        self.simulator = MarketSimulator(
            spread_multiplier=config.spread_multiplier,
            slippage_factor=config.slippage_factor,
            commission_per_lot=config.commission_per_lot,
            random_seed=config.random_seed,
        )
        self.mtf_analyzer = MultiTimeframeAnalyzer()
        self.classifier = TradeClassifier(min_confidence=config.min_ai_confidence)
        self.session_filter = SessionFilter()
        self.bt_metrics = BacktestMetrics()

        self._balance = config.initial_balance
        self._peak_balance = config.initial_balance
        self._positions: List[OpenPosition] = []
        self._closed: List[TradeStats] = []
        self._next_id = 1

    def run(
        self,
        h1_df: pd.DataFrame,
        m15_df: pd.DataFrame,
        m5_df: pd.DataFrame,
    ) -> BacktestResult:
        """
        Run the full backtest synchronously.
        """
        t0 = time.perf_counter()
        cfg = self.config
        error = None

        logger.info(
            f"Backtest start: {cfg.symbol} "
            f"balance=${cfg.initial_balance} warmup={cfg.warmup_bars}"
        )

        try:
            for bar_idx, bar, m5_hist in self.simulator.iter_bars(
                m5_df, cfg.symbol, "M5", cfg.warmup_bars
            ):
                # Update open positions on every bar
                self._update_positions(bar)

                # Max drawdown stop
                dd = (self._peak_balance - self._balance) / (self._peak_balance + 1e-10)
                if dd >= cfg.max_drawdown_stop:
                    logger.warning(
                        f"Backtest stopped at bar {bar_idx}: max drawdown "
                        f"{dd:.1%} >= {cfg.max_drawdown_stop:.1%}"
                    )
                    break

                # Scan for new setups periodically
                if bar_idx % cfg.scan_every_n_bars != 0:
                    continue
                if len(self._positions) >= cfg.max_trades_per_session:
                    continue

                # Session filter
                if cfg.use_session_filter:
                    session = self.session_filter.get_current_session(
                        bar.time.to_pydatetime()
                    )
                    if not session.is_active:
                        continue

                # Get aligned H1/M15 slices (no lookahead)
                h1_slice = self._align_slice(h1_df, bar.time, 100)
                m15_slice = self._align_slice(m15_df, bar.time, 100)

                if len(h1_slice) < 50 or len(m15_slice) < 30 or len(m5_hist) < 30:
                    continue

                # Strategy + AI
                try:
                    mtf = self.mtf_analyzer.analyze(
                        cfg.symbol, h1_slice, m15_slice, m5_hist
                    )
                except Exception:
                    continue

                if not mtf.tradeable or mtf.m5_entry is None:
                    continue

                pred = self.classifier.predict(h1_slice, m15_slice, m5_hist, mtf)
                if not pred.should_trade:
                    continue

                # Execute
                self._open_position(bar, mtf.m5_entry, bar_idx)

        except Exception as e:
            error = str(e)
            logger.error(f"Backtest error: {e}", exc_info=True)

        # Close remaining positions at last price
        for pos in list(self._positions):
            last_price = m5_df.iloc[-1]["close"]
            self._force_close(pos, last_price, m5_df.index[-1] - pos.entry_bar)

        metrics = self.bt_metrics.compute(self._closed, cfg.initial_balance)
        equity_curve = self.bt_metrics.equity_curve(self._closed, cfg.initial_balance)
        trade_log = self._build_trade_log()

        duration = time.perf_counter() - t0
        logger.info(
            f"Backtest done: {len(self._closed)} trades "
            f"WR={metrics.get('win_rate_pct','N/A')} "
            f"PnL={metrics.get('pnl',{}).get('total','N/A')} "
            f"({duration:.1f}s)"
        )

        return BacktestResult(
            config=cfg,
            metrics=metrics,
            trade_log=trade_log,
            equity_curve=equity_curve,
            open_at_end=len(self._positions),
            duration_seconds=round(duration, 2),
            error=error,
        )

    # ── Position management ──────────────────────────────────────────────

    def _open_position(self, bar: SimulatedBar, entry, bar_idx: int):
        """Open a new simulated position."""
        risk_amount = self._balance * self.config.risk_per_trade
        sl_dist = abs(entry.entry_price - entry.stop_loss)
        if sl_dist <= 0:
            return

        # Simple lot sizing: risk_amount / sl_pips / pip_value
        pip_size = 0.01 if bar.symbol.endswith("JPY") else (1.0 if "USDT" in bar.symbol else 0.0001)
        sl_pips = sl_dist / pip_size
        pip_value = 10.0  # approximate
        lot_size = max(0.01, round(risk_amount / (sl_pips * pip_value), 2))
        lot_size = min(lot_size, 10.0)

        exec_result = self.simulator.simulate_entry(
            entry.direction, entry.entry_price, bar, lot_size
        )
        if not exec_result.success:
            return

        pos = OpenPosition(
            trade_id=self._next_id,
            symbol=bar.symbol,
            direction=entry.direction,
            entry_price=exec_result.filled_price,
            stop_loss=entry.stop_loss,
            take_profit_1=entry.take_profit_1,
            take_profit_2=entry.take_profit_2 or 0.0,
            take_profit_3=entry.take_profit_3 or 0.0,
            lot_size=lot_size,
            entry_bar=bar_idx,
            remaining_lots=lot_size,
            total_commission=exec_result.commission,
        )
        self._positions.append(pos)
        self._next_id += 1

    def _update_positions(self, bar: SimulatedBar):
        """Check all open positions against current bar."""
        for pos in list(self._positions):
            self._update_position(pos, bar)

    def _update_position(self, pos: OpenPosition, bar: SimulatedBar):
        """Update MAE/MFE and check TP/SL levels."""
        pip_size = 0.01 if bar.symbol.endswith("JPY") else (1.0 if "USDT" in bar.symbol else 0.0001)
        pip_value = 10.0

        # Track MAE/MFE
        if pos.direction == "long":
            unrealised = (bar.close - pos.entry_price) / pip_size * pip_value * pos.remaining_lots
            adverse = (pos.entry_price - bar.low) / pip_size * pip_value * pos.remaining_lots
        else:
            unrealised = (pos.entry_price - bar.close) / pip_size * pip_value * pos.remaining_lots
            adverse = (bar.high - pos.entry_price) / pip_size * pip_value * pos.remaining_lots

        pos.mae = max(pos.mae, -unrealised) if unrealised < pos.mae else pos.mae
        if -adverse < pos.mae:
            pos.mae = -adverse
        pos.mfe = max(pos.mfe, unrealised)

        # TP3 → full close
        if pos.take_profit_3 > 0:
            result = self.simulator.check_sl_tp(
                pos.direction, pos.entry_price,
                pos.stop_loss, pos.take_profit_3,
                bar, pos.remaining_lots, pip_value,
            )
            if result:
                reason, exit_p, pnl = result
                self._close_position(pos, exit_p, pnl, reason)
                return

        # TP2 → partial close 33%
        if pos.take_profit_2 > 0 and not pos.tp2_hit:
            result = self.simulator.check_sl_tp(
                pos.direction, pos.entry_price,
                pos.stop_loss, pos.take_profit_2,
                bar, pos.remaining_lots * 0.33, pip_value,
            )
            if result:
                _, exit_p, pnl = result
                if pos.direction == "long" and bar.high >= pos.take_profit_2:
                    pos.tp2_hit = True
                    pos.total_pnl += pnl
                    pos.remaining_lots = round(pos.remaining_lots * 0.67, 3)
                    self._balance += pnl

        # TP1 → partial close 33% + move BE
        if not pos.tp1_hit:
            result = self.simulator.check_sl_tp(
                pos.direction, pos.entry_price,
                pos.stop_loss, pos.take_profit_1,
                bar, pos.remaining_lots * 0.33, pip_value,
            )
            if result:
                _, exit_p, pnl = result
                tp1_hit = (pos.direction == "long" and bar.high >= pos.take_profit_1) or \
                           (pos.direction == "short" and bar.low <= pos.take_profit_1)
                if tp1_hit:
                    pos.tp1_hit = True
                    pos.total_pnl += pnl
                    pos.remaining_lots = round(pos.remaining_lots * 0.67, 3)
                    self._balance += pnl
                    # Move SL to break-even
                    buffer = abs(pos.entry_price - pos.stop_loss) * 0.05
                    pos.stop_loss = pos.entry_price + buffer \
                        if pos.direction == "long" else pos.entry_price - buffer
                    pos.breakeven_moved = True

        # SL check (on remaining position)
        result = self.simulator.check_sl_tp(
            pos.direction, pos.entry_price,
            pos.stop_loss, pos.take_profit_1 if not pos.tp1_hit else (pos.take_profit_2 or pos.take_profit_3),
            bar, pos.remaining_lots, pip_value,
        )
        if result:
            reason, exit_p, pnl = result
            if reason.startswith("stop_loss"):
                self._close_position(pos, exit_p, pnl, reason)

    def _close_position(
        self,
        pos: OpenPosition,
        exit_price: float,
        pnl: float,
        reason: str,
    ):
        if pos in self._positions:
            self._positions.remove(pos)

        total_pnl = pos.total_pnl + pnl
        self._balance += pnl
        self._peak_balance = max(self._peak_balance, self._balance)

        self._closed.append(TradeStats(
            pnl=total_pnl,
            entry_price=pos.entry_price,
            exit_price=exit_price,
            direction=pos.direction,
            duration_bars=self._next_id - pos.entry_bar,
            exit_reason=reason,
            mae=pos.mae,
            mfe=pos.mfe,
        ))

    def _force_close(self, pos: OpenPosition, exit_price: float, duration: int):
        if pos in self._positions:
            self._positions.remove(pos)
        pip_size = 0.01 if pos.symbol.endswith("JPY") else (1.0 if "USDT" in pos.symbol else 0.0001)
        pip_value = 10.0
        if pos.direction == "long":
            pips = (exit_price - pos.entry_price) / pip_size
        else:
            pips = (pos.entry_price - exit_price) / pip_size
        pnl = pips * pip_value * pos.remaining_lots - self.config.commission_per_lot * pos.remaining_lots
        total_pnl = pos.total_pnl + pnl
        self._balance += pnl

        self._closed.append(TradeStats(
            pnl=total_pnl,
            entry_price=pos.entry_price,
            exit_price=exit_price,
            direction=pos.direction,
            duration_bars=max(duration, 1),
            exit_reason="end_of_data",
            mae=pos.mae,
            mfe=pos.mfe,
        ))

    def _align_slice(
        self,
        df: pd.DataFrame,
        current_time: pd.Timestamp,
        n: int,
    ) -> pd.DataFrame:
        """Return up to n bars strictly before current_time."""
        mask = df["time"] <= current_time
        return df[mask].tail(n).reset_index(drop=True)

    def _build_trade_log(self) -> List[dict]:
        return [
            {
                "pnl": round(t.pnl, 2),
                "entry": t.entry_price,
                "exit": t.exit_price,
                "direction": t.direction,
                "duration_bars": t.duration_bars,
                "exit_reason": t.exit_reason,
                "slippage_pips": t.slippage_pips,
                "spread_pips": t.spread_pips,
                "mae": round(t.mae, 2),
                "mfe": round(t.mfe, 2),
            }
            for t in self._closed
        ]
