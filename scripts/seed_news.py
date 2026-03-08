import argparse
import asyncio
from datetime import datetime

import pandas as pd

from app.core.database import SessionLocal, init_db
from app.models.entities import NewsEvent


async def seed(csv_path: str) -> None:
    await init_db()
    frame = pd.read_csv(csv_path)
    async with SessionLocal() as session:
        for _, row in frame.iterrows():
            event = NewsEvent(
                title=row["title"],
                currency=row["currency"],
                impact=row["impact"].lower(),
                starts_at=datetime.fromisoformat(row["starts_at"]),
            )
            session.add(event)
        await session.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed high-impact news events from CSV.")
    parser.add_argument("--csv", required=True, help="CSV with title,currency,impact,starts_at")
    args = parser.parse_args()
    asyncio.run(seed(args.csv))


if __name__ == "__main__":
    main()
