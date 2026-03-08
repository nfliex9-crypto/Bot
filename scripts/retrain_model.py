"""
Standalone script to retrain the ML model from stored trade data.
Run periodically (e.g., weekly) to improve predictions.
"""

import sys
sys.path.insert(0, ".")

from ai.classifier import TradeClassifier
from config.settings import get_config
from database.repository import TradingRepository

config = get_config()
db = TradingRepository(config.database)
db.connect()

features_df, labels = db.get_ml_training_data()

if features_df.empty:
    print("No training data available yet. The model will learn from live trades.")
    sys.exit(0)

classifier = TradeClassifier()
result = classifier.train(features_df, labels)

print(f"\nTraining result: {result}")
