"""
Train or retrain the AI classifier on accumulated trade data.
"""

from __future__ import annotations

import sys
sys.path.insert(0, ".")

import numpy as np
from loguru import logger

from app.ai.classifier import TradeClassifier
from app.ai.feature_engineer import generate_synthetic_training_data


def main():
    logger.info("Training AI classifier...")

    classifier = TradeClassifier()
    classifier.train_initial()

    importance = classifier.get_feature_importance()
    logger.info("Feature importance:")
    for name, score in sorted(importance.items(), key=lambda x: x[1], reverse=True):
        logger.info(f"  {name}: {score:.4f}")

    X_test, y_test = generate_synthetic_training_data(n_samples=500, seed=99)
    correct = 0
    total = len(X_test)
    for i in range(total):
        pred = classifier._model.predict(X_test[i : i + 1])[0]
        if pred == y_test[i]:
            correct += 1

    logger.info(f"Test accuracy: {correct/total*100:.1f}% ({correct}/{total})")


if __name__ == "__main__":
    main()
