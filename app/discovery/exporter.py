"""
Export top strategies with full logic, parameters, and performance reports.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import List

from app.discovery.ranking import RankedStrategy
from app.discovery.strategy_config import Condition


def _condition_to_dict(c: Condition) -> dict:
    return {"left": c.left, "op": c.op, "right": c.right}


def _report_section(title: str, report) -> dict:
    return {
        "period": title,
        "total_trades": report.total_trades,
        "win_rate": round(report.win_rate, 4),
        "profit_factor": round(report.profit_factor, 4),
        "sharpe_ratio": round(report.sharpe_ratio, 4),
        "max_drawdown": round(report.max_drawdown, 4),
        "avg_r_multiple": round(report.avg_r_multiple, 4),
        "trade_frequency": round(report.trade_frequency, 6),
        "total_pnl": round(report.total_pnl, 2),
        "expectancy": round(report.expectancy, 4),
        "consistency": round(report.consistency, 4),
    }


def export_top_strategies(
    ranked: List[RankedStrategy],
    top_n: int = 5,
    output_dir: str = "output/discovery",
) -> str:
    """
    Export the top *top_n* strategies to JSON files.

    Returns the output directory path.
    """
    os.makedirs(output_dir, exist_ok=True)

    top = ranked[:top_n]
    summary: list = []

    for rank_idx, rs in enumerate(top, 1):
        strat = rs.strategy
        entry = {
            "rank": rank_idx,
            "name": strat.name,
            "family": strat.family,
            "composite_score": rs.composite_score,
            "description": strat.description,
            "complexity": strat.complexity,
            "scores": {
                "sharpe": rs.sharpe_score,
                "profit_factor": rs.pf_score,
                "drawdown": rs.dd_score,
                "consistency": rs.consistency_score,
                "simplicity_bonus": rs.simplicity_bonus,
            },
            "parameters": strat.params,
            "risk_management": {
                "sl_atr_multiplier": strat.sl_atr_mult,
                "tp_reward_risk": strat.tp_rr,
                "risk_per_trade_pct": strat.risk_pct,
            },
            "logic": {
                "long_entry": [_condition_to_dict(c) for c in strat.long_entry],
                "short_entry": [_condition_to_dict(c) for c in strat.short_entry],
                "long_exit": [_condition_to_dict(c) for c in strat.long_exit],
                "short_exit": [_condition_to_dict(c) for c in strat.short_exit],
            },
            "performance": {
                "training": _report_section("training", rs.train_report),
                "validation": _report_section("validation", rs.val_report),
                "out_of_sample": _report_section("out_of_sample", rs.oos_report),
            },
        }
        summary.append(entry)

        strat_path = os.path.join(output_dir, f"strategy_{rank_idx}_{strat.name}.json")
        with open(strat_path, "w") as f:
            json.dump(entry, f, indent=2, default=str)

    summary_path = os.path.join(output_dir, "discovery_summary.json")
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "strategies_survived": len(ranked),
        "top_strategies": summary,
    }
    with open(summary_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    return output_dir
