from app.services.ai_model import TradeConfidenceModel


def test_confidence_score_is_probability() -> None:
    model = TradeConfidenceModel()
    confidence = model.score([0.8, 0.7, 0.5, 1.2, 0.3])
    assert 0.0 <= confidence <= 1.0
