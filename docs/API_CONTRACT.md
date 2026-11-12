# API contract

`GET /health` and `GET /ready` expose liveness and data readiness. Aggregate endpoints are `/api/overview`, `/api/trends`, `/api/sentiment`, `/api/sides`, `/api/assets`, `/api/quality`, `/api/filters`, and `/api/manifest`.

Optional `start`, `end`, `asset`, `sentiment`, and `side` query parameters scope aggregate endpoints. `assets` is bounded to 100 rows. Download routes accept only an allowlist of aggregate report names; no source CSV or arbitrary filesystem path is reachable.

Dates must be ISO `YYYY-MM-DD`, `start` must not follow `end`, and assets, sentiments, and sides must be values returned by `/api/filters`; invalid values return HTTP 422. Filters apply consistently to overview, trend, sentiment, side, and asset aggregates. `/api/quality` is deliberately full-dataset-only, while `/api/overview` identifies its counts as filtered population metrics.

Reports are explicitly full-dataset exports. Before serving one, the API compares hashes of both input CSVs with the report manifest and regenerates reports if either input changed. It never accepts a caller-controlled report path.

All win rates are record-level: winning matched, non-zero-PnL records divided by matched non-zero-PnL records. Filtered reconciliation applies to the filtered valid record population; source-file controls remain available in `/api/quality`.
