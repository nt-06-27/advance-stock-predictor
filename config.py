from datetime import datetime
from pathlib import Path

# ── Tickers ──────────────────────────────────────────────────────────────
TICKERS = ["AAPL", "MSFT", "GOOGL", "TSLA", "AMZN", "VOO", "SPYG"]

# ── Data ─────────────────────────────────────────────────────────────────
INTERVAL = "1d"
START_DATE = "2020-01-01"
END_DATE = datetime.now().strftime("%Y-%m-%d")

# ── Horizons (trading days forward) ──────────────────────────────────────
HORIZONS = [1, 5, 21]

# ── Feature parameters ───────────────────────────────────────────────────
FEATURE_CONFIG = {
    "ma_windows": [5, 10, 20, 50],
    "rsi_period": 14,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "volatility_window": 20,
    "lag_days": [1, 2, 3, 5],
}

# ── Model hyperparameters ────────────────────────────────────────────────
MODEL_CONFIGS = {
    "ridge": {
        "alpha": 1.0,
    },
    "random_forest": {
        "n_estimators": 200,
        "max_depth": 10,
        "min_samples_leaf": 5,
        "random_state": 42,
        "n_jobs": -1,
    },
    "xgboost": {
        "n_estimators": 200,
        "max_depth": 6,
        "learning_rate": 0.05,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "random_state": 42,
    },
}

# ── Model escalation threshold ───────────────────────────────────────────
# Only train XGBoost if RF improves RMSE by at least this much over Ridge
ESCALATION_THRESHOLD = 0.10

# ── Alpaca ───────────────────────────────────────────────────────────────
ALPACA_PAPER_URL = "https://paper-api.alpaca.markets"
ALPACA_DATA_URL = "https://data.alpaca.markets"
TRADE_ALLOCATION = 1000     # dollars per trade
MIN_CONFIDENCE = 0.5        # minimum confidence to place a trade

# ── News ─────────────────────────────────────────────────────────────────
MAX_NEWS_ARTICLES = 10          # max articles per ticker per fetch
NEWS_SENTIMENT_WINDOW = 7       # days to look back for sentiment features

# ── Fundamentals ─────────────────────────────────────────────────────────
FUNDAMENTALS_CACHE_DAYS = 30    # min days before refetching fundamentals

# ── Cache ────────────────────────────────────────────────────────────────
CACHE_ROOT = Path("cache")
DATASET_VERSION = "1.0"
RANDOM_SEED = 42

# ── Derived cache paths ──────────────────────────────────────────────────
CACHE_DIRS = {
    "data": CACHE_ROOT / "data",
    "features": CACHE_ROOT / "features",
    "datasets": CACHE_ROOT / "datasets",
    "models": CACHE_ROOT / "models",
    "predictions": CACHE_ROOT / "predictions",
    "evals": CACHE_ROOT / "evals",
    "news": CACHE_ROOT / "news",
    "fundamentals": CACHE_ROOT / "fundamentals",
}
