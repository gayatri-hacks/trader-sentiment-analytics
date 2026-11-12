# Trader Sentiment Analytics

An auditable, descriptive analysis of historical Hyperliquid trade records alongside the Bitcoin Fear & Greed Index. The project turns raw operational data into data-quality controls, segmented realised-PnL KPIs, exportable summary tables, and a management-readable report.

## Business problem and objectives

Trading and operations stakeholders need a reliable way to review historical performance across market-sentiment regimes without treating patterns as trading rules. This project:

- reconciles trade timestamps to daily market-sentiment classifications;
- identifies data-quality exceptions before aggregating results;
- measures realised closed-PnL, win rates, and performance by sentiment and reported transaction side; and
- produces reproducible CSV outputs and an executive Markdown report for review and decision support.

The workflow is designed for business analysis and reporting. It does **not** predict prices, prove a causal effect of sentiment, or provide investment advice.

## Data sources and provenance

The repository tracks the two input files used by both the original notebook and the reporting command:

- `historical_data (1).csv` — supplied Hyperliquid historical trade export, with account, asset, transaction-side, timestamp, realised `Closed PnL`, fee, and transaction identifiers.
- `fear_greed_index.csv` — supplied daily Bitcoin Fear & Greed Index extract, with timestamp, numeric index value, classification, and date.

The reporting process never fabricates or imputes input values. Its exact input scope, record counts, date matching, and exclusions are exported every time it runs.

## Dataset volume and coverage

The verified full-data run processed **211,224** trade records dated 1 May 2023–1 May 2025 and 2,644 sentiment-index dates (1 February 2018–2 May 2025). It found 0 invalid timestamps, 0 invalid/missing PnL values, 0 exact duplicate trade rows, 32 accounts, and 246 assets. Calendar-date reconciliation matched 211,218 rows (99.997%); six valid trades had no matching sentiment date and were excluded from sentiment aggregates rather than imputed. Re-run the command below to regenerate these controls from the tracked inputs.

## Methodology and quality controls

1. Load the full trade CSV and retain all source records.
2. Parse `Timestamp IST` to a calendar date and coerce `Closed PnL` to numeric; disclose invalid records rather than silently filling them.
3. Validate the sentiment classifications, reject conflicting classifications for a date, and allow only consistent duplicate sentiment rows.
4. Join valid trade rows to sentiment by calendar date with a many-to-one constraint; disclose rows that do not match.
5. For matched, non-zero realised-PnL records, calculate record counts, winning/losing counts, total, mean, median, and win rate by sentiment, transaction side, and their intersection.
6. Export all results alongside a Markdown executive report that states its limitations.

An “exact duplicate” means a row duplicated across every source field; duplicates are counted and retained, not automatically deleted. The reported win rate uses only matched non-zero `Closed PnL` records, so it is not an overall trade or position win rate. `BUY` and `SELL` are reported transaction labels and must not be interpreted as long/short exposure without position-level data.

## Reproducible setup and execution

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python scripts/reporting.py --trades "historical_data (1).csv" --sentiment fear_greed_index.csv --out reports
```

The command creates:

- `reports/data_quality_summary.csv`
- `reports/pnl_by_sentiment.csv`
- `reports/pnl_by_side.csv`
- `reports/pnl_by_sentiment_and_side.csv`
- `reports/executive_report.md`
- `reports/verification_manifest.json`

`reports/` is Git-ignored so the outputs can be regenerated locally from the tracked real inputs. See [docs/REPORTING.md](docs/REPORTING.md) for the concise workflow reference. The original exploratory analysis remains available in `analysis.ipynb`.

## Trader Sentiment Intelligence dashboard

The repository also contains a local React + TypeScript dashboard and FastAPI aggregate API. It uses the same real tracked inputs and reporting conventions; raw records, accounts, and transaction IDs are never sent to the browser.

```bash
python -m pip install -r requirements.txt
uvicorn backend.main:app --reload
cd frontend && npm ci && npm run dev
```

See [web architecture](docs/WEB_ARCHITECTURE.md), the [API contract](docs/API_CONTRACT.md), and [verification notes](docs/WEB_VERIFICATION.md). This is retrospective descriptive analytics, not a prediction system or live trading product.

The reconciliation convention is explicit: `Timestamp IST` is matched by its local IST calendar date to the sentiment extract's ISO date field. The sentiment source does not declare a timezone, so no UTC conversion is assumed. Exact duplicate rows and repeated transaction IDs are audit counts and are retained—never removed automatically—because they can represent legitimate multiple events.

## Verified findings and limitations

In the verified run, 104,402 matched records had non-zero closed PnL. The largest total realised PnL segment was **Fear** ($3,357,155.44 across 29,808 records); **Extreme Greed** had the highest mean non-zero PnL ($130.21) and win rate (89.17%). By transaction label, SELL records totalled $6,589,147.64 across 68,345 non-zero records and BUY records totalled $3,665,339.31 across 36,057. These are historical descriptive associations, not recommended actions or evidence that any sentiment state or transaction side caused a result.

The generated executive report is the source of record for realised descriptive findings, because it is rerun from the actual CSVs. The analysis does not control for fees, account and position clustering, changing market regimes, selection/survivorship effects, or temporal leakage. It therefore cannot establish that a sentiment category caused a result or guarantee that any strategy will work in the future.

## Project structure

```text
analysis.ipynb                 Original exploratory notebook
scripts/reporting.py           Full-data reporting CLI
tests/test_reporting.py        Synthetic-fixture unit tests
docs/REPORTING.md              Reporting workflow documentation
.github/workflows/             Automated reporting tests
```

## License

MIT License — see `LICENSE` if present in the upstream repository.
