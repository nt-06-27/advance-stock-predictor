import logging
from typing import Optional

import numpy as np
from sklearn.model_selection import train_test_split

from cache import make_cache_key, load_json, save_json
from config import FEATURE_CONFIG, INTERVAL, RANDOM_SEED, START_DATE, END_DATE
from dataset.builder import build_dataset
from models.trainer import train_model

logger = logging.getLogger(__name__)


def evaluate(
    ticker: str,
    model_type: str,
    horizon: int,
    interval: str = INTERVAL,
    start: str = START_DATE,
    end: str = END_DATE,
    config: Optional[dict] = None,
) -> dict:
    """Compute cached evaluation metrics for a trained model.

    Metrics:
        rmse, mae, directional_accuracy, sharpe, hit_rate
    """
    cfg = config or FEATURE_CONFIG

    model, _ = train_model(ticker, model_type, horizon, interval, start, end, cfg)
    dataset = build_dataset(ticker, horizon, interval, start, end, cfg)

    dataset_key = make_cache_key(
        operation="build_dataset",
        ticker=ticker,
        horizon=horizon,
        interval=interval,
        start=start,
        end=end,
        config=cfg,
    )

    key = make_cache_key(
        operation="evaluate",
        model_type=model_type,
        dataset_hash=dataset_key,
        dataset_version="1.0",
    )

    cached = load_json("evals", key)
    if cached is not None:
        logger.info("[CACHED] Eval %s %s h=%d", ticker, model_type, horizon)
        return cached

    logger.info("[EVAL] %s %s h=%d", ticker, model_type, horizon)

    feature_cols = [c for c in dataset.columns if c != "target"]
    X = dataset[feature_cols].values
    y = dataset["target"].values

    _, X_test, _, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_SEED, shuffle=False
    )

    y_pred = model.predict(X_test)

    rmse = float(np.sqrt(np.mean((y_test - y_pred) ** 2)))
    mae = float(np.mean(np.abs(y_test - y_pred)))
    directional_accuracy = float(np.mean((np.sign(y_test) == np.sign(y_pred))))
    sharpe = float(
        np.mean(y_pred) / np.std(y_pred) * np.sqrt(252) if np.std(y_pred) > 0 else 0.0
    )
    hit_rate = float(np.mean(np.abs(y_test - y_pred) / np.maximum(np.abs(y_test), 1e-8) < 0.05))

    result = {
        "ticker": ticker,
        "model": model_type,
        "horizon": f"{horizon}d",
        "rmse": round(rmse, 6),
        "mae": round(mae, 6),
        "directional_accuracy": round(directional_accuracy, 4),
        "sharpe": round(sharpe, 4),
        "hit_rate": round(hit_rate, 4),
        "cached": False,
    }

    save_json(result, "evals", key)
    return result
