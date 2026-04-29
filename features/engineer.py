import logging
from typing import Optional

import numpy as np
import pandas as pd

from cache import make_cache_key, load_df, save_df
from config import FEATURE_CONFIG, INTERVAL, START_DATE, END_DATE
from data.fetcher import fetch_data

logger = logging.getLogger(__name__)


def _rsi(series: pd.Series, period: int) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _macd(series: pd.Series, fast: int, slow: int, signal: int) -> pd.DataFrame:
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return pd.DataFrame({"MACD": macd_line, "MACD_signal": signal_line, "MACD_hist": histogram})


def _add_news_features(features: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Add news sentiment columns as constant features (latest available data)."""
    try:
        from news.fetcher import fetch_news, get_news_hash
        from news.sentiment import compute_sentiment

        articles = fetch_news(ticker)
        sentiment = compute_sentiment(articles, ticker)
        if sentiment:
            features["news_sentiment"] = sentiment["avg_sentiment"]
            features["article_count"] = sentiment["article_count"]
            features["news_recency"] = sentiment["recency_weighted"]
        else:
            features["news_sentiment"] = 0.0
            features["article_count"] = 0
            features["news_recency"] = 0.0
    except Exception as e:
        logger.warning("News features failed for %s: %s", ticker, e)
        features["news_sentiment"] = 0.0
        features["article_count"] = 0
        features["news_recency"] = 0.0
    return features


def _add_fundamental_features(features: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Add fundamental columns as constant features (latest available data)."""
    try:
        from fundamentals.fetcher import fetch_fundamentals, get_fundamentals_hash

        fund = fetch_fundamentals(ticker)
        features["pe_ratio"] = fund.get("pe_ratio") or 0.0
        features["eps"] = fund.get("eps") or 0.0
        features["revenue_bn"] = (fund.get("revenue") or 0) / 1e9
        features["revenue_growth"] = fund.get("revenue_growth") or 0.0
        features["profit_margin"] = fund.get("profit_margins") or 0.0
    except Exception as e:
        logger.warning("Fundamental features failed for %s: %s", ticker, e)
        features["pe_ratio"] = 0.0
        features["eps"] = 0.0
        features["revenue_bn"] = 0.0
        features["revenue_growth"] = 0.0
        features["profit_margin"] = 0.0
    return features


def compute_features(
    ticker: str,
    interval: str = INTERVAL,
    start: str = START_DATE,
    end: str = END_DATE,
    config: Optional[dict] = None,
) -> pd.DataFrame:
    """Compute deterministic technical-indicator + news + fundamental features.

    Cache key includes hashes of news and fundamental data so that
    features are recomputed only when those inputs change.
    """
    cfg = config or FEATURE_CONFIG

    # Content-hashes for cache key extension
    news_hash = "none"
    fund_hash = "none"
    try:
        from news.fetcher import get_news_hash
        news_hash = get_news_hash(ticker)
    except Exception:
        pass
    try:
        from fundamentals.fetcher import get_fundamentals_hash
        fund_hash = get_fundamentals_hash(ticker)
    except Exception:
        pass

    key = make_cache_key(
        operation="compute_features",
        ticker=ticker,
        interval=interval,
        start=start,
        end=end,
        config=cfg,
        news_hash=news_hash,
        fundamentals_hash=fund_hash,
    )

    cached = load_df("features", key)
    if cached is not None:
        logger.info("[CACHED] Features %s", ticker)
        return cached

    logger.info("[COMPUTE] Features %s", ticker)
    df, _ = fetch_data(ticker, interval, start, end)
    close = df["Close"].squeeze()
    features = pd.DataFrame(index=df.index)

    # Returns
    features["return_1d"] = close.pct_change()
    features["log_return_1d"] = np.log(close / close.shift(1))

    # Moving averages
    for w in cfg["ma_windows"]:
        features[f"MA_{w}"] = close.rolling(window=w).mean()
        features[f"MA_{w}_ratio"] = close / features[f"MA_{w}"]

    # RSI
    features["RSI"] = _rsi(close, cfg["rsi_period"])

    # MACD
    macd_df = _macd(close, cfg["macd_fast"], cfg["macd_slow"], cfg["macd_signal"])
    features = pd.concat([features, macd_df], axis=1)

    # Volatility
    features["volatility"] = features["return_1d"].rolling(window=cfg["volatility_window"]).std()

    # Lag features
    for lag in cfg["lag_days"]:
        features[f"return_lag_{lag}"] = features["return_1d"].shift(lag)

    # News features (constant per ticker)
    features = _add_news_features(features, ticker)

    # Fundamental features (constant per ticker)
    features = _add_fundamental_features(features, ticker)

    features.dropna(inplace=True)
    save_df(features, "features", key)
    return features
