# API contract

`GET /health` and `GET /ready` expose liveness and data readiness. Aggregate endpoints are `/api/overview`, `/api/trends`, `/api/sentiment`, `/api/sides`, `/api/assets`, `/api/quality`, `/api/filters`, and `/api/manifest`.

Optional `start`, `end`, `asset`, `sentiment`, and `side` query parameters scope aggregate endpoints. `assets` is bounded to 100 rows. Download routes accept only an allowlist of aggregate report names; no source CSV or arbitrary filesystem path is reachable.

All win rates are record-level: winning matched, non-zero-PnL records divided by matched non-zero-PnL records. Filtered reconciliation applies to the filtered valid record population; source-file controls remain available in `/api/quality`.
