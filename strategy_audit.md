# TradingView Strategy Audit

## Source audited

The original script supplied in the prompt combines:

- alternate-timeframe smoothed open/close crossover signals,
- supply/demand and support/resistance drawing logic,
- multiple indicator experiments,
- a custom floating-state TP/SL engine.

## Highest-priority findings

### 1) Lookahead bias and repaint risk in higher-timeframe signals

The original script labels multiple wrappers as non-repainting, but several of them are repaint-prone:

- `securityNoRep(... lookahead_on)`
- `securityNoRep1(... lookahead_on)`
- `reso(... lookahead_on)`

Because the entry triggers are driven by `closeSeriesAlt` and `openSeriesAlt`, the strategy can use future-confirmed higher-timeframe values on historical bars. That makes backtests materially over-optimistic.

## 2) Large computational overhead from unused or incomplete logic

A significant share of the original script does not contribute to entries or exits:

- Keltner channel stacks
- linear-regression helpers
- divergence helpers
- daily OHLC pulls
- support/resistance arrays and redraw loops
- order-block helper stubs

This is expensive on low timeframes and increases the chance of object-limit or performance issues without improving execution.

## 3) Heavy line/label/box churn

Several sections create and delete visual objects on nearly every bar:

- support/resistance lines and labels
- trade level lines and labels
- supply/demand box maintenance

That is unnecessarily costly and can degrade performance on intraday data.

## 4) Fragile trade-state machine

The original strategy uses a float `condition` state (`1.0`, `1.1`, `1.2`, etc.) to represent entry and TP progress. This is difficult to maintain and easy to break during future edits. It also obscures the real trade state.

## 5) Incorrect / inconsistent order messaging

The short entry order uses the long-entry alert message variable:

- short entry sends `i_leMsg` instead of `i_seMsg`

## 6) Manual close triggers never fire

The original code hardcodes:

- `lxTrigger = false`
- `sxTrigger = false`

So the associated `strategy.close()` branches are effectively dead code.

## 7) Swing processing misses simultaneous pivot events

The pivot block uses:

- `if not na(swing_high) ... else if not na(swing_low) ...`

If both are confirmed on the same bar, only one branch is processed.

## 8) Misleading naming around repaint safety

Several helpers are named as if they guarantee non-repainting behavior, but their implementation does not consistently enforce confirmed-bar or confirmed-HTF logic. That makes the script harder to trust during audit and maintenance.

---

## Refactor goals applied

The refactored strategy keeps the original concept intact:

- smoothed open vs smoothed close crossover,
- optional alternate-timeframe confirmation,
- multi-target exits,
- visual market-structure context.

Engineering changes made:

- replaced repaint-prone HTF requests with confirmed HTF requests using the prior completed HTF bar,
- removed unused indicator blocks and dead helpers,
- replaced float-state trade logic with explicit stored trade levels,
- added optional trend, volatility, session, structure, and sweep filters,
- added ATR/swing dynamic stops,
- added normalized multi-target partial exits,
- added break-even logic after TP1,
- added position sizing modes,
- added max trades per session/day,
- added drawdown lockout,
- added a lightweight stats table.

## Backtest integrity notes

The refactored version is intentionally conservative:

- higher-timeframe signals use the previous confirmed HTF bar,
- entries can be validated only on closed bars,
- pivots are based on confirmed `ta.pivothigh/ta.pivotlow`,
- break-even activation occurs after TP1 has been observed by price, rather than anticipating fills.

## Remaining limitations

Even with the refactor, a few TradingView simulator realities still apply:

- intrabar sequencing on OHLC bars can still affect whether TP or SL is assumed to hit first,
- partial exits are still processed by TradingView's broker emulator rules,
- Heikin Ashi signals are synthetic by nature and should not be treated as executable market prices.
