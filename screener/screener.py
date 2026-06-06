"""Market screener orchestrator — finds the most promising stocks each day.

Pipeline:
  1. Momentum screen — quick technical pass across the full universe
  2. Sector rotation — score by sector ETF performance
  3. News screen — sentiment + article volume

The top N candidates are returned for the full ML pipeline.
"""

import logging
from typing import Optional

import pandas as pd

from config import (
    SCREENER_MOMENTUM_WEIGHT,
    SCREENER_NEWS_WEIGHT,
    SCREENER_SECTOR_WEIGHT,
    SCREENER_TOP_N,
)
from screener.momentum import screen_momentum
from screener.news_screener import screen_news
from screener.universe import BROAD_UNIVERSE, get_sector_etf

logger = logging.getLogger(__name__)


def _screen_sector_rotation(tickers: list[str]) -> dict[str, float]:
    """Score each ticker by its sector ETF's recent performance.

    Fetches price data for all sector ETFs used by *tickers*, computes
    the 20-day return, and assigns that return as the sector score for
    each ticker in that sector.

    Returns:
        {ticker: sector_score (0-1)}
    """
    from screener.momentum import screen_momentum

    # Collect unique sector ETFs referenced by the universe
    sector_etfs = sorted({get_sector_etf(t) for t in tickers})

    if not sector_etfs:
        return {}

    # Get momentum scores for sector ETFs (returns dict[ticker, composite_score])
    etf_scores = screen_momentum(sector_etfs)
    if not etf_scores:
        return {}

    # Map each ticker to its sector ETF's score
    result: dict[str, float] = {}
    for t in tickers:
        sector_etf = get_sector_etf(t)
        result[t] = etf_scores.get(sector_etf, 0.5)

    return result


def screen_market(
    universe: Optional[list[str]] = None,
    top_n: int = SCREENER_TOP_N,
    held_tickers: Optional[set[str]] = None,
    momentum_weight: float = SCREENER_MOMENTUM_WEIGHT,
    news_weight: float = SCREENER_NEWS_WEIGHT,
    sector_weight: float = SCREENER_SECTOR_WEIGHT,
) -> list[str]:
    """Run the full market screen and return the top ranked tickers.

    Steps:
      1. Momentum screen (quick technical pass)
      2. Sector rotation screen
      3. News sentiment screen
      4. Weighted composite score
      5. Return top N + held tickers

    Args:
        universe: List of tickers to screen (defaults to BROAD_UNIVERSE).
        top_n: Number of top candidates to return.
        held_tickers: Set of currently-held tickers (always included).
        momentum_weight, news_weight, sector_weight: Score weights.

    Returns:
        Ranked list of ticker strings (top candidates + held positions).
    """
    if universe is None:
        universe = BROAD_UNIVERSE

    if held_tickers is None:
        held_tickers = set()

    logger.info("=" * 55)
    logger.info("  MARKET SCREENER")
    logger.info("=" * 55)
    logger.info("  Universe:        %d tickers", len(universe))
    logger.info("  Held positions:  %d", len(held_tickers))
    logger.info("  Target top N:    %d", top_n)

    # Remove sector ETFs and broad ETFs from screening candidates
    # (we use sectors for rotation, not as trade candidates)
    screening_universe = [
        t for t in universe
        if not t.startswith("XL") and t not in ("SPY", "IVV", "VOO", "VTI", "QQQ")
    ]

    # --- Step 1: Momentum ---
    logger.info("")
    logger.info("-- Step 1/3: Momentum screen --")
    momentum_scores = screen_momentum(screening_universe)
    if not momentum_scores:
        logger.warning("[SCREENER] Momentum screen returned no results — using defaults")
        momentum_scores = {t: 0.5 for t in screening_universe}

    # --- Step 2: Sector rotation ---
    logger.info("")
    logger.info("-- Step 2/3: Sector rotation screen --")
    sector_scores = _screen_sector_rotation(screening_universe)
    if not sector_scores:
        logger.warning("[SCREENER] Sector rotation returned no results — using defaults")
        sector_scores = {t: 0.5 for t in screening_universe}

    # --- Step 3: News ---
    logger.info("")
    logger.info("-- Step 3/3: News sentiment screen --")
    news_scores = screen_news(screening_universe)

    # --- Composite score ---
    all_tickers = set(momentum_scores) | set(sector_scores) | set(news_scores)

    scores: dict[str, float] = {}
    for t in all_tickers:
        m = momentum_scores.get(t, 0.5)
        s = sector_scores.get(t, 0.5)
        n = news_scores.get(t, 0.0)
        scores[t] = m * momentum_weight + s * sector_weight + n * news_weight

    # --- Rank ---
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    # Separate held tickers from new candidates
    held_in_ranked = [t for t, _ in ranked if t in held_tickers]
    new_candidates = [(t, s) for t, s in ranked if t not in held_tickers]

    # Take top N new candidates
    selected_new = [t for t, _ in new_candidates[:top_n]]

    # Combine: held tickers always included, then top new candidates
    final = held_in_ranked + [t for t in selected_new if t not in held_in_ranked]

    logger.info("")
    logger.info("-" * 55)
    logger.info("  SCREENER RESULTS")
    logger.info("-" * 55)
    logger.info("  Held positions included: %d", len(held_in_ranked))
    logger.info("  New candidates selected: %d", len(selected_new))
    logger.info("  Total candidates:        %d", len(final))

    if held_in_ranked:
        logger.info("  Held: %s", ", ".join(held_in_ranked))

    # Log top 10 new candidates with scores
    logger.info("  Top new candidates:")
    for i, (t, s) in enumerate(new_candidates[:10]):
        logger.info("    %2d. %-6s  score=%.4f  mom=%.2f  sect=%.2f  news=%.2f",
                    i + 1, t, s,
                    momentum_scores.get(t, 0),
                    sector_scores.get(t, 0),
                    news_scores.get(t, 0))

    logger.info("=" * 55)
    return final
