"""Aggregate-only access to the canonical reporting reconciliation."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import reporting  # noqa: E402


@dataclass(frozen=True)
class Dataset:
    records: pd.DataFrame
    metrics: dict


@lru_cache(maxsize=1)
def dataset() -> Dataset:
    """Cache one canonical, validated reconciliation per process."""
    reconciled = reporting.reconcile(ROOT / "historical_data (1).csv", ROOT / "fear_greed_index.csv")
    return Dataset(reconciled.records, reconciled.metrics)


def clear_dataset_cache() -> None:
    dataset.cache_clear()


def validate_filters(start: str | None = None, end: str | None = None, asset: str | None = None,
                     sentiment: str | None = None, side: str | None = None) -> dict[str, str | None]:
    frame = dataset().records
    try:
        parsed_start = pd.Timestamp(start).normalize() if start else None
        parsed_end = pd.Timestamp(end).normalize() if end else None
    except (TypeError, ValueError) as exc:
        raise ValueError("dates must use ISO YYYY-MM-DD") from exc
    if parsed_start is not None and parsed_end is not None and parsed_start > parsed_end:
        raise ValueError("start must be on or before end")
    if asset and asset not in set(frame["Coin"].dropna()):
        raise ValueError("unknown asset")
    if sentiment and sentiment not in reporting.SENTIMENT_ORDER:
        raise ValueError("unknown sentiment classification")
    if side and side.upper() not in set(frame["Side"].dropna()):
        raise ValueError("unknown transaction side")
    return {"start": parsed_start.isoformat() if parsed_start is not None else None,
            "end": parsed_end.isoformat() if parsed_end is not None else None,
            "asset": asset, "sentiment": sentiment, "side": side.upper() if side else None}


def apply_filters(frame: pd.DataFrame, **filters: str | None) -> pd.DataFrame:
    filtered = frame
    if filters.get("start"):
        filtered = filtered[filtered["date"] >= pd.Timestamp(filters["start"])]
    if filters.get("end"):
        filtered = filtered[filtered["date"] <= pd.Timestamp(filters["end"])]
    if filters.get("asset"):
        filtered = filtered[filtered["Coin"] == filters["asset"]]
    if filters.get("sentiment"):
        filtered = filtered[filtered["classification"] == filters["sentiment"]]
    if filters.get("side"):
        filtered = filtered[filtered["Side"] == filters["side"]]
    return filtered.copy()


def aggregate(frame: pd.DataFrame, columns: list[str]) -> list[dict]:
    eligible = frame.loc[frame["classification"].notna() & frame["pnl"].ne(0)]
    if eligible.empty:
        return []
    grouped = eligible.groupby(columns, dropna=False)["pnl"].agg(records="count", total_pnl="sum", mean_pnl="mean", median_pnl="median")
    grouped["winning_records"] = eligible.assign(win=eligible["pnl"] > 0).groupby(columns, dropna=False)["win"].sum().astype(int)
    grouped["win_rate_pct"] = 100 * grouped["winning_records"] / grouped["records"]
    return grouped.reset_index().to_dict(orient="records")
