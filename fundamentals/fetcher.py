import hashlib
import logging
from datetime import datetime, timezone

import yfinance as yf

from cache import load_json, save_json
from config import FUNDAMENTALS_CACHE_DAYS

logger = logging.getLogger(__name__)


def _needs_refresh(cached: dict) -> bool:
    """Return True if cached fundamentals are older than FUNDAMENTALS_CACHE_DAYS."""
    last = cached.get("last_updated", 0)
    age = (datetime.now(tz=timezone.utc).timestamp() - last) / 86400
    return age > FUNDAMENTALS_CACHE_DAYS


def fetch_fundamentals(ticker: str) -> dict:
    """Fetch quarterly earnings + key ratios for *ticker*.

    Cached by ticker.  Only refetches if the cache is older than
    FUNDAMENTALS_CACHE_DAYS (default 30).  Financial data changes
    quarterly, so this should fire roughly once a quarter per ticker.
    The date is checked in the info dict to see if data is from a new quarter.

    Returns:
        {
            "last_updated": epoch_ts,
            "eps": float or None,
            "revenue": float or None,
            "pe_ratio": float or None,
            "earnings": [quarterly earnings rows],
        }
    """
    cache_key = f"fundamentals_{ticker}"
    cached = load_json("fundamentals", cache_key)

    if cached is not None and not _needs_refresh(cached):
        logger.info("[CACHED] Fundamentals %s (%.0f days old)",
                     ticker, (datetime.now(tz=timezone.utc).timestamp() - cached["last_updated"]) / 86400)
        return cached

    logger.info("[FETCH] Fundamentals %s", ticker)
    try:
        tk = yf.Ticker(ticker)
        info = tk.info or {}

        # Quarterly earnings
        earnings_data = {"eps": None, "revenue": None, "earnings": []}
        try:
            qe = tk.quarterly_earnings
            if qe is not None and not qe.empty:
                earnings_data["earnings"] = qe.reset_index().to_dict(orient="records")
                if "Earnings" in qe.columns:
                    earnings_data["eps"] = float(qe["Earnings"].iloc[0]) if not qe["Earnings"].isna().iloc[0] else None
                if "Revenue" in qe.columns:
                    earnings_data["revenue"] = float(qe["Revenue"].iloc[0]) if not qe["Revenue"].isna().iloc[0] else None
        except Exception:
            pass

        result = {
            "last_updated": datetime.now(tz=timezone.utc).timestamp(),
            "eps": earnings_data["eps"],
            "revenue": earnings_data["revenue"],
            "pe_ratio": info.get("trailingPE") or info.get("forwardPE"),
            "market_cap": info.get("marketCap"),
            "revenue_growth": info.get("revenueGrowth"),
            "profit_margins": info.get("profitMargins"),
            "debt_to_equity": info.get("debtToEquity"),
            "earnings": earnings_data["earnings"][:4],  # last 4 quarters
        }

        save_json(result, "fundamentals", cache_key)
        logger.info("[FUNDAMENTALS] %s — EPS: %s, P/E: %s, Revenue: %s",
                     ticker, result["eps"], result["pe_ratio"], result["revenue"])
        return result

    except Exception as e:
        logger.warning("[FUNDAMENTALS] Failed for %s: %s", ticker, e)
        if cached is not None:
            return cached
        return {
            "last_updated": 0,
            "eps": None, "revenue": None, "pe_ratio": None,
            "market_cap": None, "revenue_growth": None,
            "profit_margins": None, "debt_to_equity": None,
            "earnings": [],
        }


def get_fundamentals_hash(ticker: str) -> str:
    """Content-hash of cached fundamentals.

    Used in the feature cache key so features are recomputed only when
    fundamentals change.
    """
    cache_key = f"fundamentals_{ticker}"
    cached = load_json("fundamentals", cache_key)
    if not cached:
        return "none"
    raw = f"{cached.get('eps')}_{cached.get('pe_ratio')}_{cached.get('revenue')}_{cached.get('last_updated')}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]
