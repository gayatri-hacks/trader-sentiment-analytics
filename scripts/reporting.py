"""Create an auditable, descriptive report from the repository's real CSV files.

The workflow reports historical associations only.  It neither predicts markets nor
estimates causal effects of sentiment on trading results.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

SENTIMENT_ORDER = ("Extreme Fear", "Fear", "Neutral", "Greed", "Extreme Greed")
TRADE_COLUMNS = ("Timestamp IST", "Account", "Coin", "Side", "Closed PnL")


def _parse_dates(values: pd.Series, *, dayfirst: bool) -> pd.Series:
    """Parse mixed CSV timestamp formats without silently coercing valid values."""
    return pd.to_datetime(values, format="mixed", dayfirst=dayfirst, errors="coerce").dt.normalize()


def _aggregate(frame: pd.DataFrame, group_columns: list[str], index: list[str] | None = None) -> pd.DataFrame:
    """Summarise non-zero realised PnL, preserving missing categories as N/A."""
    output_columns = group_columns + [
        "nonzero_pnl_records", "winning_records", "losing_records",
        "total_closed_pnl_usd", "mean_nonzero_pnl_usd", "median_nonzero_pnl_usd",
        "win_rate_nonzero_pnl_pct",
    ]
    if frame.empty:
        return pd.DataFrame(columns=output_columns)
    result = frame.groupby(group_columns, dropna=False)["pnl"].agg(
        nonzero_pnl_records="count",
        winning_records=lambda values: int((values > 0).sum()),
        losing_records=lambda values: int((values < 0).sum()),
        total_closed_pnl_usd="sum",
        mean_nonzero_pnl_usd="mean",
        median_nonzero_pnl_usd="median",
    )
    result["win_rate_nonzero_pnl_pct"] = 100 * result["winning_records"] / result["nonzero_pnl_records"]
    if index is not None:
        result = result.reindex(index)
    return result.reset_index()


def analyze(trades_path: Path, sentiment_path: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """Validate inputs and return sentiment, side, detailed summaries and controls."""
    raw_trades = pd.read_csv(trades_path, low_memory=False)
    missing_columns = set(TRADE_COLUMNS) - set(raw_trades.columns)
    if missing_columns:
        raise ValueError(f"Trade CSV is missing required columns: {sorted(missing_columns)}")
    trades = raw_trades.loc[:, TRADE_COLUMNS].copy()
    sentiment_source = pd.read_csv(sentiment_path, usecols=["date", "classification"])

    total = len(trades)
    trades["date"] = _parse_dates(trades["Timestamp IST"], dayfirst=True)
    trades["pnl"] = pd.to_numeric(trades["Closed PnL"], errors="coerce")
    invalid_date = int(trades["date"].isna().sum())
    invalid_pnl = int(trades["pnl"].isna().sum())
    valid = trades.loc[trades["date"].notna() & trades["pnl"].notna()].copy()

    sentiment = sentiment_source.copy()
    sentiment["date"] = _parse_dates(sentiment["date"], dayfirst=False)
    sentiment["classification"] = sentiment["classification"].astype("string").str.strip()
    invalid_sentiment = int(sentiment["date"].isna().sum() + sentiment["classification"].isna().sum())
    sentiment = sentiment.dropna(subset=["date", "classification"])
    unknown = sorted(set(sentiment["classification"]) - set(SENTIMENT_ORDER))
    if unknown:
        raise ValueError(f"Unrecognized sentiment categories: {unknown}")
    conflicting_dates = int((sentiment.groupby("date")["classification"].nunique() > 1).sum())
    if conflicting_dates:
        raise ValueError("Sentiment CSV has conflicting classifications for the same date")
    duplicate_sentiment_rows = int(sentiment.duplicated().sum())
    sentiment = sentiment.drop_duplicates(subset=["date"])

    joined = valid.merge(sentiment, how="left", on="date", validate="many_to_one")
    matched = joined.loc[joined["classification"].notna()].copy()
    nonzero = matched.loc[matched["pnl"].ne(0)].copy()
    nonzero["Side"] = nonzero["Side"].fillna("Unknown").astype(str).str.upper().str.strip()

    metrics = {
        "source_records": total,
        "exact_duplicate_source_records": int(raw_trades.duplicated().sum()),
        "invalid_timestamp_records": invalid_date,
        "invalid_pnl_records": invalid_pnl,
        "valid_records": len(valid),
        "missing_account_valid_records": int(valid["Account"].isna().sum()),
        "missing_asset_valid_records": int(valid["Coin"].isna().sum()),
        "missing_side_valid_records": int(valid["Side"].isna().sum()),
        "sentiment_source_records": len(sentiment_source),
        "invalid_sentiment_field_count": invalid_sentiment,
        "duplicate_consistent_sentiment_rows": duplicate_sentiment_rows,
        "unique_sentiment_dates": len(sentiment),
        "matched_sentiment_records": len(matched),
        "unmatched_sentiment_records": len(valid) - len(matched),
        "zero_pnl_matched_records": int(matched["pnl"].eq(0).sum()),
        "nonzero_pnl_matched_records": len(nonzero),
        "unique_accounts": int(valid["Account"].nunique(dropna=True)),
        "unique_assets": int(valid["Coin"].nunique(dropna=True)),
    }
    metrics["sentiment_coverage_pct"] = 100 * len(matched) / len(valid) if len(valid) else 0.0

    return (
        _aggregate(nonzero, ["classification"], list(SENTIMENT_ORDER)),
        _aggregate(nonzero, ["Side"]),
        _aggregate(nonzero, ["classification", "Side"]),
        metrics,
    )


def quality_table(metrics: dict) -> pd.DataFrame:
    """Return the controls as a portable two-column CSV table."""
    return pd.DataFrame({"metric": list(metrics), "value": list(metrics.values())})


def report_markdown(sentiment: pd.DataFrame, side: pd.DataFrame, metrics: dict) -> str:
    """Render an executive-readable report without inventing zeros for missing data."""
    def md_table(frame: pd.DataFrame) -> str:
        headers = list(frame.columns)
        lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
        for row in frame.itertuples(index=False, name=None):
            values = ["N/A" if pd.isna(cell) else f"{cell:,.2f}" if isinstance(cell, float) else str(cell).replace("|", "/") for cell in row]
            lines.append("| " + " | ".join(values) + " |")
        return "\n".join(lines)

    return f"""# Trading performance — descriptive executive report

## Scope and data-quality controls

- Source trade records: **{metrics['source_records']:,}**
- Exact duplicate source records (retained, not removed): **{metrics['exact_duplicate_source_records']:,}**
- Valid timestamp and PnL records: **{metrics['valid_records']:,}**
- Invalid timestamp records: **{metrics['invalid_timestamp_records']:,}**
- Invalid or missing PnL records: **{metrics['invalid_pnl_records']:,}** (may overlap timestamp failures)
- Valid records joined to sentiment by calendar date: **{metrics['matched_sentiment_records']:,}** (**{metrics['sentiment_coverage_pct']:.1f}%**)
- Valid records without a sentiment match: **{metrics['unmatched_sentiment_records']:,}**
- Matched zero-PnL records: **{metrics['zero_pnl_matched_records']:,}**; matched non-zero PnL records analysed below: **{metrics['nonzero_pnl_matched_records']:,}**
- Unique accounts / assets among valid records: **{metrics['unique_accounts']:,} / {metrics['unique_assets']:,}**
- Sentiment input rows / unique dates / consistent duplicate rows: **{metrics['sentiment_source_records']:,} / {metrics['unique_sentiment_dates']:,} / {metrics['duplicate_consistent_sentiment_rows']:,}**

## Non-zero closed-PnL records by market sentiment

{md_table(sentiment)}

## Non-zero closed-PnL records by reported transaction side

{md_table(side)}

## Interpretation and limitations

- This is **observational, retrospective analysis**, not evidence that sentiment causes profit or a validated trading strategy.
- The win-rate denominator is only matched records with non-zero `Closed PnL`; it is not an overall trade win rate.
- `Side` is a transaction-side field. BUY and SELL cannot be assumed to be long and short position directions.
- Invalid and unmatched records are counted above and excluded from sentiment aggregations; no values are imputed and exact duplicate source rows are not silently removed.
- Fees, account/position clustering, market-regime confounding, survivorship effects, and temporal leakage have not been controlled. These results are descriptive, not investment advice.
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trades", type=Path, default=Path("historical_data (1).csv"))
    parser.add_argument("--sentiment", type=Path, default=Path("fear_greed_index.csv"))
    parser.add_argument("--out", type=Path, default=Path("reports"))
    args = parser.parse_args()
    sentiment, side, detail, metrics = analyze(args.trades, args.sentiment)
    args.out.mkdir(parents=True, exist_ok=True)
    sentiment.to_csv(args.out / "pnl_by_sentiment.csv", index=False)
    side.to_csv(args.out / "pnl_by_side.csv", index=False)
    detail.to_csv(args.out / "pnl_by_sentiment_and_side.csv", index=False)
    quality_table(metrics).to_csv(args.out / "data_quality_summary.csv", index=False)
    (args.out / "executive_report.md").write_text(report_markdown(sentiment, side, metrics), encoding="utf-8")
    print(f"Report written to {args.out.resolve()}")
    print(f"Sentiment coverage: {metrics['sentiment_coverage_pct']:.1f}%")


if __name__ == "__main__":
    main()
