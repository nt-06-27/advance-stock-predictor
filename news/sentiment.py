import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional

from cache import load_json, save_json
from config import NEWS_SENTIMENT_WINDOW

logger = logging.getLogger(__name__)

try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

    _analyzer = SentimentIntensityAnalyzer()
    VADER_AVAILABLE = True
except ImportError:
    _analyzer = None
    VADER_AVAILABLE = False
    logger.warning("vaderSentiment not installed — sentiment scores will be 0.0")


def _analyze_sentiment(text: str) -> float:
    """Return compound sentiment score (-1 to 1)."""
    if not VADER_AVAILABLE or not _analyzer:
        return 0.0
    return _analyzer.polarity_scores(text)["compound"]


def compute_sentiment(articles: list[dict], ticker: str) -> Optional[dict]:
    """Compute and cache sentiment scores for uncached articles.

    Returns:
        {
            "avg_sentiment": float,      # mean compound score
            "article_count": int,        # articles in lookback window
            "recency_weighted": float,   # more recent = higher weight
        }
    """
    if not articles:
        return None

    now = datetime.now(tz=timezone.utc)
    window_sec = NEWS_SENTIMENT_WINDOW * 86400

    scored = []
    for article in articles:
        ts = article.get("_ts", 0)

        # Check for cached sentiment
        cache_key = f"sentiment_{article['_hash']}"
        cached = load_json("news", cache_key)
        if cached is not None:
            score = cached["compound"]
        else:
            text = article.get("title", "")
            score = _analyze_sentiment(text)
            save_json({"compound": score, "hash": article["_hash"]}, "news", cache_key)

        age = now.timestamp() - ts
        if age <= window_sec:
            scored.append((score, ts))

    if not scored:
        return {"avg_sentiment": 0.0, "article_count": 0, "recency_weighted": 0.0}

    scores = [s[0] for s in scored]
    avg = sum(scores) / len(scores)

    # Recency weight: linear decay from 1 (now) to 0 (window edge)
    weights = [max(0.0, 1.0 - (now.timestamp() - ts) / window_sec) for _, ts in scored]
    weighted = sum(s * w for s, w in zip(scores, weights)) / sum(weights) if sum(weights) > 0 else avg

    return {
        "avg_sentiment": round(avg, 4),
        "article_count": len(scored),
        "recency_weighted": round(weighted, 4),
    }
