from app.db.models import BotState
from app.db.session import Base, SessionLocal, engine


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        state = db.query(BotState).first()
        if not state:
            db.add(BotState())
            db.commit()
    finally:
        db.close()

