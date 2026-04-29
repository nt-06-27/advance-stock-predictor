import logging
from typing import Optional

import pandas as pd

from cache import make_cache_key, load_df, save_df
from config import FEATURE_CONFIG, INTERVAL, START_DATE, END_DATE
from data.fetcher import fetch_data
from features.engineer import compute_features

logger = logging.getLogger(__name__)


def build_dataset(
    ticker: str,
    horizon: int,
    interval: str = INTERVAL,
    start: str = START_DATE,
    end: str = END_DATE,
    config: Optional[dict] = None,
) -> pd.DataFrame:
    """Build a supervised dataset: features + forward-return target.

    The target is the future return ``horizon`` trading days ahead.
    Rows with NaN targets (end of series) are dropped.

    Fully cached — re-running with identical parameters costs nothing.
    """
    cfg = config or FEATURE_CONFIG
    key = make_cache_key(
        operation="build_dataset",
        ticker=ticker,
        horizon=horizon,
        interval=interval,
        start=start,
        end=end,
        config=cfg,
    )

    cached = load_df("datasets", key)
    if cached is not None:
        logger.info("[CACHED] Dataset %s h=%d", ticker, horizon)
        return cached

    logger.info("[BUILD] Dataset %s h=%d", ticker, horizon)
    features = compute_features(ticker, interval, start, end, cfg)

    # Target: forward return
    df, _ = fetch_data(ticker, interval, start, end)
    close = df["Close"].squeeze()
    future_price = close.shift(-horizon)
    target = (future_price - close) / close
    target.name = "target"

    dataset = features.join(target)
    dataset.dropna(subset=["target"], inplace=True)

    save_df(dataset, "datasets", key)
    return dataset
