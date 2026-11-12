# Reproducible reporting workflow

The executive reporting command analyses the repository's two real CSV files. It validates timestamps and realised PnL, reconciles trades to daily Fear & Greed classifications, and produces traceable CSV tables plus a Markdown summary.

```bash
python -m unittest discover -s tests -v
python scripts/reporting.py --trades "historical_data (1).csv" --sentiment fear_greed_index.csv --out reports
```

The command writes `data_quality_summary.csv`, `pnl_by_sentiment.csv`, `pnl_by_side.csv`, `pnl_by_sentiment_and_side.csv`, `executive_report.md`, and `verification_manifest.json`. The manifest records input/output SHA-256 hashes, configuration, and reconciliation controls, without nondeterministic timestamps.

## Validation and reconciliation policy

- Required trade fields are `Timestamp IST`, `Account`, `Coin`, `Side`, and `Closed PnL`; the sentiment fields are `date` and `classification`. Empty files and missing fields fail the command with exit code 2.
- Trade timestamps accept only `DD-MM-YYYY HH:MM[:SS]`. Since the source explicitly calls the field `Timestamp IST`, its local IST calendar date is used. Sentiment dates accept only ISO `YYYY-MM-DD`. The supplied sentiment extract does not declare a timezone, so the process does not convert it to UTC or silently infer one.
- A valid trade has both a valid timestamp and a finite numeric PnL. Invalid timestamp and PnL counts may overlap; `excluded_invalid_records` is their union, so `source = valid + excluded` always holds. Likewise, `valid = matched + unmatched`.
- Daily sentiment may have an identical duplicate row, which is retained as a quality count and collapsed for the many-to-one join. Conflicting classifications for one date, unknown classifications, and invalid sentiment rows are reported or rejected; missing sentiment dates are never imputed.
- No trade records are deduplicated. Exact duplicate source rows and repeated transaction hash/order/trade IDs are audit signals only, because an identifier can legitimately cover multiple execution events. They remain in descriptive PnL calculations.
- PnL is parsed as a finite IEEE-754 numeric value, preserving the source's existing numeric semantics. Positive, negative, and zero values are all retained; grouped KPIs use matched non-zero records only and explicitly label their record-level denominator.

Exports neutralize spreadsheet formula prefixes in textual values. Account identifiers are only counted, never exported in reporting tables or logs. Generated reports are intentionally excluded from Git; rerun the command against the tracked inputs to reproduce them.

The workflow is descriptive. It does not establish causal effects, recommend trades, or treat BUY/SELL transaction labels as long/short exposure.
