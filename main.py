import argparse
import logging
import sys
from collections import defaultdict

from config import (
    FEATURE_CONFIG,
    HORIZONS,
    INTERVAL,
    START_DATE,
    END_DATE,
    TICKERS,
)
from pipeline import run_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    stream=sys.stdout,
)


def _parse_list(val: str) -> list[str]:
    return [x.strip() for x in val.split(",") if x.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Advance Stock Predictor — cost-first ML pipeline"
    )
    parser.add_argument(
        "--tickers",
        type=_parse_list,
        default=None,
        help="Comma-separated tickers (default: from config)",
    )
    parser.add_argument(
        "--horizons",
        type=_parse_list,
        default=None,
        help="Comma-separated horizons in trading days (default: from config)",
    )
    parser.add_argument(
        "--models",
        type=_parse_list,
        default=None,
        help="Comma-separated model types: ridge, random_forest, xgboost (default: all)",
    )
    parser.add_argument(
        "--interval",
        default=INTERVAL,
        choices=["1d", "1wk", "1mo"],
        help="Data interval",
    )
    parser.add_argument(
        "--start",
        default=START_DATE,
        help="Start date YYYY-MM-DD",
    )
    parser.add_argument(
        "--end",
        default=END_DATE,
        help="End date YYYY-MM-DD",
    )
    parser.add_argument(
        "--force-data",
        action="store_true",
        help="Force re-fetch raw data (clear data cache)",
    )
    parser.add_argument(
        "--force-features",
        action="store_true",
        help="Force recompute features (clear feature cache)",
    )
    parser.add_argument(
        "--force-models",
        action="store_true",
        help="Force retrain models (clear model cache)",
    )
    parser.add_argument(
        "--trade",
        action="store_true",
        help="Execute paper trades via Alpaca based on predictions",
    )

    args = parser.parse_args()

    horizons: list[int] = (
        [int(h) for h in args.horizons] if args.horizons else HORIZONS
    )

    logging.info("=" * 50)
    logging.info("Advance Stock Predictor — Cost-First ML Pipeline")
    logging.info("=" * 50)

    results = run_pipeline(
        tickers=args.tickers or TICKERS,
        horizons=horizons,
        model_types=args.models,
        interval=args.interval,
        start=args.start,
        end=args.end,
        config=FEATURE_CONFIG,
        trade=args.trade,
    )

    # ── Print summary ──────────────────────────────────────────────
    agg = defaultdict(lambda: {"returns": [], "confidences": []})
    for p in results["predictions"]:
        key = (p["ticker"], p["horizon"])
        agg[key]["returns"].append(p["predicted_return"])
        agg[key]["confidences"].append(p["confidence"])

    logging.info("")
    logging.info("=" * 55)
    logging.info("  FORECAST")
    logging.info("=" * 55)
    for (ticker, horizon), v in sorted(agg.items()):
        avg_return = sum(v["returns"]) / len(v["returns"])
        avg_conf = sum(v["confidences"]) / len(v["confidences"])
        arrow = "^ UP" if avg_return > 0 else "v DOWN"
        logging.info(
            "  %s  %s  %+.2f%%  (confidence: %.2f)",
            ticker.ljust(6),
            arrow,
            avg_return * 100,
            avg_conf,
        )
    logging.info("=" * 55)

    if results["orders"]:
        logging.info("")
        logging.info("=" * 50)
        logging.info("  PAPER TRADES")
        logging.info("=" * 50)
        for o in results["orders"]:
            if "error" in o:
                logging.info("  X %s %s  FAILED: %s", o["side"], o["ticker"], o["error"])
            else:
                logging.info(
                    "  OK %s %s $%.0f  order=%s  status=%s",
                    o["side"].ljust(4),
                    o["ticker"],
                    o["notional"],
                    o["order_id"][:8],
                    o["status"],
                )

    logging.info("")
    logging.info("Done.")


if __name__ == "__main__":
    main()
