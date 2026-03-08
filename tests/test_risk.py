from app.config import Settings
from app.risk.manager import RiskManager


def test_position_size_respects_risk():
    settings = Settings(account_balance=3000, risk_per_trade=0.0075)
    manager = RiskManager(settings)
    qty = manager.compute_position_size(entry=1.1000, stop=1.0990)
    assert round(qty, 2) == 22500.00

