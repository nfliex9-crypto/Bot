import numpy as np

from app.ai.model import TradeConfidenceModel
from app.config import get_settings
from app.db.models import Trade
from app.db.session import SessionLocal


def build_dataset():
    db = SessionLocal()
    try:
        closed = db.query(Trade).filter(Trade.status == "closed").all()
        X, y = [], []
        for t in closed:
            feats = (t.metadata_json or {}).get("features", {})
            realized = float((t.metadata_json or {}).get("realized_pnl", 0.0))
            if not feats:
                continue
            x = [float(feats.get(k, 0.0)) for k in TradeConfidenceModel.FEATURE_ORDER]
            X.append(x)
            y.append(1 if realized > 0 else 0)
    finally:
        db.close()

    if len(X) < 100:
        # Bootstrap synthetic training data to initialize the model.
        rng = np.random.default_rng(42)
        synth_X = rng.normal(loc=0.0, scale=1.0, size=(1200, len(TradeConfidenceModel.FEATURE_ORDER)))
        synth_y = ((synth_X[:, 0] + synth_X[:, 4] + synth_X[:, 5]) > 0).astype(int)
        return synth_X, synth_y
    return np.array(X, dtype=float), np.array(y, dtype=int)


def main():
    settings = get_settings()
    model = TradeConfidenceModel(settings)
    X, y = build_dataset()
    model.train_and_save(X, y)
    print(f"Model trained and saved to {settings.model_path}. Samples={len(y)}")


if __name__ == "__main__":
    main()

