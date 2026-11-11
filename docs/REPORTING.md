# Reproducible reporting workflow

The executive reporting command analyses the repository's two real CSV files. It validates timestamps and realised PnL, reconciles trades to daily Fear & Greed classifications, and produces traceable CSV tables plus a Markdown summary.

```bash
python -m unittest discover -s tests -v
python scripts/reporting.py --trades "historical_data (1).csv" --sentiment fear_greed_index.csv --out reports
```

The command writes `data_quality_summary.csv`, `pnl_by_sentiment.csv`, `pnl_by_side.csv`, `pnl_by_sentiment_and_side.csv`, and `executive_report.md`. Generated reports are intentionally excluded from Git; rerun the command against the tracked inputs to reproduce them.

The workflow is descriptive. It does not establish causal effects, recommend trades, or treat BUY/SELL transaction labels as long/short exposure.
