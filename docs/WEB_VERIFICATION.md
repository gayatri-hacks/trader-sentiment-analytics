# Web verification

Local API integration was exercised with FastAPI's `TestClient`: health, readiness, every aggregate endpoint, the manifest, approved report download, and rejected report name. The observed real-data baseline was 211,224 source records, 211,218 matched, and 6 unmatched.

`npm run lint` and `npm run build` completed successfully. Browser interaction testing was not performed because a browser preview was not available in this environment.
