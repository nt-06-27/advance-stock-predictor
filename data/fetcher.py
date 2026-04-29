import logging
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import yfinance as yf
from dotenv import load_dotenv

from cache import make_cache_key, load_df, save_df
from config import ALPACA_DATA_URL, INTERVAL, START_DATE

load_dotenv()
logger = logging.getLogger(__name__)


class DataCache:
    def __init__(self, hit: bool) -> None:
        self.hit = hit


def _fetch_alpaca(
    ticker: str, interval: str, start: str, end: str
) -> Optional[pd.DataFrame]:
    import os

    api_key = os.getenv("APCA_API_KEY_ID")
    secret = os.getenv("APCA_SECRET_KEY")
    if not api_key or not secret:
        return None

    try:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        client = StockHistoricalDataClient(api_key, secret)
        tf_map = {"1d": TimeFrame.Day, "1wk": TimeFrame.Week, "1mo": TimeFrame.Month}

        request = StockBarsRequest(
            symbol_or_symbols=ticker,
            timeframe=tf_map.get(interval, TimeFrame.Day),
            start=datetime.strptime(start, "%Y-%m-%d"),
            end=datetime.strptime(end, "%Y-%m-%d") + timedelta(days=1),
        )

        bars = client.get_stock_bars(request)
        if ticker not in bars.data:
            return None

        df = pd.DataFrame(
            {"Open": b.open, "High": b.high, "Low": b.low, "Close": b.close, "Volume": b.volume}
            for b in bars.data[ticker]
        )
        df.index = pd.DatetimeIndex([b.timestamp for b in bars.data[ticker]]).tz_localize(None)
        df.index.name = "Date"
        return df

    except Exception as e:
        logger.warning("Alpaca fetch failed for %s: %s — falling back to yfinance", ticker, e)
        return None


def _fetch_yfinance(ticker: str, interval: str, start: str, end: str) -> pd.DataFrame:
    df = yf.download(
        ticker, interval=interval, start=start, end=end,
        auto_adjust=True, multi_level_index=False,
    )
    return df


def fetch_data(
    ticker: str,
    interval: str = INTERVAL,
    start: str = START_DATE,
    end: Optional[str] = None,
) -> tuple[pd.DataFrame, DataCache]:
    """Return OHLCV data with incremental caching.

    Cache key excludes *end* so it stays stable across days.
    On cache hit, checks if the latest date is before *end* and only
    fetches the missing slice — avoids re-downloading years of history.
    """
    if end is None:
        end = datetime.now().strftime("%Y-%m-%d")

    # Stable key: no end date so it doesn't change daily
    key = make_cache_key(operation="fetch_data", ticker=ticker, interval=interval, start=start)

    cached = load_df("data", key)
    if cached is not None:
        last_date = cached.index.max()
        end_dt = datetime.strptime(end, "%Y-%m-%d")

        if last_date >= end_dt - timedelta(days=1):
            logger.info("[CACHED] Data %s (%s %s – %s)", ticker, interval, start, end)
            return cached, DataCache(hit=True)

        # Incremental: fetch from last cached date (overlap is deduplicated)
        missing_start = last_date.strftime("%Y-%m-%d")
        logger.info("[FETCH] Incremental %s (%s – %s)", ticker, missing_start, end)
        new_df_alpaca = _fetch_alpaca(ticker, interval, missing_start, end)
        new_df = new_df_alpaca if new_df_alpaca is not None else _fetch_yfinance(ticker, interval, missing_start, end)

        if not new_df.empty:
            combined = pd.concat([cached, new_df])
            combined = combined[~combined.index.duplicated(keep="last")]
            combined.sort_index(inplace=True)
            save_df(combined, "data", key)
            return combined, DataCache(hit=True)
        return cached, DataCache(hit=True)

    # Full fetch
    logger.info("[FETCH] Full %s (%s %s – %s)", ticker, interval, start, end)
    df = _fetch_alpaca(ticker, interval, start, end)
    if df is None:
        df = _fetch_yfinance(ticker, interval, start, end)

    if df is None or df.empty:
        raise ValueError(f"No data returned for {ticker}")

    save_df(df, "data", key)
    return df, DataCache(hit=False)
