# Web architecture

The React/Vite client requests only aggregate responses from FastAPI. The browser never receives the trade CSV, account IDs, transaction hashes, or individual trade records. FastAPI retains a bounded one-entry process cache and reads the tracked data through the reporting module's strict parsers and reconciliation conventions.

Run locally with `uvicorn backend.main:app --reload` and `cd frontend && npm run dev`. Vite proxies `/api` to port 8000.

`scripts/reporting.py` owns parsing, validation, date reconciliation, and the full-data report definitions. `backend/service.py` calls that canonical reconciliation and only adds validated filtering and aggregate projection; it does not duplicate financial-data logic. The client uses real FastAPI responses in the running application. Test fixtures are restricted to isolated Vitest UI tests.

This is a local full-stack application. A static-site host alone cannot run the FastAPI service, so no production deployment is claimed.
