import logging
from typing import Any, Optional

import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import train_test_split

from cache import make_cache_key, load_model, save_model
from config import (
    FEATURE_CONFIG,
    INTERVAL,
    MODEL_CONFIGS,
    RANDOM_SEED,
    START_DATE,
    END_DATE,
)
from dataset.builder import build_dataset

logger = logging.getLogger(__name__)

MODEL_REGISTRY = {
    "ridge": Ridge,
    "random_forest": RandomForestRegressor,
}

try:
    from xgboost import XGBRegressor

    MODEL_REGISTRY["xgboost"] = XGBRegressor
except ImportError:
    logger.warning("XGBoost not installed — 'xgboost' model unavailable")


def _model_factory(model_type: str) -> Any:
    cls = MODEL_REGISTRY.get(model_type)
    if cls is None:
        raise ValueError(f"Unknown model type {model_type!r}. Available: {list(MODEL_REGISTRY)}")
    params = MODEL_CONFIGS.get(model_type, {})
    return cls(**params)


def train_model(
    ticker: str,
    model_type: str,
    horizon: int,
    interval: str = INTERVAL,
    start: str = START_DATE,
    end: str = END_DATE,
    config: Optional[dict] = None,
):
    """Train (or load cached) model for a given ticker / horizon / model_type.

    Returns (model, was_cached_bool).
    """
    cfg = config or FEATURE_CONFIG
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

    hyperparams = MODEL_CONFIGS.get(model_type, {})
    key = make_cache_key(
        operation="train_model",
        dataset_hash=dataset_key,
        model_type=model_type,
        hyperparams=hyperparams,
        dataset_version="1.0",
    )

    cached = load_model(key)
    if cached is not None:
        logger.info("[CACHED] Model %s %s h=%d", ticker, model_type, horizon)
        return cached, True

    logger.info("[TRAIN] Model %s %s h=%d", ticker, model_type, horizon)

    feature_cols = [c for c in dataset.columns if c != "target"]
    X = dataset[feature_cols].values
    y = dataset["target"].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_SEED, shuffle=False
    )

    model = _model_factory(model_type)
    model.fit(X_train, y_train)

    save_model(model, key)
    return model, False
