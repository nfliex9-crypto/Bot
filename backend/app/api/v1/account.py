from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional

from app.database import get_db
from app.models.account import Account, EquitySnapshot
from app.schemas.account import AccountRead, EquitySnapshotRead

router = APIRouter(prefix="/account", tags=["Account"])


@router.get("/", response_model=List[AccountRead])
async def get_accounts(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Account).where(Account.is_active == True))
    return result.scalars().all()


@router.get("/equity-curve", response_model=List[EquitySnapshotRead])
async def get_equity_curve(
    account_id: Optional[int] = None,
    limit: int = Query(500, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(EquitySnapshot).order_by(desc(EquitySnapshot.timestamp)).limit(limit)
    if account_id:
        stmt = stmt.where(EquitySnapshot.account_id == account_id)

    result = await db.execute(stmt)
    snapshots = result.scalars().all()
    return list(reversed(snapshots))  # Return oldest first for chart


@router.get("/summary")
async def get_account_summary(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import func
    from app.models.trade import Trade, TradeStatus

    accounts_result = await db.execute(
        select(Account).where(Account.is_active == True)
    )
    accounts = accounts_result.scalars().all()

    open_trades_result = await db.execute(
        select(func.count(Trade.id)).where(Trade.status == TradeStatus.OPEN)
    )
    open_count = open_trades_result.scalar() or 0

    total_balance = sum(a.current_balance for a in accounts)
    total_equity = sum((a.equity or a.current_balance) for a in accounts)
    total_pnl = sum(a.total_pnl or 0 for a in accounts)
    max_dd = max((a.max_drawdown_pct or 0) for a in accounts) if accounts else 0

    return {
        "total_balance": round(total_balance, 2),
        "total_equity": round(total_equity, 2),
        "total_pnl": round(total_pnl, 2),
        "open_trades": open_count,
        "max_drawdown_pct": round(max_dd, 2),
        "accounts": [
            {
                "id": a.id,
                "broker": a.broker.value,
                "balance": a.current_balance,
                "equity": a.equity or a.current_balance,
                "drawdown_pct": a.current_drawdown_pct or 0,
                "win_rate": round(
                    a.winning_trades / a.total_trades * 100 if a.total_trades > 0 else 0, 1
                ),
                "session_trades_today": a.session_trades_today,
            }
            for a in accounts
        ],
    }
