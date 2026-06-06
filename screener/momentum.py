"""Technical momentum screening — quick pass across the full universe.

Downloads OHLCV for all tickers in a single batch call, then computes
momentum signals per ticker:
  - 20-day price return
  - 50-day MA ratio (price / 50MA)
  - Volume ratio (20d avg volume / 50d avg volume)

Each signal is normalized to [0, 1] and averaged into a single score.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

# Minimum data points needed for reliable momentum calculation
MIN_VALID_DAYS = 60


def _normalize(series: pd.Series) -> pd.Series:
    """Min-max normalize a series into [0, 1], handling edge cases."""
    mn, mx = series.min(), series.max()
    if mx == mn or pd.isna(mx - mn):
        return pd.Series(0.5, index=series.index)
    return (series - mn) / (mx - mn)


def screen_momentum(
    tickers: list[str],
    period: str = "3mo",
    interval: str = "1d",
) -> dict[str, float]:
    """Score each ticker on price momentum and volume.

    Downloads data for all *tickers* in one yfinance call, computes
    three signals per ticker, normalizes each to [0,1], and returns a
    mean composite score.

    Returns:
        {ticker: composite_momentum_score (0-1)}
        Tickers with insufficient data are omitted.
    """
    if not tickers:
        logger.warning("[MOMENTUM] No tickers to screen")
        return {}

    logger.info("[MOMENTUM] Screening %d tickers ...", len(tickers))

    try:
        # Batch download — yfinance handles multi-ticker efficiently
        raw: Optional[pd.DataFrame] = yf.download(
            tickers,
            period=period,
            interval=interval,
            auto_adjust=True,
            multi_level_index=False,
            group_by="ticker",
            progress=False,
        )
    except Exception as e:
        logger.warning("[MOMENTUM] Batch download failed: %s", e)
        return {}

    if raw is None or raw.empty:
        logger.warning("[MOMENTUM] No data returned")
        return {}

    scores: dict[str, float] = {}

    for ticker in tickers:
        try:
            if isinstance(raw.columns, pd.MultiIndex):
                # Multi-ticker download returns MultiIndex columns
                close_col = (ticker, "Close") if ticker in raw.columns.levels[0] else None
                vol_col = (ticker, "Volume") if ticker in raw.columns.levels[0] else None
            else:
                close_col = vol_col = None

            # Handle both single and multi-ticker DataFrame shapes
            if close_col is None:
                # Try single-ticker flat columns
                df = raw
                if "Close" not in df.columns:
                    continue
                close = df["Close"].squeeze()
                volume = df["Volume"].squeeze() if "Volume" in df.columns else pd.Series(dtype=float)
            else:
                close = raw[close_col].squeeze()
                volume = raw[vol_col].squeeze() if vol_col is not None else pd.Series(dtype=float)

            close = close.dropna()
            if len(close) < MIN_VALID_DAYS:
                continue

            # --- 20-day price return ---
            ret_20d = (close.iloc[-1] / close.iloc[-20] - 1) if len(close) >= 20 else 0.0

            # --- 50-day MA ratio ---
            ma_50 = close.rolling(50).mean().iloc[-1]
            ma_50_ratio = (close.iloc[-1] / ma_50 - 1) if pd.notna(ma_50) and ma_50 > 0 else 0.0

            # --- Volume ratio: 20d avg / 50d avg ---
            volume = volume.dropna()
            if len(volume) >= 20:
                vol_20 = volume.tail(20).mean()
                vol_50 = volume.tail(50).mean() if len(volume) >= 50 else vol_20
                vol_ratio = (vol_20 / vol_50 - 1) if vol_50 > 0 else 0.0
            else:
                vol_ratio = 0.0

            scores[ticker] = {
                "ret_20d": ret_20d,
                "ma_50_ratio": ma_50_ratio,
                "vol_ratio": vol_ratio,
            }

        except Exception as e:
            logger.debug("[MOMENTUM] Skipping %s: %s", ticker, e)
            continue

    if not scores:
        logger.warning("[MOMENTUM] No valid momentum data for any ticker")
        return {}

    # Build DataFrame for normalization
    df_scores = pd.DataFrame.from_dict(scores, orient="index")
    df_scores.fillna(0.0, inplace=True)

    # Clip outliers to 3 std devs then normalize
    for col in df_scores.columns:
        mean = df_scores[col].mean()
        std = df_scores[col].std()
        if std > 0:
            df_scores[col] = df_scores[col].clip(mean - 3 * std, mean + 3 * std)

    # Normalize each signal to [0, 1]
    normalized = pd.DataFrame(index=df_scores.index)
    for col in df_scores.columns:
        normalized[col] = _normalize(df_scores[col])

    # Composite: simple average of the three signals
    composite = normalized.mean(axis=1)

    result = composite.to_dict()
    logger.info("[MOMENTUM] Screened %d tickers with momentum data", len(result))
    return result
