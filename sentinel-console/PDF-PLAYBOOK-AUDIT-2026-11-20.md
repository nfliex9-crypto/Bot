# Sentinel PDF Playbook — evidence-first research (20 Nov 2026)

## Original inputs (8 owner-supplied PDFs; 350 pages)
Files remain in the conversation, **not** copied into the public GitHub repository.
The `brain/pdf-playbook-lab.js` module identifies each exact file using SHA-256,
page count and original title. Hashes refer to the bytes provided by the owner.
These are educational hypotheses, **not** verified institutional execution facts
or guaranteed profitable algorithms. The library stores our original paraphrases
and test rules, not large copyrighted PDF passages.

| Source | Pages used | Research implication |
|---|---|---|
| Entry Types Continuation Part 1 | 3–4, 7–8 | Compare early single-BOS entries with extra structural confirmation |
| Entry Types Continuations & Liquidity Part 2 | 2–4, 6 | A wick-heavy/weak break is distinct from a displacement; reject stale mitigated zones |
| Types of Liquidity | 1, 3, 5 | Prior highs/lows and equal highs/lows are candidate sweep levels; actual resting stops cannot be seen from OHLC |
| Price Action Imbalance | 2–3, 11 | Three-candle FVG is a geometric price gap, detected only after 3rd candle closes; retest and fill-depth claims require testing |
| Supply and Demand | 2–5, 11 | Consolidation followed by expansion and BOS is a candidate price zone, not proof of hidden orders |
| Liquidity and Manipulation | 2–4 | Detect possible liquidity raids with observable candle data, without asserting intentional bank manipulation |
| FOREX ICT & MMM Notes — Reginald Mmari | 8, 28, 34, 44, 55, 72–73 | HTF/LTF alignment, swing levels, FVG, timing/holiday caveats; use audited exchange sessions/DST before session-specific studies |
| Market Structure and Powerful Setups — Wade FX | 9, 80–82, 104–105 | Turtle Soup short/long as *hypotheses*, plus HTF bias and closed-bar confirmation; don't transport fixed FX pip stops to BTC/gold/NAS100 |

## Two original hypotheses now testable

1. **Sweep + closed displacement confirmation** (`sweep_displacement_confirm`):
   after a closed M15 candle sweeps the 20-bar high/low and closes back inside,
   a later closed directional displacement must beat the sweep extreme while
   matching a *fully closed* H1 trend. No limit entry on mere touch or sweep.
2. **Displacement FVG retest** (`displacement_fvg_retest`):
   find a three-candle non-overlapping gap where the middle candle displaced
   in direction; the first retest within 10 closed bars must reject its midpoint,
   in the direction of a fully closed H1 trend. Retests are a **price geometry**
   hypothesis, not authenticated aggressive order flow or a genuine liquidity void.

Every H1 bar is assembled from four consecutive **actual** M15 broker bars
aligned to the hour. A missing M15 candle invalidates that H1 rather than
forward filling it. Higher-timeframe indicators only use H1 closes that existed
when the signal M15 candle closed.

## Comparison, limitations and promotion

Train 60% / validation 20% / sealed holdout 20% in time order.
Position is modelled on **next M15 open**, intrabar TP+SL ambiguity chooses
stop-first, missing bars fail the trade. Families are evaluated independently
to avoid overlapping same-family trades. Costs use a P90 of recently observed
Fusion MT5 bid/ask spreads plus a 2x-spread validation stress scenario; this is
**not historic spread reconstruction**. The evaluator lacks independently
verified historical commissions, slippage, spread paths or fill sequence.
Positive results are labelled *manual shadow review only*, never live/demo
strategy authorization. No M1 or 30-second fills may be imputed from M15.

The trainer does **not** read an LLM's chain of thought or modify model weights.
It is an auditable rule-extraction → deterministic backtest → OOS report →
forward shadow journaling process. Research outcomes can inform future
candidate specifications **only after** safety, data quality, multiple-test
controls and adequate forward samples. No automatic risk increase.

## Source-critical caveats

- Assertions that every market move is institutional stop hunting or that an
  untested FVG must be filled are educational narratives, not verified claims.
- A PDF example reporting unusually high RR is not reproducible audited PnL.
- The ICT/MMM notes give generic hours in GMT and discuss session patterns.
  Applying these blindly to Brussels local time or around US DST is unsafe.
- Bookmap-style volume profile, footprint, CVD, passive absorption and L2
  **cannot** be reconstructed from an MT5 OHLC feed. For these, obtain a
  compatible exchange futures feed (e.g. CME NQ/GC plus actual volume-at-price,
  aggressor-tagged ticks and ideally MBO/DOM with rights to store it).
- No new candidate will be sent to Fusion Demo or a real-money account from
  this experimental source-analysis pipeline.

## Next experiment
Compare against the existing `sweep_reclaim` and
`compression_breakout` baselines on the **same time span and cost proxy**;
store separate per-symbol run IDs, shadow reports and threshold provenance.
Selection requires out-of-sample positive expectancy **after fees** in more
than one regime, stable across cost stress and many genuine broker-forward
fills. Reject/no-signal is an acceptable result.
