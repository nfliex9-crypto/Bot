import argparse

import pandas as pd

from app.ai.model import TradeConfidenceModel
from app.config import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Train RandomForest confidence model.")
    parser.add_argument("--csv", required=True, help="Path to training dataset csv.")
    parser.add_argument("--target", default="won", help="Target column name.")
    args = parser.parse_args()

    settings = get_settings()
    model = TradeConfidenceModel(settings.model_path, settings.min_confidence_to_trade)
    data = pd.read_csv(args.csv)
    model.train(data, target_col=args.target)
    print(f"Model trained and saved to {settings.model_path}")


if __name__ == "__main__":
    main()
