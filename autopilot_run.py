#!/usr/bin/env python3
"""Autopilot entry point — daily trading, warmup, approval, and reporting.

Usage:
    python autopilot_run.py              # Daily run (after market close)
    python autopilot_run.py --approve    # Approve trading for next week
    python autopilot_run.py --report     # Show latest weekly P&L report
    python autopilot_run.py --status     # Show autopilot state summary
    python autopilot_run.py --warmup     # Pre-train all models (one-time)

Scheduling (Windows Task Scheduler):
    Action: start a program
    Program: python
    Arguments: "C:\\path\\to\\autopilot_run.py"
    Trigger: Daily at 4:30 PM (weekdays only)
"""

import argparse
import logging
import sys
from datetime import datetime, timezone

from trading.autopilot import run_daily, warmup
from trading.state import AutopilotState

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    stream=sys.stdout,
)


def cmd_daily(state: AutopilotState) -> None:
    """Daily autopilot run — after-market-close trading cycle."""
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %A")

    logging.info("=" * 55)
    logging.info("  AUTOPILOT - %s", today)
    logging.info("=" * 55)

    # Check if we should run today (skip weekends)
    if not state.is_weekday():
        logging.info("  Weekend - no trading. Exiting.")
        return

    # Check approval
    if not state.check_approval():
        # Check if we're waiting for an SMS reply
        if state.data.get("approval_pending"):
            logging.info("  Waiting for your YES/NO reply...")
            from trading.notifier import check_sms_reply
            reply = check_sms_reply()
            if reply is True:
                logging.info("  Reply: YES - approving next week.")
                state.approve_next_week()
                state.data["approval_pending"] = False
                state.save()
                # Fall through to run_daily below
            elif reply is False:
                logging.info("  Reply: NO - stopping trading.")
                state.stop_trading()
                state.data["approval_pending"] = False
                state.save()
                logging.info("")
                logging.info("  Trading stopped. Run --approve to restart.")
                return
            else:
                logging.info("  No reply yet - skipping today.")
                # Show the latest report again
                report = state.latest_weekly_report()
                if report:
                    logging.info("")
                    logging.info(state.format_weekly_report(report))
                return
        else:
            report = state.latest_weekly_report()
            if report:
                logging.info("")
                logging.info(state.format_weekly_report(report))
            logging.info("")
            logging.info("  To approve next week, run:  python autopilot_run.py --approve")
            return

    # Run the daily cycle
    result = run_daily(state)

    # Print summary
    logging.info("")
    logging.info("-" * 55)
    logging.info("  DAILY SUMMARY")
    logging.info("-" * 55)
    logging.info("  Tickers analyzed:  %d", result["tickers_analyzed"])
    logging.info("  Tickers failed:    %d", result["tickers_failed"])
    logging.info("  Buy orders:        %d", len(result["buy_orders"]))
    logging.info("  Sell orders:       %d", len(result["sell_orders"]))
    logging.info("  Skipped/failed:    %d", len(result["skipped"]))

    for o in result["buy_orders"]:
        if "error" in o:
            logging.info("  [FAIL] BUY  %s  $%s  ERROR: %s", o["ticker"], o.get("notional", "?"), o["error"])
        else:
            logging.info("  [OK]   BUY  %s  $%.0f  order=%s", o["ticker"], o["notional"], o["order_id"][:8])
    for o in result["sell_orders"]:
        if "error" in o:
            logging.info("  [FAIL] SELL %s  ERROR: %s", o["ticker"], o["error"])
        elif o.get("status") == "skipped (no position)":
            logging.info("  [SKIP] SELL %s  no position", o["ticker"])
        else:
            logging.info("  [OK]   SELL %s  %d shares  order=%s", o["ticker"], o.get("qty", "?"), o["order_id"][:8])

    if result["weekly_report"]:
        logging.info("")
        logging.info("  Weekly report saved - run --report to view")

    logging.info("")
    logging.info("=" * 55)
    logging.info("  Done.")
    logging.info("=" * 55)


def cmd_approve(state: AutopilotState) -> None:
    """Approve trading for the next week."""
    week = state.approve_next_week()
    logging.info("=" * 50)
    logging.info("  TRADING APPROVED")
    logging.info("=" * 50)
    logging.info("  Week %s is now approved for trading.", week)
    logging.info("  The autopilot will run on the next weekday.")
    logging.info("=" * 50)


def cmd_report(state: AutopilotState) -> None:
    """Display the latest weekly P&L report."""
    report = state.latest_weekly_report()
    if report is None:
        logging.info("No weekly reports yet. The autopilot needs to run through a full week first.")
        return

    formatted = state.format_weekly_report(report)
    logging.info(formatted)

    # List all historical weeks
    reports = state.data.get("weekly_reports", [])
    if len(reports) > 1:
        logging.info("")
        logging.info("  ALL WEEKS:")
        for r in reports:
            flag = "[OK]" if r.get("approved") else "[--]"
            logging.info(
                "    %s  %s -> %s   $%+10.2f (%+.2f%%)  %s",
                r["iso_week"], r["start_date"], r["end_date"],
                r.get("pnl", 0), r.get("pnl_percent", 0), flag,
            )


def cmd_status(state: AutopilotState) -> None:
    """Show current autopilot state."""
    logging.info(state.status_summary())


def cmd_stop(state: AutopilotState) -> None:
    """Immediately stop all trading until --approve is run."""
    week = state.stop_trading()
    logging.info("=" * 50)
    logging.info("  TRADING STOPPED")
    logging.info("=" * 50)
    logging.info("  All trading halted.")
    logging.info("  Run --approve to restart.")
    logging.info("=" * 50)


def cmd_warmup(state: AutopilotState) -> None:
    """Pre-train all models so daily runs are fast."""
    logging.info("=" * 55)
    logging.info("  WARMUP - pre-training models for all tickers")
    logging.info("  This only needs to run once. May take a few minutes.")
    logging.info("=" * 55)
    warmup(state)
    logging.info("=" * 55)
    logging.info("  Warmup complete. Daily runs will now be fast.")
    logging.info("=" * 55)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Advance Stock Predictor - Autopilot",
    )
    parser.add_argument("--approve", action="store_true", help="Approve trading for next week")
    parser.add_argument("--stop", action="store_true", help="Stop all trading immediately")
    parser.add_argument("--report", action="store_true", help="Show latest weekly P&L report")
    parser.add_argument("--status", action="store_true", help="Show autopilot state summary")
    parser.add_argument("--warmup", action="store_true", help="Pre-train all models (one-time)")
    args = parser.parse_args()

    state = AutopilotState()

    if args.warmup:
        cmd_warmup(state)
    elif args.approve:
        cmd_approve(state)
    elif args.stop:
        cmd_stop(state)
    elif args.report:
        cmd_report(state)
    elif args.status:
        cmd_status(state)
    else:
        cmd_daily(state)


if __name__ == "__main__":
    main()
