"""News-based stock screening.

Fetches recent news for each ticker, computes sentiment, and returns
a composite news score.  Stops early once enough tickers with positive
news have been found (configurable via NEWS_SCREEN_MIN_CANDIDATES).
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Stop fetching news early once we have this many tickers with non-zero news
NEWS_SCREEN_MIN_CANDIDATES = 60


def _news_score_from_sentiment(sentiment: Optional[dict]) -> float:
    """Convert a sentiment result dict into a score in [0, 1].

    Formula: clamp(recency_weighted * 0.5 + 0.5, 0, 1)
    A neutral sentiment (0) maps to 0.5. Positive → up to 1. Negative → down to 0.
    Multiply by a log-scaled article count so more articles = higher confidence.
    """
    if sentiment is None:
        return 0.0

    avg = sentiment.get("recency_weighted", 0.0)
    count = sentiment.get("article_count", 0)

    # Shift [-1, 1] sentiment into [0, 1], scaled by article volume
    base = (avg * 0.5 + 0.5)
    volume_factor = np.log1p(count) / np.log1p(10)  # ~1.0 at 10 articles
    return min(1.0, base * volume_factor)


def screen_news(
    tickers: list[str],
    min_candidates: int = NEWS_SCREEN_MIN_CANDIDATES,
) -> dict[str, float]:
    """Score each ticker by news sentiment and article volume.

    Iterates through *tickers*, fetches cached (or fresh) news, computes
    sentiment, and returns a score in [0, 1].

    Stops early once *min_candidates* tickers with non-zero news scores
    have been found, since remaining tickers are likely to have no news.

    Returns:
        {ticker: news_sentiment_score (0-1)}
        Tickers with no news return 0.0 (not omitted, so they rank
        below any ticker with actual news).
    """
    if not tickers:
        logger.warning("[NEWS_SCREEN] No tickers to screen")
        return {}

    logger.info("[NEWS_SCREEN] Screening %d tickers for news sentiment ...", len(tickers))

    from news.fetcher import fetch_news
    from news.sentiment import compute_sentiment

    scores: dict[str, float] = {}
    found_with_news = 0

    for i, ticker in enumerate(tickers):
        try:
            articles = fetch_news(ticker)
            sentiment = compute_sentiment(
                articles if isinstance(articles, list) else articles.get("articles", []),
                ticker,
            )
            score = _news_score_from_sentiment(sentiment)
            scores[ticker] = score

            if score > 0:
                found_with_news += 1

            if (i + 1) % 50 == 0:
                logger.info(
                    "[NEWS_SCREEN] %d/%d tickers processed (%d with news)",
                    i + 1, len(tickers), found_with_news,
                )

            # Early stop: once we have enough news-positive tickers, assign
            # 0.0 to the rest (they probably have no news anyway).
            if found_with_news >= min_candidates and len(scores) >= len(tickers) // 2:
                remaining = len(tickers) - (i + 1)
                if remaining > 0:
                    logger.info(
                        "[NEWS_SCREEN] Early stop — %d news-positive tickers found, "
                        "assigning 0.0 to remaining %d",
                        found_with_news, remaining,
                    )
                for t in tickers[i + 1:]:
                    scores[t] = 0.0
                break

        except Exception as e:
            logger.debug("[NEWS_SCREEN] %s failed: %s", ticker, e)
            scores[ticker] = 0.0

    logger.info(
        "[NEWS_SCREEN] Done — %d/%d tickers have non-zero news scores",
        found_with_news, len(tickers),
    )
    return scores
