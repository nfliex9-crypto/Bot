# Sentinel — Orderflows Delta Trading Course: source-traced rulebook

**Source:** Five user-provided MP4s, 114 minutes 14 seconds total. Educational material, not independently validated alpha. **Current scope:** source-traced visual slides/examples; NOT a verified word-for-word audio transcript. Do not claim the whole narration has been audited. No proprietary videos redistributed or embedded in GitHub.

## Video provenance (SHA-256)

| Lesson | Filename | Duration | SHA-256 |
|---|---|---:|---|
| 1 | `Orderflows Delta Trading Course Lesson 1 - Delta Explained(1).mp4` | 36:38 | `9cf3555f4c31d96d6fb2c2bc0fec0d50ecb42fdf710a5433846ea7b559c289d1` |
| 2 | `Orderflows Delta Trading Course Lesson 2 - How To Read Delta(2).mp4` | 15:45 | `b840a3a6da231d1f2abaf308142cfcc8a11f107bf3dcb241e25df093c287f763` |
| 3 | `Orderflows Delta Trading Course Lesson 3 - Delta Numbers(1).mp4` | 32:09 | `bd6dbff480ae32559ce3da2e73c2729be59d9e73a03a90d294713932dbea9ca1` |
| 4A | `Orderflows Delta Trading Course Lesson 4 - Delta Trade Setups.mp4` | 14:12 | `2778d1c6fa6aa2cd81a1b7f9f462286ece8c16c9f38fe0ed1a9fd1d145410a21` |
| 4B | `Orderflows Delta Trading Course Lesson 4 - Delta Trade Setups(1).mp4` | 15:29 | `22369df128c4ac4c8c358c02774ae6c6ca846f23e8e3f5adcf5e188c026415e5` |

## Lesson 1 — what Delta means (00:00–36:38)

- Market transactions have both buyer and seller; aggressor side describes **which party crosses the spread**, not a count of buyers vs sellers (around 01:00–07:30).
- Passive buyers/sellers rest limit orders; aggressive buyers lift the offer; aggressive sellers hit the bid (around 04:00–07:30).
- `Delta = aggressive buy executed volume - aggressive sell executed volume`. Positive/negative describes **executed initiative**, not future price direction (around 07:30–16:00).
- Passive liquidity, absorption, and possibly hidden/iceberg liquidity can explain price moving opposite to Delta; **Delta alone does not prove an iceberg** (around 17:00–21:00).
- Delta changes during a candle; a final value hides its path. Observe transitions and context around ranges, consolidation, and accumulation/distribution examples (around 22:00–35:00).

## Lesson 2 — ways to read Delta (00:00–15:45)

- Compare one candle and a sequence of candles; the chart display affects what is visible.
- Delta Chart / Delta Candle (around 02:00–08:00): final delta over time; a separate candle representation may reveal intra-candle transitions depending on data.
- Delta Footprint (around 09:00–11:00): delta **by traded price level**. The executable module computes `buyVolume`, `sellVolume`, and `delta` per price level.
- Diagonal Delta Footprint (around 12:00–14:00): compares activity on adjacent prices diagonally. **Exact formula/normalization has not been audio-verified**; do not pretend a guessed diagonal calculation is a course rule.
- No single display is mandated for all trading styles.

## Lesson 3 — Delta Numbers (00:00–32:09)

- Distinguish final Delta, Max Delta, Min Delta, Cumulative Delta, and Cumulative Delta/Volume (around 01:00).
- Time bars and range bars aggregate trades differently (around 02:00). The current engine implements **time bars only**, not range bars.
- Final Delta is fixed at bar close, while the running value varies during the bar (around 03:00–04:00).
- Session/open/close volume affects raw magnitudes; do not compare across assets/sessions using an arbitrary universal threshold (around 06:00–08:00).
- `Max Delta` is the highest **running intra-bar delta**, `Min Delta` the lowest **running intra-bar delta**, including the starting zero (around 10:00–22:00). These are not extrema of the last N final bar deltas.
- Cumulative Delta is a running signed sum across the venue session; it can lag or conceal local changes (around 23:00–25:00).
- `Cumulative Delta / Volume` is running session Delta divided by running session executed volume; can flatten as the denominator grows (around 26:00–31:00).
- **Important lesson 3 ~26:37 detail:** instructor looks for CVD/Volume **near zero**, suggesting near-balanced buyers/sellers and consolidation/absorption, **then a strong directional Delta** as a possible trade cue. This is represented by a separate research detector with explicit `nearZeroRatioTolerance` and `strongDeltaThreshold`; neither cutoff is provided by the source.

## Lesson 4 — Trade Setups (4A 00:00–14:12, 4B 00:00–15:29)

The course names **seven**: Delta Surge, Delta Divergence, Delta Flips, Delta Transition, Delta Tails, Delta Bulges, Delta Reversal. The **two uploaded files visually document detailed conditions only for the first three**. The last four must remain `SOURCE_RULE_UNSPECIFIED` until the missing instructional details are verifiable; their names alone do not define an algorithm.

### Delta Surge — 4A ~07:50–14:12, 4B ~00:00

- **General source concept:** Delta strengthens in a positive or negative direction over **several** bars, especially near consolidation/turning points. The instructor does **not** prescribe four bars as a universal requirement.
- **Four-bar example variant — long**: `d1<0`, `d2>0`, `d3>d2`, `d4>d3`.
- **Four-bar example variant — short**: `d1>0`, `d2<0`, `d3<d2`, `d4<d3`.
- Course context: around turning points, consolidation and especially emergence from sideways activity (4B ~00:15). This is context, **not an independently quantified mandatory filter**.
- No verified stop, target, risk/reward, win rate, or fixed threshold from the source.

### Delta Divergence — 4B ~01:30–05:00

- **Short hypothesis**: new/equal high with negative Delta on the extreme bar.
- **Long hypothesis**: new/equal low with positive Delta on the extreme bar.
- The examples refer to swing extremes, not only day highs/lows. `swingLookback` and `equalTolerance` are **unprovided by the source** and therefore mandatory explicit research parameters; no default is disguised as the instructor's rule.
- Entry confirmation, SL, TP, and exit are not specified in the slides.

### Delta Flips — 4B ~05:15–15:29

- **Long**: first bar `MaxDelta=0` and final Delta near its Min; next bar `MinDelta=0` and final Delta near its Max.
- **Short**: first bar `MinDelta=0` and final Delta near its Max; next bar `MaxDelta=0` and final Delta near its Min.
- An example permits **one intervening bar** (~12:30). This is a separately enabled variation, not the default.
- “Near” is **not numerically defined in the slides**. `nearExtremeTolerance` is explicitly required by the engine and is a research parameter, not a source fact.

### Other four names — blocked, not invented

`delta_transition`, `delta_tails`, `delta_bulges`, `delta_reversal`: mentioned in the list (~03:17 of 4A), but **no detailed conditions are visible in these two uploaded videos**. They are registered as knowledge gaps, not silently omitted or made up.

## Data and implementation contract

`worker/orderflow/delta-engine.js` consumes an ordered **executed-trade tape**, each record with `time` (UTC milliseconds), `tradeId` (unique), `price`, `size`, `aggressorSide` (`BUY`/`SELL`), and `sessionId` (assigned by venue calendar). Caller must supply `venue`, `symbol`, `tickSize`, `barMs`, `sourceQuality="VERIFIED_AGGRESSOR_TRADES"`, and `now`.

From the tape it calculates price OHLC, executed volume, aggressive buy/sell volume, final Delta, **running intra-bar Max/Min Delta**, per-price footprint levels, session CVD and CVD/volume. All signals are `RESEARCH_HYPOTHESIS`, `executionEnabled:false`, `edgeVerified:false`. Unverified bars, unknown aggressor sides, duplicate trade IDs, nonmonotonic times, partial candles, inconsistent volumes, session changes inside patterns, and missing research thresholds block signal evaluation.

**Do not substitute MT5 tick volume or CFD OHLC for exchange executed-trade Delta.** XAUUSD/NAS100/EURUSD OTC CFDs have no single universal exchange tape. GC/NQ futures can be an external proxy, not identical to FusionMarkets CFDs; BTCUSD exchange tape is venue-specific. Validate symbol mapping, source entitlement, latency, data gaps and contract/session calendar.

**No strategy is trade-approved.** Next stages: ingest authenticated real trade tape; replay historical events and compare reconstructed footprint to the source chart; verify each setup visually with timecoded examples; run bid/ask cost-aware walk-forward/OOS; then controlled Fusion Demo only after explicit authorization and broker fill reconciliation. Do not change the existing cloud demo trading mode based solely on these source slides.

## Completeness register — no false claims

| Component | Status |
|---|---|
| Five MP4s present; durations and SHA-256 verified | Done |
| Source slides and example chart screenshots sampled across the lessons | Done |
| Educational concepts from the visually reviewed material recorded | Done |
| Three named trade setups encoded with provenance | Done |
| Four named but unspecified setups preserved as blocked gaps | Done |
| Word-for-word 114-minute audio transcription / all spoken nuances | **Not done; local ASR model unavailable** |
| Full lesson-specific tick tape and screenshot-by-screenshot reconciliation | **Not done** |
| Live authenticated aggressor tape for Sentinel | **Not connected** |
| OOS/backtest evidence and verified new demo fills | **Not established** |

To reach *literally no spoken detail omitted*, run a timecoded transcription of **all five audio tracks**, review it against the screenshots, and update this register. Until then this is a rigorously bounded **visual-source implementation**, not a complete course transcription.