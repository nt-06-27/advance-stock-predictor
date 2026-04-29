import logging
from typing import Optional

import numpy as np

from cache import make_cache_key, load_json, save_json
from config import FEATURE_CONFIG, INTERVAL, START_DATE, END_DATE
from features.engineer import compute_features
from models.trainer import train_model

logger = logging.getLogger(__name__)


def _estimate_confidence(model, model_type: str, X_latest: np.ndarray) -> float:
    """Return a heuristic confidence score in [0, 1]."""
    try:
        if model_type == "ridge":
            score = max(0.0, min(1.0, model.score(X_latest, model.predict(X_latest))))
            return float(score)

        if model_type in ("random_forest", "xgboost") and hasattr(model, "estimators_"):
            preds = np.array([t.predict(X_latest) for t in model.estimators_])
            std = float(preds.std())
            if std > 0:
                return float(1.0 / (1.0 + std))
    except Exception:
        pass
    return 0.5


def predict(
    ticker: str,
    model_type: str,
    horizon: int,
    interval: str = INTERVAL,
    start: str = START_DATE,
    end: str = END_DATE,
    config: Optional[dict] = None,
) -> dict:
    """Generate a cached prediction for *(ticker, model_type, horizon)*.

    Returns a dict matching the project's output schema::

        {
            "ticker": ...,
            "model": ...,
            "horizon": ...,
            "predicted_return": ...,
            "cached": True|False,
            "confidence": ...,
        }
    """
    cfg = config or FEATURE_CONFIG

    # Load model (cached)
    model, model_cached = train_model(ticker, model_type, horizon, interval, start, end, cfg)

    # Latest features for prediction
    features = compute_features(ticker, interval, start, end, cfg)
    latest = features.iloc[[-1]]

    feature_cols = [c for c in features.columns]
    X_latest = latest[feature_cols].values

    input_key = make_cache_key(
        operation="predict",
        ticker=ticker,
        model_type=model_type,
        horizon=horizon,
        interval=interval,
        start=start,
        end=end,
        config=cfg,
    )

    cached_result = load_json("predictions", input_key)
    if cached_result is not None:
        # Backward compatibility: fill fields that may be missing from older cache
        if "model" not in cached_result:
            cached_result["model"] = model_type
        logger.info("[CACHED] Prediction %s %s h=%d", ticker, model_type, horizon)
        return cached_result

    logger.info("[PREDICT] %s %s h=%d", ticker, model_type, horizon)

    pred = float(model.predict(X_latest)[0])
    confidence = _estimate_confidence(model, model_type, X_latest)

    result = {
        "ticker": ticker,
        "model": model_type,
        "horizon": f"{horizon}d",
        "predicted_return": round(pred, 4),
        "cached": False,
        "confidence": round(confidence, 4),
    }
    save_json(result, "predictions", input_key)
    return result
