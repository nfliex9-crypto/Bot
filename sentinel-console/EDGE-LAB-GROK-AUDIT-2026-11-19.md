# Sentinel Edge Lab v1 — review of user-supplied Grok MT5 export

Date: 2026-11-19. Input: `MT5_TRADER_FULL_2026-11-19.zip` (user-supplied archive).
This is a code/research review, **not** a statement of profitability. Neither the
archive nor the research is promoted to live trading by this change.

## Evidence inspected
- `mt5-scalper/research/FUSION_REPORT.md`: 87 historical picks on Fusion
  M1, **0 met** its OOS gates, despite several positive isolated results.
- `research/mt5-scalper-next2/STRONG_NOTES.md`: 772 proposed SMC/ICT
  variants, **0 passed** the formal selector; multiple take-profits generally
  lowered test expectancy relative to the original main strategy.
- `mt5-scalper/DEPLOY16S_NOTES.md`: rolling daily planner was **negative OOS**
  and weaker than core slots. Not imported into active execution.
- `strategy-factory/data/factory.db` (SQLite in the archive):
  605 stored candidates = 603 rejected + 2 `shadow_live`.
  Both shadow candidates failed its DSR gate (reported DSR=0.0).
  `fwd_trades` contained 0 forward observations at export. Their positive
  historical train/validation/holdout numbers are **not** forward proof.
- `strategy-factory/RULES.md`, `engine.py`, `scalper/rotation.py`,
  `shadow_strats.py`, `quality.py`, `scorecard.py`: useful *methodological*
  elements are chronological separation, explicit luck/correlation guards,
  no-lookahead, broker-cost accounting, conservative shadow promotion and
  rejection records. Avoid reusing account-specific schedule or broker-clock
  assumptions unchanged.
- The archive explicitly excludes large 5-year source bar CSVs, so some
  historical performance claims **cannot be independently reproduced
  from the ZIP alone**.

## What Sentinel has implemented independently

**Research isolation.** The new `brain/edge-lab.js` is an original M15
research evaluator. It never connects to MT5, creates a broker order, or
modifies an approved strategy. The separate research worker imports actual
Fusion M15 closed candles from Sentinel's own Neon storage.

**Two falsifiable candidate ideas, NOT copies:**
1. `sweep_reclaim`: a failed liquidity breakout returning inside a prior
   20-bar range, with causal wick/volatility/regime checks.
2. `compression_breakout`: a small preceding 12-bar range followed by a
   strong close outside it, conditioned on EMA direction and trend efficiency.

Both use only bars available at signal close. Entry is modelled at **next
M15 open**. Unknown same-bar stop/target sequence is always **stop first**;
missing candles invalidate a forward path. No future prices enter signal
generation. Chronological train/validation/holdout is fixed ahead of the
candidate evaluation. Holdout is reported only, never used to decide
candidate status. No automated order or promotion from these reports.

**Truthful transaction friction.** Since imported historical OHLC currently
lacks bid/ask/spread, the lab takes observed *recent* positive Fusion
bid/ask spreads from Neon and uses P90 as a proxy, plus a 2x-spread
sensitivity scenario. The results must remain labelled
`COST_PROXY_RESEARCH_ONLY`. Commissions, slippage, and actual historical
execution costs are **not** fully verified. No strategy can be described as
a broker-verified edge because a proxy-cost backtest looks favorable.

**Forward evidence remains separate.** Sentinel's real broker-confirmed
Fusion Demo fill ledger is unchanged; there has been one verified closed
BTCUSD SHORT `trend_pullback` at −43.66 EUR. The observation is too small
to establish an edge or a regime filter. Nothing in this research changes
the demo-trading authorization, risk size, running scheduler, or Grok bot.

## Requirements before considering candidate activation
1. Obtain properly timestamped historical bid/ask and commission/slippage
   evidence matching the broker contract and M15 bar times.
2. Test data gaps, price source (bid vs midpoint), stop-hit ordering and
   calendar sessions independently.
3. Check family-vs-baseline improvement on untouched holdout and more
   than one market regime; multiple comparisons must be accounted for.
4. Collect real **forward shadow** signals and independently verify closes;
   assess uncertainty and dependence between same-day observations.
5. Any change to real/demo order authorization requires a separate,
   tested engineering change and explicit operational review.

No claimed guaranteed returns or "AI mastered trading" conclusions.
