import logging
import os
from collections import defaultdict
from typing import Any, Optional

from dotenv import load_dotenv

from config import ALPACA_PAPER_URL, MIN_CONFIDENCE, TRADE_ALLOCATION

load_dotenv()
logger = logging.getLogger(__name__)


def _get_trading_client():
    """Return an Alpaca TradingClient for paper trading, or None if not configured."""
    from alpaca.trading.client import TradingClient

    api_key = os.getenv("APCA_API_KEY_ID")
    secret = os.getenv("APCA_SECRET_KEY")
    if not api_key or not secret:
        logger.warning("Alpaca API keys not set — trading disabled")
        return None
    return TradingClient(api_key, secret, paper=True)


def get_account_info() -> Optional[dict]:
    """Return account summary: cash, portfolio value, buying power."""
    client = _get_trading_client()
    if client is None:
        return None
    try:
        account = client.get_account()
        return {
            "cash": float(account.cash),
            "portfolio_value": float(account.portfolio_value),
            "buying_power": float(account.buying_power),
            "equity": float(account.equity),
        }
    except Exception as e:
        logger.error("Failed to get account info: %s", e)
        return None


def place_trades(
    predictions: list[dict],
    confidence_threshold: float = MIN_CONFIDENCE,
    allocation: float = TRADE_ALLOCATION,
) -> list[dict]:
    """Submit paper trades based on aggregated prediction signals.

    For each ticker with a 5-day horizon:
      - avg predicted_return > 0  → BUY market order
      - avg predicted_return < 0  → SELL market order
    Only trades with avg confidence >= *confidence_threshold* are executed.

    Returns a list of order confirmation dicts.
    """
    from alpaca.trading.enums import OrderSide, TimeInForce
    from alpaca.trading.requests import MarketOrderRequest

    client = _get_trading_client()
    if client is None:
        return []

    # Aggregate predictions per ticker (5d horizon only)
    agg = defaultdict(lambda: {"returns": [], "confidences": []})
    for p in predictions:
        if p.get("horizon") != "5d":
            continue
        agg[p["ticker"]]["returns"].append(p["predicted_return"])
        agg[p["ticker"]]["confidences"].append(p["confidence"])

    orders = []
    for ticker, v in agg.items():
        avg_return = sum(v["returns"]) / len(v["returns"])
        avg_conf = sum(v["confidences"]) / len(v["confidences"])
        if avg_conf < confidence_threshold:
            logger.info("[SKIP] %s conf=%.2f below threshold %.2f", ticker, avg_conf, confidence_threshold)
            continue

        side = OrderSide.BUY if avg_return > 0 else OrderSide.SELL
        notional = round(allocation, 2)

        try:
            req = MarketOrderRequest(
                symbol=ticker,
                notional=notional,
                side=side,
                time_in_force=TimeInForce.DAY,
            )
            order = client.submit_order(req)
            logger.info(
                "[TRADE] %s %s $%.2f → order %s (%s)",
                side.name, ticker, notional, order.id, order.status,
            )
            orders.append({
                "ticker": ticker,
                "side": side.name,
                "notional": notional,
                "order_id": str(order.id),
                "status": order.status,
                "confidence": round(avg_conf, 2),
                "predicted_return": round(avg_return, 4),
            })
        except Exception as e:
            logger.error("[TRADE FAIL] %s %s: %s", side.name, ticker, e)
            orders.append({
                "ticker": ticker,
                "side": side.name,
                "notional": notional,
                "error": str(e),
            })

    return orders
