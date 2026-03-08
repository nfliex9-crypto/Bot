from __future__ import annotations

from fastapi import APIRouter, Depends

from database.repository import TradeRepository

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def get_repo() -> TradeRepository:
    return TradeRepository()


@router.get("/account-history")
async def account_history(days: int = 30, repo: TradeRepository = Depends(get_repo)):
    return await repo.get_account_history(days)


@router.get("/recent-signals")
async def recent_signals(limit: int = 50, repo: TradeRepository = Depends(get_repo)):
    return await repo.get_recent_signals(limit)


@router.get("/performance")
async def performance(repo: TradeRepository = Depends(get_repo)):
    closed = await repo.get_closed_trades(limit=500)
    if not closed:
        return {"total": 0, "winners": 0, "losers": 0, "win_rate": 0, "avg_pnl": 0, "total_pnl": 0}

    winners = [t for t in closed if t["pnl"] > 0]
    losers = [t for t in closed if t["pnl"] <= 0]
    total_pnl = sum(t["pnl"] for t in closed)
    avg_pnl = total_pnl / len(closed) if closed else 0

    return {
        "total": len(closed),
        "winners": len(winners),
        "losers": len(losers),
        "win_rate": round(len(winners) / len(closed) * 100, 1) if closed else 0,
        "avg_pnl": round(avg_pnl, 2),
        "total_pnl": round(total_pnl, 2),
        "avg_winner": round(sum(t["pnl"] for t in winners) / len(winners), 2) if winners else 0,
        "avg_loser": round(sum(t["pnl"] for t in losers) / len(losers), 2) if losers else 0,
    }
