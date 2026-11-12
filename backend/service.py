"""Cached, aggregate-only access to the reporting pipeline's reconciled inputs."""
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


def _records(trades_path: Path, sentiment_path: Path) -> Dataset:
    """Use the same strict parsers, sentiment policy, and finite PnL semantics as CLI."""
    raw = reporting._read_csv(trades_path, label="Trade")
    missing = sorted(set(reporting.TRADE_COLUMNS) - set(raw.columns))
    if missing:
        raise ValueError(f"Trade CSV is missing required columns: {missing}")
    sentiment_source = reporting._read_csv(sentiment_path, label="Sentiment")
    if {"date", "classification"} - set(sentiment_source.columns):
        raise ValueError("Sentiment CSV is missing required columns")
    trades = raw.loc[:, reporting.TRADE_COLUMNS].copy()
    trades["date"] = reporting._parse_trade_dates(trades["Timestamp IST"])
    trades["pnl"] = pd.to_numeric(trades["Closed PnL"], errors="coerce")
    finite = trades["pnl"].map(lambda x: bool(pd.notna(x) and __import__("math").isfinite(float(x))))
    valid = trades.loc[trades["date"].notna() & finite].copy()
    valid["Side"] = reporting._normalise_text(valid["Side"]).fillna("UNKNOWN").str.upper()
    sentiment = sentiment_source.loc[:, ["date", "classification"]].copy()
    sentiment["date"] = reporting._parse_sentiment_dates(sentiment["date"])
    sentiment["classification"] = reporting._normalise_text(sentiment["classification"])
    sentiment = sentiment.dropna(subset=["date", "classification"])
    if set(sentiment["classification"]) - set(reporting.SENTIMENT_ORDER):
        raise ValueError("Sentiment CSV has unrecognized classifications")
    if (sentiment.groupby("date")["classification"].nunique() > 1).any():
        raise ValueError("Sentiment CSV has conflicting classifications for the same date")
    sentiment = sentiment.drop_duplicates("date", keep="first")
    joined = valid.merge(sentiment, how="left", on="date", validate="many_to_one", sort=False)
    _, _, _, metrics = reporting.analyze(trades_path, sentiment_path)
    return Dataset(joined, metrics)


@lru_cache(maxsize=1)
def dataset() -> Dataset:
    """Process the 211K-row inputs once per process; restart invalidates this cache."""
    return _records(ROOT / "historical_data (1).csv", ROOT / "fear_greed_index.csv")


def apply_filters(frame: pd.DataFrame, start: str | None = None, end: str | None = None,
                  asset: str | None = None, sentiment: str | None = None, side: str | None = None) -> pd.DataFrame:
    filtered = frame.copy()
    if start:
        filtered = filtered[filtered["date"] >= pd.Timestamp(start)]
    if end:
        filtered = filtered[filtered["date"] <= pd.Timestamp(end)]
    if asset:
        filtered = filtered[filtered["Coin"] == asset]
    if sentiment:
        filtered = filtered[filtered["classification"] == sentiment]
    if side:
        filtered = filtered[filtered["Side"] == side.upper()]
    return filtered


def aggregate(frame: pd.DataFrame, columns: list[str]) -> list[dict]:
    eligible = frame.loc[frame["classification"].notna() & frame["pnl"].ne(0)]
    if eligible.empty:
        return []
    grouped = eligible.groupby(columns, dropna=False)["pnl"].agg(records="count", total_pnl="sum", mean_pnl="mean", median_pnl="median")
    wins = eligible.assign(win=eligible["pnl"] > 0).groupby(columns, dropna=False)["win"].sum()
    grouped["winning_records"] = wins.astype(int)
    grouped["win_rate_pct"] = 100 * grouped["winning_records"] / grouped["records"]
    return grouped.reset_index().to_dict(orient="records")
