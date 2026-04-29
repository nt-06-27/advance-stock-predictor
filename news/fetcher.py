import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Optional

import yfinance as yf

from cache import load_json, save_json
from config import MAX_NEWS_ARTICLES

logger = logging.getLogger(__name__)


def _article_hash(article: dict) -> str:
    raw = f"{article.get('title', '')}_{article.get('content', '')}_{article.get('link', '')}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _parse_timestamp(article: dict) -> Optional[datetime]:
    ts = article.get("providerPublishTime") or article.get("pubDate", 0)
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc)
    except (ValueError, TypeError):
        return None


def fetch_news(ticker: str) -> list[dict]:
    """Fetch recent news for *ticker*, returning only new articles.

    Cached articles are loaded first.  Only articles published after the
    latest cached timestamp are fetched from yfinance.  Results are
    deduplicated by content hash and merged back into the cache.
    """
    cache_key = f"news_{ticker}"
    cached = load_json("news", cache_key) or []
    seen_hashes = {a["_hash"] for a in cached if "_hash" in a}

    latest_ts = max(
        (a["_ts"] for a in cached if "_ts" in a),
        default=0,
    )

    logger.info("[NEWS] Checking %s (last article: %s)", ticker,
                datetime.fromtimestamp(latest_ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
                if latest_ts > 0 else "never")

    try:
        raw = yf.Ticker(ticker).news or []
    except Exception as e:
        logger.warning("[NEWS] yfinance failed for %s: %s", ticker, e)
        raw = []

    fresh = []
    for article in raw:
        ts = article.get("providerPublishTime", 0)
        if ts <= latest_ts:
            continue
        h = _article_hash(article)
        if h in seen_hashes:
            continue
        seen_hashes.add(h)
        entry = {
            "title": article.get("title", ""),
            "link": article.get("link", ""),
            "source": (article.get("publisher") or article.get("source", "")),
            "timestamp": ts,
            "_ts": ts,
            "_hash": h,
        }
        fresh.append(entry)

    if fresh:
        cached.extend(fresh)
        # Keep only the latest N articles per ticker (capped)
        cached.sort(key=lambda a: a.get("_ts", 0), reverse=True)
        cached[:] = cached[:MAX_NEWS_ARTICLES]
        save_json({"articles": cached}, "news", cache_key)
        logger.info("[NEWS] %d new articles for %s (total cached: %d)", len(fresh), ticker, len(cached))
    else:
        logger.info("[NEWS] No new articles for %s", ticker)

    return cached


def get_news_hash(ticker: str) -> str:
    """Return a content-hash of all cached news for *ticker*.

    Used in the feature cache key so features are recomputed only when
    the underlying news data changes.
    """
    cache_key = f"news_{ticker}"
    cached = load_json("news", cache_key)
    if not cached:
        return "none"
    titles = "".join(a.get("title", "") for a in cached.get("articles", []))
    return hashlib.sha256(titles.encode()).hexdigest()[:12]
