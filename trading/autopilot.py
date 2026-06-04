import logging
import os
from collections import defaultdict
from typing import Optional

from dotenv import load_dotenv

from config import (
    AUTOPILOT_TICKERS,
    END_DATE,
    FEATURE_CONFIG,
    HORIZONS,
    INTERVAL,
    MAX_POSITIONS,
    MIN_CONFIDENCE,
    MIN_SIGNAL_STRENGTH,
    PER_TRADE_FRACTION,
    START_DATE,
    TRADE_ALLOCATION,
)
from trading.pnl import compute_weekly_pnl, record_snapshot
from trading.state import AutopilotState

load_dotenv()
logger = logging.getLogger(__name__)

# ── Horizon weights for multi-timeframe ensembling ──────────────────────
# Short-term (1d) 20%, medium-term (5d) 50%, long-term (21d) 30%
HORIZON_WEIGHTS = {"1d": 0.2, "5d": 0.5, "21d": 0.3}
AVAILABLE_MODELS = ["ridge", "random_forest", "xgboost"]


# ── Alpaca helpers ──────────────────────────────────────────────────────

def _get_client():
    from alpaca.trading.client import TradingClient

    api_key = os.getenv("APCA_API_KEY_ID")
    secret = os.getenv("APCA_SECRET_KEY")
    if not api_key or not secret:
        logger.error("Alpaca API keys not set")
        return None
    return TradingClient(api_key, secret, paper=True)


def get_account_info() -> Optional[dict]:
    """Return full account info including positions list."""
    client = _get_client()
    if client is None:
        return None
    try:
        account = client.get_account()
        positions_raw = client.get_all_positions()
        positions = []
        for p in positions_raw:
            positions.append({
                "symbol": p.symbol,
                "qty": p.qty,
                "market_value": p.market_value,
                "avg_entry_price": p.avg_entry_price,
                "unrealized_pl": p.unrealized_pl,
                "unrealized_plpc": p.unrealized_plpc,
                "current_price": p.current_price,
            })

        return {
            "cash": float(account.cash),
            "portfolio_value": float(account.portfolio_value),
            "buying_power": float(account.buying_power),
            "equity": float(account.equity),
            "positions": positions,
        }
    except Exception as e:
        logger.error("Failed to get account info: %s", e)
        return None


def get_position_qty(ticker: str) -> float:
    """Return shares held, or 0."""
    client = _get_client()
    if client is None:
        return 0.0
    try:
        pos = client.get_open_position(ticker)
        return float(pos.qty)
    except Exception:
        return 0.0


# ── Prediction helpers ──────────────────────────────────────────────────

def _get_ensemble_prediction(ticker: str) -> Optional[dict]:
    """Run all models × horizons for *ticker* and return ensemble signal.

    Returns:
        {
            "ticker": ...,
            "predicted_return": weighted_avg,
            "confidence": weighted_confidence,
            "signal_strength": weighted_avg * weighted_confidence,
            "horizon_details": {h: {model: {...}, "ensemble": {...}}},
        }
    """
    from predict.predictor import predict

    returns = []
    confidences = []
    details = {}

    for horizon in HORIZONS:
        h_key = f"{horizon}d"
        h_returns = []
        h_confs = []
        model_details = {}

        for model_type in AVAILABLE_MODELS:
            try:
                result = predict(ticker, model_type, horizon)
                r = result["predicted_return"]
                c = result["confidence"]
                model_details[model_type] = {"predicted_return": r, "confidence": c}
                h_returns.append(r)
                h_confs.append(c)
            except Exception as e:
                logger.debug("[AUTOPILOT] %s %s h=%d failed: %s", ticker, model_type, horizon, e)

        if h_returns:
            avg_r = sum(h_returns) / len(h_returns)
            avg_c = sum(h_confs) / len(h_confs)
            weight = HORIZON_WEIGHTS.get(h_key, 1.0 / len(HORIZONS))
            returns.append(avg_r * weight)
            confidences.append(avg_c)
            details[h_key] = {
                "models": model_details,
                "ensemble": {"predicted_return": round(avg_r, 4), "confidence": round(avg_c, 4)},
            }

    if not returns:
        return None

    total_return = sum(returns)
    total_confidence = sum(confidences) / len(confidences) if confidences else 0
    total_confidence = min(total_confidence, 1.0)

    return {
        "ticker": ticker,
        "predicted_return": round(total_return, 4),
        "confidence": round(total_confidence, 4),
        "signal_strength": round(total_return * total_confidence, 6),
        "horizon_details": details,
    }


def _run_ticker_pipeline(ticker: str) -> None:
    """Ensure data, news, and fundamentals are fetched for *ticker*."""
    from data.fetcher import fetch_data
    from features.engineer import compute_features

    try:
        fetch_data(ticker, INTERVAL, START_DATE, END_DATE)
    except Exception as e:
        logger.warning("[AUTOPILOT] Data fetch failed for %s: %s", ticker, e)

    try:
        from news.fetcher import fetch_news
        fetch_news(ticker)
    except Exception as e:
        logger.warning("[AUTOPILOT] News fetch failed for %s: %s", ticker, e)

    try:
        from fundamentals.fetcher import fetch_fundamentals
        fetch_fundamentals(ticker)
    except Exception as e:
        logger.warning("[AUTOPILOT] Fundamentals fetch failed for %s: %s", ticker, e)

    # Pre-compute features (caches them for later)
    try:
        compute_features(ticker, INTERVAL, START_DATE, END_DATE, FEATURE_CONFIG)
    except Exception as e:
        logger.warning("[AUTOPILOT] Feature computation failed for %s: %s", ticker, e)


# ── Trade execution ─────────────────────────────────────────────────────

def _calculate_position_sizing(
    account: dict,
    buy_candidates: list[dict],
) -> list[dict]:
    """Allocate cash across buy candidates.

    Each candidate gets a fraction of available cash proportional to
    its signal strength relative to the total.
    """
    cash = float(account.get("cash", 0))
    current_positions = len(account.get("positions", []))
    available_slots = max(0, MAX_POSITIONS - current_positions)

    if available_slots <= 0 or cash <= 0 or not buy_candidates:
        return []

    # Take top N by signal_strength
    candidates = sorted(buy_candidates, key=lambda x: x["signal_strength"], reverse=True)
    candidates = candidates[:available_slots]

    total_signal = sum(abs(c["signal_strength"]) for c in candidates) or 1.0

    allocations = []
    for c in candidates:
        signal_share = abs(c["signal_strength"]) / total_signal
        trade_cash = max(
            TRADE_ALLOCATION,
            round(cash * PER_TRADE_FRACTION * signal_share, 2),
        )
        trade_cash = min(trade_cash, cash / available_slots)  # Don't exceed fair share

        allocations.append({
            "ticker": c["ticker"],
            "notional": round(trade_cash, 2),
            "predicted_return": c["predicted_return"],
            "confidence": c["confidence"],
            "signal_strength": c["signal_strength"],
        })

    return allocations


def _execute_buy(ticker: str, notional: float, confidence: float, predicted_return: float) -> dict:
    """Submit a buy market order."""
    from alpaca.trading.enums import OrderSide, TimeInForce
    from alpaca.trading.requests import MarketOrderRequest

    client = _get_client()
    if client is None:
        return {"ticker": ticker, "side": "BUY", "notional": notional, "error": "no client"}

    try:
        req = MarketOrderRequest(
            symbol=ticker,
            notional=notional,
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY,
        )
        order = client.submit_order(req)
        logger.info("[TRADE] BUY %s $%.2f → %s (%s)", ticker, notional, order.id, order.status)
        return {
            "ticker": ticker,
            "side": "BUY",
            "notional": notional,
            "order_id": str(order.id),
            "status": order.status,
            "confidence": round(confidence, 2),
            "predicted_return": round(predicted_return, 4),
        }
    except Exception as e:
        logger.error("[TRADE FAIL] BUY %s: %s", ticker, e)
        return {"ticker": ticker, "side": "BUY", "notional": notional, "error": str(e)}


def _execute_sell(ticker: str, confidence: float, predicted_return: float) -> dict:
    """Sell 1/10th of current position (min 1 share)."""
    from alpaca.trading.enums import OrderSide, TimeInForce
    from alpaca.trading.requests import MarketOrderRequest

    client = _get_client()
    if client is None:
        return {"ticker": ticker, "side": "SELL", "error": "no client"}

    qty = get_position_qty(ticker)
    if qty <= 0:
        logger.info("[SKIP] SELL %s - no shares held", ticker)
        return {
            "ticker": ticker, "side": "SELL", "status": "skipped (no position)",
            "confidence": round(confidence, 2), "predicted_return": round(predicted_return, 4),
        }

    sell_qty = max(1, round(qty / 10))
    try:
        req = MarketOrderRequest(
            symbol=ticker,
            qty=sell_qty,
            side=OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
        )
        order = client.submit_order(req)
        logger.info("[TRADE] SELL %s %d of %d shares → %s (%s)", ticker, sell_qty, round(qty), order.id, order.status)
        return {
            "ticker": ticker,
            "side": "SELL",
            "qty": sell_qty,
            "order_id": str(order.id),
            "status": order.status,
            "confidence": round(confidence, 2),
            "predicted_return": round(predicted_return, 4),
        }
    except Exception as e:
        logger.error("[TRADE FAIL] SELL %s: %s", ticker, e)
        return {"ticker": ticker, "side": "SELL", "qty": round(qty), "error": str(e)}


# ── Core autopilot ──────────────────────────────────────────────────────

def run_daily(state: AutopilotState) -> dict:
    """Execute one daily autopilot cycle.

    Returns a summary dict with predictions, orders, and weekly report (if Friday).
    """
    result = {
        "date": state.data.get("last_run_date"),
        "week": state.data.get("current_iso_week"),
        "tickers_analyzed": 0,
        "tickers_failed": 0,
        "buy_orders": [],
        "sell_orders": [],
        "skipped": [],
        "weekly_report": None,
    }

    # 1. Account info
    account = get_account_info()
    if account is None:
        logger.error("[AUTOPILOT] Cannot get account info - aborting")
        return result

    held_tickers = {p["symbol"] for p in account.get("positions", [])}
    logger.info("[AUTOPILOT] Account: $%.2f cash, $%.2f equity, %d positions",
                account["cash"], account["equity"], len(held_tickers))

    # 2. Run predictions across universe
    all_signals = []
    universe = list(set(AUTOPILOT_TICKERS) | held_tickers)  # Include held tickers not in universe

    for ticker in universe:
        try:
            # Ensure base data is ready
            _run_ticker_pipeline(ticker)
            result["tickers_analyzed"] += 1

            # Get ensemble prediction
            signal = _get_ensemble_prediction(ticker)
            if signal is None:
                logger.info("[AUTOPILOT] No prediction for %s", ticker)
                result["tickers_failed"] += 1
                continue

            logger.info(
                "[AUTOPILOT] %s → return=%+.4f conf=%.2f strength=%.6f",
                ticker, signal["predicted_return"], signal["confidence"], signal["signal_strength"],
            )
            all_signals.append(signal)

        except Exception as e:
            logger.warning("[AUTOPILOT] %s failed: %s", ticker, e)
            result["tickers_failed"] += 1

    if not all_signals:
        logger.warning("[AUTOPILOT] No predictions generated for any ticker")
        record_snapshot(state, account, [])
        return result

    # 3. Rank: separate buys and sells
    buy_signals = [
        s for s in all_signals
        if s["signal_strength"] >= MIN_SIGNAL_STRENGTH
        and s["confidence"] >= MIN_CONFIDENCE
    ]
    sell_signals = [
        s for s in all_signals
        if s["signal_strength"] < 0
        and s["confidence"] >= MIN_CONFIDENCE
        and s["ticker"] in held_tickers
    ]

    buy_signals.sort(key=lambda x: x["signal_strength"], reverse=True)
    sell_signals.sort(key=lambda x: x["signal_strength"])  # most negative first

    logger.info("[AUTOPILOT] Buy candidates: %d, Sell candidates: %d", len(buy_signals), len(sell_signals))

    # 4. Execute sells (before buys, to free up cash)
    orders = []
    for sig in sell_signals:
        order = _execute_sell(sig["ticker"], sig["confidence"], sig["predicted_return"])
        orders.append(order)
        result["sell_orders"].append(order)
        if order.get("error"):
            result["skipped"].append(order)

    # 5. Allocate buys
    buy_allocations = _calculate_position_sizing(account, buy_signals)
    for alloc in buy_allocations:
        # Re-check cash (sells may have freed some up, but we have latest account info)
        order = _execute_buy(alloc["ticker"], alloc["notional"], alloc["confidence"], alloc["predicted_return"])
        orders.append(order)
        result["buy_orders"].append(order)
        if order.get("error"):
            result["skipped"].append(order)

    # 6. Record daily snapshot (re-fetch account to get updated state)
    updated_account = get_account_info() or account
    record_snapshot(state, updated_account, orders)

    # 7. Weekly closeout on Friday
    if state.is_friday():
        logger.info("[AUTOPILOT] Friday - computing weekly P&L")
        report = compute_weekly_pnl(state)
        if report:
            result["weekly_report"] = report
            formatted = state.format_weekly_report(report)

            # Send SMS asking YES/NO for next week
            try:
                from trading.notifier import send_weekly_report
                send_weekly_report(report, formatted)
            except Exception:
                pass

            # Mark next week as pending (not yet approved)
            state.data["approval_pending"] = True
            state.data["next_week_approved"] = False
            state.save()

            logger.info("\n%s", formatted)
            logger.info("[AUTOPILOT] SMS sent - waiting for YES/NO reply")

    return result


def warmup(state: AutopilotState, tickers: Optional[list[str]] = None) -> None:
    """Pre-train models for all tickers so daily runs are fast."""
    tickers = tickers or AUTOPILOT_TICKERS
    logger.info("[WARMUP] Pre-training models for %d tickers...", len(tickers))

    for i, ticker in enumerate(tickers):
        logger.info("[WARMUP] %d/%d %s", i + 1, len(tickers), ticker)
        try:
            _run_ticker_pipeline(ticker)
            signal = _get_ensemble_prediction(ticker)
            if signal:
                logger.info("[WARMUP] %s -> return=%+.4f conf=%.2f",
                            ticker, signal["predicted_return"], signal["confidence"])
            else:
                logger.warning("[WARMUP] %s - no prediction", ticker)
        except Exception as e:
            logger.warning("[WARMUP] %s failed: %s", ticker, e)

    logger.info("[WARMUP] Done. %d tickers processed.", len(tickers))
