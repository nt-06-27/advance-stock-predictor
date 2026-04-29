import logging
from typing import Optional

from config import (
    FEATURE_CONFIG,
    HORIZONS,
    INTERVAL,
    START_DATE,
    END_DATE,
    TICKERS,
)
from data.fetcher import fetch_data
from dataset.builder import build_dataset
from evaluate.evaluator import evaluate
from features.engineer import compute_features
from models.trainer import MODEL_REGISTRY, train_model
from predict.predictor import predict

logger = logging.getLogger(__name__)


def run_pipeline(
    tickers: Optional[list[str]] = None,
    horizons: Optional[list[int]] = None,
    model_types: Optional[list[str]] = None,
    interval: str = INTERVAL,
    start: str = START_DATE,
    end: str = END_DATE,
    config: Optional[dict] = None,
    trade: bool = False,
) -> dict:
    """End-to-end pipeline: data → news → fundamentals → features → ... → predict.

    Every step respects the cache.  When *trade* is True, submits paper
    trades via Alpaca for 5d-horizon predictions with sufficient confidence.
    """
    tickers = tickers or TICKERS
    horizons = horizons or HORIZONS
    model_types = model_types or list(MODEL_REGISTRY)
    cfg = config or FEATURE_CONFIG

    results = {"predictions": [], "evaluations": [], "orders": []}

    for ticker in tickers:
        logger.info("=== %s ===", ticker)

        # Step 1: Price data
        logger.info("-- Data %s --", ticker)
        fetch_data(ticker, interval, start, end)

        # Step 2: News
        logger.info("-- News %s --", ticker)
        try:
            from news.fetcher import fetch_news
            fetch_news(ticker)
        except Exception as e:
            logger.warning("News fetch failed for %s: %s", ticker, e)

        # Step 3: Fundamentals
        logger.info("-- Fundamentals %s --", ticker)
        try:
            from fundamentals.fetcher import fetch_fundamentals
            fetch_fundamentals(ticker)
        except Exception as e:
            logger.warning("Fundamentals fetch failed for %s: %s", ticker, e)

        for horizon in horizons:
            # Step 4: Features (now includes news + fundamental columns)
            logger.info("-- Features %s h=%d --", ticker, horizon)
            compute_features(ticker, interval, start, end, cfg)

            # Step 5: Dataset
            logger.info("-- Dataset %s h=%d --", ticker, horizon)
            build_dataset(ticker, horizon, interval, start, end, cfg)

            for model_type in model_types:
                # Step 6: Train
                logger.info("-- Train %s %s h=%d --", ticker, model_type, horizon)
                train_model(ticker, model_type, horizon, interval, start, end, cfg)

                # Step 7: Eval
                logger.info("-- Eval %s %s h=%d --", ticker, model_type, horizon)
                eval_result = evaluate(ticker, model_type, horizon, interval, start, end, cfg)
                results["evaluations"].append(eval_result)

                # Step 8: Predict
                logger.info("-- Predict %s %s h=%d --", ticker, model_type, horizon)
                pred_result = predict(ticker, model_type, horizon, interval, start, end, cfg)
                results["predictions"].append(pred_result)

    if trade:
        logger.info("")
        logger.info("=== TRADING ===")
        from trading.executor import get_account_info, place_trades

        acct = get_account_info()
        if acct:
            logger.info("Account: $%.2f cash, $%.2f portfolio", acct["cash"], acct["portfolio_value"])

        results["orders"] = place_trades(results["predictions"])

    return results
