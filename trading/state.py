import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from config import STATE_FILE

logger = logging.getLogger(__name__)

WEEKLY_REPORT_TEMPLATE = """\
======================================================
  WEEKLY P&L REPORT — {iso_week}
  {date_range}
======================================================

  Starting equity:  ${start_equity:>10,.2f}
  Ending equity:    ${end_equity:>10,.2f}
  -------------------------------
  P&L:              ${pnl:>+10,.2f}  ({pnl_pct:>+7.2f}%)
  -------------------------------

  Realized P&L:     ${realized:>+10,.2f}
  Unrealized P&L:   ${unrealized:>+10,.2f}
  Trade count:      {trade_count}

  Best trade:       {best_ticker} ({best_return:>+7.2f}%)
  Worst trade:      {worst_ticker} ({worst_return:>+7.2f}%)

------------------------------------------------------

  Week {approved_text}

======================================================
"""


class AutopilotState:
    """Persistent state for the autopilot: week tracking, approvals, daily snapshots."""

    def __init__(self, path: Path = STATE_FILE):
        self.path = path
        self.data: dict = self._load()

    # ── persistence ──────────────────────────────────────────────────────

    def _load(self) -> dict:
        if self.path.exists():
            try:
                with open(self.path) as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Corrupt state file %s: %s — resetting", self.path, e)
        return {
            "current_iso_week": None,
            "week_approved": False,
            "next_week_approved": False,
            "approval_token": None,
            "last_run_date": None,
            "daily_snapshots": [],
            "weekly_reports": [],
        }

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(self.data, f, indent=2)
        tmp.replace(self.path)

    # ── week helpers ─────────────────────────────────────────────────────

    @staticmethod
    def current_iso_week() -> str:
        """Return the ISO week string for today, e.g. '2026-W23'."""
        return datetime.now(tz=timezone.utc).strftime("%Y-W%W")

    @staticmethod
    def is_weekday() -> bool:
        """True Monday–Friday."""
        return datetime.now(tz=timezone.utc).weekday() < 5

    @staticmethod
    def is_friday() -> bool:
        return datetime.now(tz=timezone.utc).weekday() == 4

    # ── approval logic ───────────────────────────────────────────────────

    def check_approval(self) -> bool:
        """Return True if we're allowed to trade this week.

        Detects week transitions and resets approval when crossing into a
        new week.
        """
        week = self.current_iso_week()
        self.data["last_run_date"] = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")

        if self.data.get("current_iso_week") != week:
            # New week — check if next_week was pre-approved
            if self.data.get("next_week_approved"):
                logger.info("[AUTOPILOT] Week %s approved (pre-approved)", week)
                self.data["current_iso_week"] = week
                self.data["week_approved"] = True
                self.data["next_week_approved"] = False
                self.save()
                return True
            else:
                logger.info(
                    "[AUTOPILOT] Week %s NOT approved. "
                    "Run `python autopilot_run.py --approve` to enable.",
                    week,
                )
                self.data["current_iso_week"] = week
                self.data["week_approved"] = False
                self.save()
                return False

        return self.data.get("week_approved", False)

    def stop_trading(self) -> str:
        """Immediately stop trading — revoke approval for current and next week."""
        self.data["week_approved"] = False
        self.data["next_week_approved"] = False
        self.data["approval_pending"] = False
        week = self.data.get("current_iso_week", "?")
        self.save()
        logger.info("[AUTOPILOT] Trading stopped. Run --approve to restart.")
        return week

    def approve_next_week(self) -> str:
        """Mark next week as approved. Returns the week string."""
        current = self.current_iso_week()
        # If we're still in the current week, switch to approved now
        if self.data.get("current_iso_week") == current:
            self.data["week_approved"] = True
            self.data["next_week_approved"] = True
            logger.info("[AUTOPILOT] Approved — continuing through %s and next week", current)
        else:
            self.data["next_week_approved"] = True
            logger.info("[AUTOPILOT] Week %s pre-approved for trading", current)

        self.data["approval_token"] = uuid.uuid4().hex[:8]
        self.save()
        return current

    # ── snapshots ────────────────────────────────────────────────────────

    def add_snapshot(self, snapshot: dict) -> None:
        """Record a daily equity/position snapshot."""
        snapshots = self.data.setdefault("daily_snapshots", [])
        # Don't double-record the same date
        date = snapshot.get("date")
        if date and any(s.get("date") == date for s in snapshots):
            # Update in place
            for s in snapshots:
                if s.get("date") == date:
                    s.update(snapshot)
                    break
        else:
            snapshots.append(snapshot)
        self.save()

    def get_week_snapshots(self, iso_week: str) -> list[dict]:
        """Return snapshots belonging to *iso_week*."""
        snapshots = self.data.get("daily_snapshots", [])
        return [s for s in snapshots if s.get("iso_week") == iso_week]

    # ── weekly reports ───────────────────────────────────────────────────

    def add_weekly_report(self, report: dict) -> None:
        reports = self.data.setdefault("weekly_reports", [])
        # Update or append
        week = report.get("iso_week")
        for i, r in enumerate(reports):
            if r.get("iso_week") == week:
                reports[i] = report
                self.save()
                return
        reports.append(report)
        self.save()

    def latest_weekly_report(self) -> Optional[dict]:
        reports = self.data.get("weekly_reports", [])
        return reports[-1] if reports else None

    def format_weekly_report(self, report: dict) -> str:
        """Return a human-readable P&L report string."""
        return WEEKLY_REPORT_TEMPLATE.format(
            iso_week=report.get("iso_week", "?"),
            date_range=f"{report.get('start_date', '?')} – {report.get('end_date', '?')}",
            start_equity=report.get("start_equity", 0),
            end_equity=report.get("end_equity", 0),
            pnl=report.get("pnl", 0),
            pnl_pct=report.get("pnl_percent", 0),
            realized=report.get("realized_pnl", 0),
            unrealized=report.get("unrealized_pnl", 0),
            trade_count=report.get("trade_count", 0),
            best_ticker=report.get("best_ticker", "-"),
            best_return=report.get("best_return", 0),
            worst_ticker=report.get("worst_ticker", "-"),
            worst_return=report.get("worst_return", 0),
            approved_text="approved [OK]" if report.get("approved") else "NOT approved - run --approve to continue",
        )

    # ── status ───────────────────────────────────────────────────────────

    def status_summary(self) -> str:
        d = self.data
        week = d.get("current_iso_week", "?")
        approved = d.get("week_approved", False)
        next_approved = d.get("next_week_approved", False)
        snapshots = d.get("daily_snapshots", [])
        last_run = d.get("last_run_date", "never")

        latest = snapshots[-1] if snapshots else {}
        equity = latest.get("equity", 0)
        cash = latest.get("cash", 0)
        pos_count = len(latest.get("positions", []))

        reports = d.get("weekly_reports", [])
        total_pnl = sum(r.get("pnl", 0) for r in reports)
        total_pnl_pct = sum(r.get("pnl_percent", 0) for r in reports)

        lines = [
            "===========================================",
            "  AUTOPILOT STATUS",
            "===========================================",
            f"  Current week:      {week}",
            f"  Approved:          {'YES' if approved else 'NO'}",
            f"  Next week pre-approved: {'YES' if next_approved else 'NO'}",
            f"  Last run:          {last_run}",
            "",
            f"  Portfolio equity:  ${equity:>10,.2f}",
            f"  Cash:              ${cash:>10,.2f}",
            f"  Open positions:    {pos_count}",
            "",
            f"  Total P&L (all weeks): ${total_pnl:>+10,.2f} ({total_pnl_pct:>+.2f}%)",
            f"  Weeks recorded:    {len(reports)}",
            "===========================================",
        ]
        return "\n".join(lines)
