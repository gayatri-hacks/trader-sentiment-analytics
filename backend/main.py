"""Aggregate-only FastAPI interface for the real-data reporting pipeline."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel

from .service import ROOT, aggregate, apply_filters, dataset, validate_filters

app = FastAPI(title="Trader Sentiment Intelligence", version="1.0.0")
REPORTS = {"pnl_by_sentiment.csv", "pnl_by_side.csv", "pnl_by_sentiment_and_side.csv", "data_quality_summary.csv", "executive_report.md"}


class Overview(BaseModel):
    source_records: int
    valid_records: int
    matched_records: int
    unmatched_records: int
    reconciliation_pct: float
    total_realised_closed_pnl_usd: float
    nonzero_pnl_records: int
    win_rate_definition: str


def filtered(start: str | None = None, end: str | None = None, asset: str | None = None,
             sentiment: str | None = None, side: str | None = None):
    try:
        return apply_filters(dataset().records, **validate_filters(start, end, asset, sentiment, side))
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, f"Invalid filter: {exc}") from exc


@app.get("/health")
def health(): return {"status": "ok"}


@app.get("/ready")
def ready():
    try:
        return {"ready": True, "cached_records": len(dataset().records)}
    except Exception as exc:
        raise HTTPException(503, "Reporting data is unavailable") from exc


@app.get("/api/overview", response_model=Overview)
def overview(start: str | None = None, end: str | None = None, asset: str | None = None, sentiment: str | None = None, side: str | None = None):
    d, frame = dataset(), filtered(start, end, asset, sentiment, side)
    matched = frame[frame["classification"].notna()]
    nonzero = matched[matched["pnl"].ne(0)]
    return Overview(source_records=d.metrics["source_records"], valid_records=len(frame), matched_records=len(matched), unmatched_records=len(frame)-len(matched), reconciliation_pct=100*len(matched)/len(frame) if len(frame) else 0, total_realised_closed_pnl_usd=float(matched.pnl.sum()), nonzero_pnl_records=len(nonzero), win_rate_definition="winning matched records / matched non-zero-PnL records")


@app.get("/api/trends")
def trends(start: str | None = None, end: str | None = None, asset: str | None = None, sentiment: str | None = None, side: str | None = None):
    frame = filtered(start, end, asset, sentiment, side)
    matched = frame[frame["classification"].notna()]
    return aggregate(matched.assign(month=matched.date.dt.strftime("%Y-%m")), ["month"])


@app.get("/api/sentiment")
def sentiment(start: str | None = None, end: str | None = None, asset: str | None = None, sentiment: str | None = None, side: str | None = None): return aggregate(filtered(start, end, asset, sentiment, side), ["classification"])


@app.get("/api/sides")
def sides(start: str | None = None, end: str | None = None, asset: str | None = None, sentiment: str | None = None, side: str | None = None): return aggregate(filtered(start, end, asset, sentiment, side), ["Side"])


@app.get("/api/assets")
def assets(limit: int = Query(25, ge=1, le=100), start: str | None = None, end: str | None = None, asset: str | None = None, sentiment: str | None = None, side: str | None = None):
    return sorted(aggregate(filtered(start, end, asset, sentiment, side), ["Coin"]), key=lambda x: abs(x["total_pnl"]), reverse=True)[:limit]


@app.get("/api/quality")
def quality(): return dataset().metrics


@app.get("/api/filters")
def filters():
    frame = dataset().records
    return {"assets": sorted(frame.Coin.dropna().unique().tolist()), "sentiments": [x for x in ["Extreme Fear", "Fear", "Neutral", "Greed", "Extreme Greed"] if x in set(frame.classification.dropna())], "sides": sorted(frame.Side.dropna().unique().tolist()), "date_min": frame.date.min().date().isoformat(), "date_max": frame.date.max().date().isoformat()}


@app.get("/api/reports/{approved_report_name}")
def report(approved_report_name: Literal["pnl_by_sentiment.csv", "pnl_by_side.csv", "pnl_by_sentiment_and_side.csv", "data_quality_summary.csv", "executive_report.md"]):
    report_dir = ROOT / "reports-api"
    from .service import reporting
    manifest_path = report_dir / "verification_manifest.json"
    current_inputs = [{"filename": path.name, "sha256": reporting._sha256(path)} for path in (ROOT / "historical_data (1).csv", ROOT / "fear_greed_index.csv")]
    stale = not manifest_path.exists()
    if not stale:
        try:
            stale = json.loads(manifest_path.read_text())["inputs"] != current_inputs
        except (ValueError, KeyError):
            stale = True
    if stale:
        reporting.write_reports(ROOT / "historical_data (1).csv", ROOT / "fear_greed_index.csv", report_dir)
    path = report_dir / approved_report_name
    return FileResponse(path, filename=approved_report_name) if path.suffix == ".csv" else PlainTextResponse(path.read_text())


@app.get("/api/manifest")
def manifest():
    report("data_quality_summary.csv")
    return json.loads((ROOT / "reports-api" / "verification_manifest.json").read_text())
