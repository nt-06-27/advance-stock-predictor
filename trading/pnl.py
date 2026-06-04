import logging
from datetime import datetime, timezone
from typing import Optional

from config import PNL_HISTORY_FILE
from trading.state import AutopilotState

logger = logging.getLogger(__name__)


def record_snapshot(
    state: AutopilotState,
    account: dict,
    orders: list[dict],
) -> None:
    """Record a daily P&L snapshot from Alpaca account info."""
    now = datetime.now(tz=timezone.utc)
    iso_week = now.strftime("%Y-W%W")

    positions = []
    pos_list = account.get("positions", [])
    for p in pos_list:
        positions.append({
            "ticker": p.get("symbol", "?"),
            "qty": float(p.get("qty", 0)),
            "market_value": float(p.get("market_value", 0)),
            "avg_entry_price": float(p.get("avg_entry_price", 0)),
            "unrealized_pl": float(p.get("unrealized_pl", 0)),
            "unrealized_plpc": float(p.get("unrealized_plpc", 0)),
            "current_price": float(p.get("current_price", 0)),
        })

    orders_summary = []
    for o in orders:
        if o.get("status") not in ("skipped (no position)",) and "error" not in o:
            orders_summary.append({
                "ticker": o.get("ticker", "?"),
                "side": o.get("side", "?"),
                "notional": o.get("notional", o.get("qty", 0)),
            })

    snapshot = {
        "date": now.strftime("%Y-%m-%d"),
        "iso_week": iso_week,
        "cash": float(account.get("cash", 0)),
        "portfolio_value": float(account.get("portfolio_value", 0)),
        "equity": float(account.get("equity", 0)),
        "positions": positions,
        "orders": orders_summary,
    }
    state.add_snapshot(snapshot)
    logger.info("[PNL] Snapshot %s — equity=$%.2f cash=$%.2f orders=%d",
                snapshot["date"], snapshot["equity"], snapshot["cash"], len(orders_summary))


def compute_weekly_pnl(state: AutopilotState) -> Optional[dict]:
    """Calculate P&L for the current week from daily snapshots.

    Returns a report dict and saves it to state.
    """
    now = datetime.now(tz=timezone.utc)
    iso_week = now.strftime("%Y-W%W")
    snapshots = state.get_week_snapshots(iso_week)

    if len(snapshots) < 1:
        logger.info("[PNL] Not enough data to compute weekly P&L for %s", iso_week)
        return None

    first = snapshots[0]
    last = snapshots[-1]

    start_equity = first["equity"]
    end_equity = last["equity"]
    pnl = end_equity - start_equity
    pnl_pct = (pnl / start_equity * 100) if start_equity > 0 else 0.0

    # Calculate trade-level P&L from daily snapshots
    realized_pnl = _estimate_realized_pnl(snapshots)
    unrealized_pnl = end_equity - snapshots[-1]["cash"] - (start_equity - snapshots[0]["cash"])
    daily_returns = []
    for i in range(1, len(snapshots)):
        prev = snapshots[i - 1]["equity"]
        curr = snapshots[i]["equity"]
        if prev > 0:
            daily_returns.append((curr - prev) / prev * 100)

    # Best/worst performing positions
    positions = snapshots[-1].get("positions", [])
    best_ticker = "-"
    best_return = 0.0
    worst_ticker = "-"
    worst_return = 0.0
    for p in positions:
        ret = p.get("unrealized_plpc", 0) * 100
        if ret > best_return:
            best_return = ret
            best_ticker = p["ticker"]
        if ret < worst_return:
            worst_return = ret
            worst_ticker = p["ticker"]

    trade_count = sum(len(s.get("orders", [])) for s in snapshots)

    report = {
        "iso_week": iso_week,
        "start_date": first["date"],
        "end_date": last["date"],
        "start_equity": round(start_equity, 2),
        "end_equity": round(end_equity, 2),
        "pnl": round(pnl, 2),
        "pnl_percent": round(pnl_pct, 2),
        "realized_pnl": round(realized_pnl, 2),
        "unrealized_pnl": round(unrealized_pnl, 2),
        "trade_count": trade_count,
        "best_ticker": best_ticker,
        "best_return": round(best_return, 2),
        "worst_ticker": worst_ticker,
        "worst_return": round(worst_return, 2),
        "approved": state.data.get("next_week_approved", False),
    }

    state.add_weekly_report(report)
    logger.info("[PNL] Week %s: P&L=%+.2f (%+.2f%%)", iso_week, pnl, pnl_pct)
    return report


def _estimate_realized_pnl(snapshots: list[dict]) -> float:
    """Estimate realized P&L by tracking cash changes from trades.

    Compares actual cash changes with expected (no-trade) cash.
    This is a rough estimate — precise realized P&L requires
    trade-level data from Alpaca.
    """
    if len(snapshots) < 2:
        return 0.0

    total = 0.0
    for i in range(1, len(snapshots)):
        prev = snapshots[i - 1]
        curr = snapshots[i]

        # Cash delta not explained by overnight change
        for order in curr.get("orders", []):
            if order.get("side") == "BUY":
                total -= order.get("notional", 0)
            elif order.get("side") == "SELL":
                total += order.get("notional", order.get("qty", 0))

    return total


def weekly_report_summary(report: dict) -> str:
    """Return a compact one-line summary for notification."""
    flag = "[+]" if report.get("pnl", 0) >= 0 else "[-]"
    return (
        f"{flag} Week {report['iso_week']}: "
        f"${report['pnl']:>+.2f} ({report['pnl_percent']:>+.2f}%)  "
        f"${report['start_equity']:,.0f} -> ${report['end_equity']:,.0f}  "
        f"{report['trade_count']} trades"
    )
