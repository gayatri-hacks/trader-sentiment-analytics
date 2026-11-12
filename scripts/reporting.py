"""Create deterministic, auditable descriptive reports from the supplied CSVs.

``Timestamp IST`` is interpreted as an India Standard Time local calendar
timestamp. It is not converted to UTC because the daily sentiment source does
not state its timezone; this is an explicit reconciliation convention.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

SENTIMENT_ORDER = ("Extreme Fear", "Fear", "Neutral", "Greed", "Extreme Greed")
TRADE_COLUMNS = ("Timestamp IST", "Account", "Coin", "Side", "Closed PnL")
IDENTIFIER_COLUMNS = ("Transaction Hash", "Order ID", "Trade ID")
TRADE_TIMESTAMP_FORMATS = ("%d-%m-%Y %H:%M", "%d-%m-%Y %H:%M:%S")
SENTIMENT_DATE_FORMAT = "%Y-%m-%d"


def _read_csv(path: Path, *, label: str) -> pd.DataFrame:
    try:
        frame = pd.read_csv(path, low_memory=False)
    except FileNotFoundError as exc:
        raise ValueError(f"{label} CSV does not exist: {path}") from exc
    except pd.errors.EmptyDataError as exc:
        raise ValueError(f"{label} CSV is empty or has no header: {path}") from exc
    if frame.empty:
        raise ValueError(f"{label} CSV has a header but no data rows: {path}")
    return frame


def _parse_trade_dates(values: pd.Series) -> pd.Series:
    """Accept only unambiguous day-month timestamps used by this trade export."""
    text = values.astype("string").str.strip()
    parsed = pd.Series(pd.NaT, index=values.index, dtype="datetime64[ns]")
    for fmt in TRADE_TIMESTAMP_FORMATS:
        remaining = parsed.isna() & text.notna()
        parsed.loc[remaining] = pd.to_datetime(text.loc[remaining], format=fmt, errors="coerce")
    return parsed.dt.normalize()


def _parse_sentiment_dates(values: pd.Series) -> pd.Series:
    return pd.to_datetime(values.astype("string").str.strip(), format=SENTIMENT_DATE_FORMAT, errors="coerce")


def _normalise_text(values: pd.Series) -> pd.Series:
    cleaned = values.astype("string").str.strip()
    return cleaned.mask(cleaned.eq(""))


def _aggregate(frame: pd.DataFrame, group_columns: list[str], index: list[str] | None = None) -> pd.DataFrame:
    columns = group_columns + ["nonzero_pnl_records", "winning_records", "losing_records", "total_closed_pnl_usd", "mean_nonzero_pnl_usd", "median_nonzero_pnl_usd", "win_rate_nonzero_pnl_pct"]
    if frame.empty:
        if index is not None and len(group_columns) == 1:
            return pd.DataFrame({group_columns[0]: index, **{column: pd.NA for column in columns[1:]}})
        return pd.DataFrame(columns=columns)
    result = frame.groupby(group_columns, dropna=False, sort=True)["pnl"].agg(
        nonzero_pnl_records="count", winning_records=lambda x: int((x > 0).sum()),
        losing_records=lambda x: int((x < 0).sum()), total_closed_pnl_usd="sum",
        mean_nonzero_pnl_usd="mean", median_nonzero_pnl_usd="median")
    result["win_rate_nonzero_pnl_pct"] = 100 * result["winning_records"] / result["nonzero_pnl_records"]
    if index is not None:
        result = result.reindex(index)
    return result.reset_index()


def _identifier_metrics(raw: pd.DataFrame) -> dict[str, int]:
    metrics: dict[str, int] = {}
    for column in IDENTIFIER_COLUMNS:
        if column not in raw:
            continue
        ids = _normalise_text(raw[column]).dropna()
        key = column.lower().replace(" ", "_")
        metrics[f"{key}_nonmissing_records"] = int(len(ids))
        metrics[f"duplicate_{key}_records"] = int(ids.duplicated(keep=False).sum())
        metrics[f"duplicate_{key}_values"] = int(ids.duplicated().sum())
    return metrics


def analyze(trades_path: Path, sentiment_path: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Validate and reconcile CSVs. No trade records are automatically deduplicated.

    Exact duplicate rows and repeated IDs are reported, not removed: one ID can
    legitimately refer to multiple execution events, so deleting them risks data
    loss and altered PnL semantics.
    """
    raw = _read_csv(trades_path, label="Trade")
    missing = sorted(set(TRADE_COLUMNS) - set(raw.columns))
    if missing:
        raise ValueError(f"Trade CSV is missing required columns: {missing}")
    sentiment_source = _read_csv(sentiment_path, label="Sentiment")
    missing = sorted({"date", "classification"} - set(sentiment_source.columns))
    if missing:
        raise ValueError(f"Sentiment CSV is missing required columns: {missing}")

    trades = raw.loc[:, TRADE_COLUMNS].copy()
    trades["date"] = _parse_trade_dates(trades["Timestamp IST"])
    trades["pnl"] = pd.to_numeric(trades["Closed PnL"], errors="coerce")
    invalid_timestamp = trades["date"].isna()
    finite_pnl = trades["pnl"].map(lambda x: bool(pd.notna(x) and math.isfinite(float(x))))
    invalid_pnl = ~finite_pnl
    invalid_any = invalid_timestamp | invalid_pnl
    valid = trades.loc[~invalid_any].copy()
    valid["Side"] = _normalise_text(valid["Side"]).fillna("UNKNOWN").str.upper()

    sentiment = sentiment_source.loc[:, ["date", "classification"]].copy()
    sentiment["date"] = _parse_sentiment_dates(sentiment["date"])
    sentiment["classification"] = _normalise_text(sentiment["classification"])
    invalid_sentiment = sentiment["date"].isna() | sentiment["classification"].isna()
    sentiment = sentiment.loc[~invalid_sentiment].copy()
    unknown = sorted(set(sentiment["classification"]) - set(SENTIMENT_ORDER))
    if unknown:
        raise ValueError(f"Unrecognized sentiment categories: {unknown}")
    conflicts = sentiment.groupby("date")["classification"].nunique()
    if (conflicts > 1).any():
        raise ValueError("Sentiment CSV has conflicting classifications for the same date")
    duplicate_sentiment_rows = int(sentiment.duplicated().sum())
    sentiment = sentiment.drop_duplicates(subset=["date"], keep="first").sort_values("date", kind="stable")

    joined = valid.merge(sentiment, how="left", on="date", validate="many_to_one", sort=False)
    matched = joined.loc[joined["classification"].notna()].copy()
    nonzero = matched.loc[matched["pnl"].ne(0)].copy()
    metrics: dict[str, Any] = {
        "source_records": int(len(raw)), "exact_duplicate_source_records": int(raw.duplicated(keep=False).sum()),
        "invalid_timestamp_records": int(invalid_timestamp.sum()), "invalid_nonfinite_pnl_records": int(invalid_pnl.sum()),
        "excluded_invalid_records": int(invalid_any.sum()), "valid_records": int(len(valid)),
        "missing_account_valid_records": int(_normalise_text(valid["Account"]).isna().sum()),
        "missing_asset_valid_records": int(_normalise_text(valid["Coin"]).isna().sum()),
        "missing_side_valid_records": int((valid["Side"] == "UNKNOWN").sum()),
        "sentiment_source_records": int(len(sentiment_source)), "invalid_sentiment_records": int(invalid_sentiment.sum()),
        "duplicate_consistent_sentiment_rows": duplicate_sentiment_rows, "unique_sentiment_dates": int(len(sentiment)),
        "matched_sentiment_records": int(len(matched)), "unmatched_sentiment_records": int(len(valid) - len(matched)),
        "zero_pnl_matched_records": int(matched["pnl"].eq(0).sum()), "nonzero_pnl_matched_records": int(len(nonzero)),
        "positive_pnl_matched_records": int((matched["pnl"] > 0).sum()), "negative_pnl_matched_records": int((matched["pnl"] < 0).sum()),
        "total_realised_closed_pnl_matched_usd": float(matched["pnl"].sum()),
        "mean_realised_closed_pnl_matched_usd": float(matched["pnl"].mean()) if len(matched) else None,
        "median_realised_closed_pnl_matched_usd": float(matched["pnl"].median()) if len(matched) else None,
        "unique_accounts": int(_normalise_text(valid["Account"]).nunique(dropna=True)), "unique_assets": int(_normalise_text(valid["Coin"]).nunique(dropna=True)),
    }
    metrics.update(_identifier_metrics(raw))
    metrics["sentiment_coverage_pct"] = 100 * len(matched) / len(valid) if len(valid) else 0.0
    assert metrics["source_records"] == metrics["valid_records"] + metrics["excluded_invalid_records"]
    assert metrics["valid_records"] == metrics["matched_sentiment_records"] + metrics["unmatched_sentiment_records"]
    return (_aggregate(nonzero, ["classification"], list(SENTIMENT_ORDER)), _aggregate(nonzero, ["Side"]), _aggregate(nonzero, ["classification", "Side"]), metrics)


def quality_table(metrics: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame({"metric": list(metrics), "value": list(metrics.values())})


def _safe_csv(frame: pd.DataFrame, path: Path) -> None:
    safe = frame.copy()
    for column in safe.select_dtypes(include=["object", "string"]).columns:
        values = safe[column].astype("string")
        safe[column] = values.mask(values.str.match(r"^[=+@-]", na=False), "'" + values)
    safe.to_csv(path, index=False, lineterminator="\n")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def report_markdown(sentiment: pd.DataFrame, side: pd.DataFrame, metrics: dict[str, Any]) -> str:
    def table(frame: pd.DataFrame) -> str:
        lines = ["| " + " | ".join(frame.columns) + " |", "|" + "|".join(["---"] * len(frame.columns)) + "|"]
        for row in frame.itertuples(index=False, name=None):
            lines.append("| " + " | ".join("N/A" if pd.isna(x) else f"{x:,.2f}" if isinstance(x, float) else str(x).replace("|", "/") for x in row) + " |")
        return "\n".join(lines)
    return f"""# Trading performance — descriptive executive report

## Scope and data-quality controls

- Source / valid / excluded-invalid trade records: **{metrics['source_records']:,} / {metrics['valid_records']:,} / {metrics['excluded_invalid_records']:,}**
- Invalid timestamps: **{metrics['invalid_timestamp_records']:,}**; invalid, missing, or non-finite PnL: **{metrics['invalid_nonfinite_pnl_records']:,}** (categories can overlap).
- Exact duplicate source records: **{metrics['exact_duplicate_source_records']:,}**; retained, never silently removed.
- Valid matched / unmatched sentiment records: **{metrics['matched_sentiment_records']:,} / {metrics['unmatched_sentiment_records']:,}** (**{metrics['sentiment_coverage_pct']:.3f}%**).
- Matched PnL records — positive / negative / zero / non-zero: **{metrics['positive_pnl_matched_records']:,} / {metrics['negative_pnl_matched_records']:,} / {metrics['zero_pnl_matched_records']:,} / {metrics['nonzero_pnl_matched_records']:,}**.
- Reconciliation controls: source = valid + excluded-invalid; valid = matched + unmatched.

`Timestamp IST` is matched by its stated local IST calendar date. The sentiment source is ISO date-only and declares no timezone, so no UTC conversion or missing-date imputation is performed.

## Non-zero closed-PnL records by market sentiment

{table(sentiment)}

## Non-zero closed-PnL records by reported transaction side

{table(side)}

## Interpretation and limitations

- This is observational retrospective analysis, not evidence that sentiment causes profit or a validated trading strategy.
- The win-rate denominator is matched records with non-zero `Closed PnL`; it is record-level, not a position-level or trader-level win rate.
- `Side` is a transaction-side field. BUY and SELL cannot be assumed to be long and short position directions.
- Fees are not analysed because their units, signs, and accounting relationship to `Closed PnL` are not established here.
"""


def write_reports(trades_path: Path, sentiment_path: Path, out: Path) -> dict[str, Any]:
    sentiment, side, detail, metrics = analyze(trades_path, sentiment_path)
    out.mkdir(parents=True, exist_ok=True)
    outputs = {"pnl_by_sentiment.csv": sentiment, "pnl_by_side.csv": side, "pnl_by_sentiment_and_side.csv": detail, "data_quality_summary.csv": quality_table(metrics)}
    for name, frame in outputs.items():
        _safe_csv(frame, out / name)
    (out / "executive_report.md").write_text(report_markdown(sentiment, side, metrics), encoding="utf-8", newline="\n")
    manifest = {"schema_version": 1, "inputs": [{"filename": path.name, "sha256": _sha256(path)} for path in (trades_path, sentiment_path)], "configuration": {"trade_timestamp_convention": "Timestamp IST local calendar date", "sentiment_date_format": SENTIMENT_DATE_FORMAT, "deduplication": "retain all trade rows; report duplicate signals"}, "reconciliation": metrics, "outputs": [{"filename": name, "sha256": _sha256(out / name)} for name in sorted([*outputs, "executive_report.md"])]}
    (out / "verification_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trades", type=Path, default=Path("historical_data (1).csv"))
    parser.add_argument("--sentiment", type=Path, default=Path("fear_greed_index.csv"))
    parser.add_argument("--out", type=Path, default=Path("reports"))
    args = parser.parse_args()
    try:
        metrics = write_reports(args.trades, args.sentiment, args.out)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(f"Report written to {args.out.resolve()}")
    print(f"Sentiment coverage: {metrics['sentiment_coverage_pct']:.3f}%")


if __name__ == "__main__":
    main()
