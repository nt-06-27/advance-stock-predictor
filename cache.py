import hashlib
import json
import pickle
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from config import CACHE_DIRS


def make_cache_key(**components: Any) -> str:
    """Deterministic SHA256 hex digest from a set of key-value pairs."""
    canonical = json.dumps(
        {k: v for k, v in sorted(components.items()) if v is not None},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _ensure_dir(subdir: str) -> Path:
    d = CACHE_DIRS[subdir]
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── DataFrame (Parquet) ──────────────────────────────────────────────────

def load_df(subdir: str, key: str) -> Optional[pd.DataFrame]:
    p = CACHE_DIRS[subdir] / f"{key}.parquet"
    return pd.read_parquet(p) if p.exists() else None


def save_df(df: pd.DataFrame, subdir: str, key: str) -> None:
    _ensure_dir(subdir)
    p = CACHE_DIRS[subdir] / f"{key}.parquet"
    df.to_parquet(p, index=True)


# ── Model (Pickle) ───────────────────────────────────────────────────────

def load_model(key: str) -> Optional[Any]:
    p = CACHE_DIRS["models"] / f"{key}.pkl"
    if not p.exists():
        return None
    with open(p, "rb") as f:
        return pickle.load(f)


def save_model(model: Any, key: str) -> None:
    _ensure_dir("models")
    p = CACHE_DIRS["models"] / f"{key}.pkl"
    with open(p, "wb") as f:
        pickle.dump(model, f)


# ── JSON ─────────────────────────────────────────────────────────────────

def load_json(subdir: str, key: str) -> Optional[dict]:
    p = CACHE_DIRS[subdir] / f"{key}.json"
    if not p.exists():
        return None
    with open(p, "r") as f:
        return json.load(f)


def save_json(data: dict, subdir: str, key: str) -> None:
    _ensure_dir(subdir)
    p = CACHE_DIRS[subdir] / f"{key}.json"
    with open(p, "w") as f:
        json.dump(data, f, indent=2)
