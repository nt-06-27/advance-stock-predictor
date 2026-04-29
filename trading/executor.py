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


def _get_position_qty(client, ticker: str) -> float:
    """Return the number of shares held for *ticker*, or 0 if no position."""
    try:
        pos = client.get_open_position(ticker)
        return float(pos.qty)
    except Exception:
        return 0.0


def place_trades(
    predictions: list[dict],
    confidence_threshold: float = MIN_CONFIDENCE,
    allocation: float = TRADE_ALLOCATION,
) -> list[dict]:
    """Submit paper trades based on aggregated prediction signals.

    For each ticker with a 5-day horizon:
      - avg predicted_return > 0  → BUY market order (fractional notional)
      - avg predicted_return < 0  → SELL existing position only (full qty)
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

        if avg_return > 0:
            # BUY: fractional market order
            try:
                req = MarketOrderRequest(
                    symbol=ticker,
                    notional=round(allocation, 2),
                    side=OrderSide.BUY,
                    time_in_force=TimeInForce.DAY,
                )
                order = client.submit_order(req)
                logger.info("[TRADE] BUY %s $%.2f → order %s (%s)", ticker, allocation, order.id, order.status)
                orders.append({
                    "ticker": ticker,
                    "side": "BUY",
                    "notional": allocation,
                    "order_id": str(order.id),
                    "status": order.status,
                    "confidence": round(avg_conf, 2),
                    "predicted_return": round(avg_return, 4),
                })
            except Exception as e:
                logger.error("[TRADE FAIL] BUY %s: %s", ticker, e)
                orders.append({"ticker": ticker, "side": "BUY", "notional": allocation, "error": str(e)})
        else:
            # SELL: only if we hold a position, sell 1/10th of shares (no short selling)
            qty = _get_position_qty(client, ticker)
            if qty <= 0:
                logger.info("[SKIP] SELL %s — no shares held", ticker)
                orders.append({
                    "ticker": ticker,
                    "side": "SELL",
                    "notional": 0,
                    "status": "skipped (no position)",
                    "confidence": round(avg_conf, 2),
                    "predicted_return": round(avg_return, 4),
                })
                continue
            sell_qty = max(1, round(qty / 10))  # sell 1/10th, minimum 1 share
            try:
                req = MarketOrderRequest(
                    symbol=ticker,
                    qty=sell_qty,
                    side=OrderSide.SELL,
                    time_in_force=TimeInForce.DAY,
                )
                order = client.submit_order(req)
                logger.info("[TRADE] SELL %s %d of %d shares → order %s (%s)", ticker, sell_qty, round(qty), order.id, order.status)
                orders.append({
                    "ticker": ticker,
                    "side": "SELL",
                    "qty": sell_qty,
                    "order_id": str(order.id),
                    "status": order.status,
                    "confidence": round(avg_conf, 2),
                    "predicted_return": round(avg_return, 4),
                })
            except Exception as e:
                logger.error("[TRADE FAIL] SELL %s: %s", ticker, e)
                orders.append({"ticker": ticker, "side": "SELL", "qty": round(qty), "error": str(e)})

    return orders
