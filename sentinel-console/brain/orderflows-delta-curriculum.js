"use strict";
/** User-provided 5-part course: visual-source index, not a full audio transcript. */
const SOURCE="Orderflows Delta Trading Course";
const LESSONS=Object.freeze([
 {id:"delta_explained",durationSeconds:2198,topics:["passive_vs_aggressive_buyers_and_sellers","lift_offer_vs_hit_bid","delta_executed_buy_minus_sell","absorption_and_possible_icebergs","delta_price_disagreement","intrabar_delta_changes","consolidation_context"]},
 {id:"how_to_read_delta",durationSeconds:945,topics:["single_bar_vs_sequence","delta_chart","delta_candle","price_level_footprint","diagonal_footprint","display_choice"]},
 {id:"delta_numbers",durationSeconds:1929,topics:["final_delta","intrabar_max_delta","intrabar_min_delta","session_cumulative_delta","cumulative_delta_over_volume","time_vs_range_bars","session_volume_effects","cumulative_lag"]},
 {id:"delta_trade_setups_part_1",durationSeconds:852.133333,topics:["seven_setups_named","trading_context","delta_surge_examples"]},
 {id:"delta_trade_setups_part_2",durationSeconds:929.466667,topics:["sideways_surge_context","delta_divergence","delta_flips","one_intervening_bar_example"]}
]);
const SETUPS=Object.freeze([
 {id:"delta_surge",sourceRule:"four consecutive signed-delta bars; -,+,higher+,higher+ for long; inverse for short",sourceCoverage:"VISUAL_RULE_CONFIRMED",requires:["verified_trade_tape","four_closed_bars"],executionEnabled:false},
 {id:"delta_divergence",sourceRule:"new or equal swing high with negative delta (short), low with positive delta (long)",sourceCoverage:"VISUAL_RULE_CONFIRMED",requires:["verified_trade_tape","swing_lookback_research_parameter","equal_tolerance_research_parameter"],executionEnabled:false},
 {id:"delta_flips",sourceRule:"Max=0 and close near Min then Min=0 and close near Max (long); inverse short; optional one intervening bar",sourceCoverage:"VISUAL_RULE_CONFIRMED",requires:["verified_trade_tape","intrabar_delta_extrema","near_tolerance_research_parameter"],executionEnabled:false},
 ...["delta_transition","delta_tails","delta_bulges","delta_reversal"].map(id=>({id,sourceRule:null,sourceCoverage:"NAME_ONLY_UNSPECIFIED",requires:["SOURCE_RULE_DETAILS"],executionEnabled:false}))
]);
function status(){return {source:SOURCE,videoFiles:LESSONS.length,lessons:LESSONS,
  setupCount:SETUPS.length,encodedResearchSetups:3,unresolvedSetups:4,
  audioFullyTranscribed:false,sourceProvenance:"VISUAL_SAMPLES_WITH_TIMECODES",
  tradeExecutionEnabled:false,setupRegistry:SETUPS};}
module.exports={SOURCE,LESSONS,SETUPS,status};