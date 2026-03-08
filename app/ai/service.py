from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.random_forest import RandomForestConfidenceModel
from app.config import Settings
from app.models import TradeFeature
from app.schemas import TrainResponse


class AIService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.model = RandomForestConfidenceModel(settings.model_path)

    def score(self, feature_payload: dict, rule_score: float) -> float:
        ml_score = self.model.predict_confidence(feature_payload)
        if ml_score is None:
            return rule_score
        return max(0.0, min(1.0, 0.6 * ml_score + 0.4 * rule_score))

    def train_from_db(self, session: Session) -> TrainResponse:
        rows = session.execute(select(TradeFeature.features, TradeFeature.label)).all()
        samples, acc = self.model.train(rows)
        if samples < self.settings.min_training_samples:
            return TrainResponse(
                trained=self.model.is_trained(),
                samples=samples,
                accuracy=acc,
                message=(
                    f"Model trained with {samples} samples; recommended >= {self.settings.min_training_samples} "
                    "for production confidence."
                ),
            )
        return TrainResponse(
            trained=self.model.is_trained(),
            samples=samples,
            accuracy=acc,
            message="Model training complete.",
        )

