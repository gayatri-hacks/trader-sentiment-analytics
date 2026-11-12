"""API tests use real aggregate data and never expose individual records."""
import unittest

from fastapi.testclient import TestClient

from backend.main import app


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health_overview_and_real_baseline(self):
        self.assertEqual(self.client.get("/health").status_code, 200)
        payload = self.client.get("/api/overview").json()
        self.assertEqual((payload["source_records"], payload["matched_records"], payload["unmatched_records"]), (211_224, 211_218, 6))

    def test_reports_are_allowlisted_and_filters_aggregate(self):
        self.assertEqual(self.client.get("/api/reports/pnl_by_side.csv").status_code, 200)
        self.assertEqual(self.client.get("/api/reports/historical_data%20%281%29.csv").status_code, 422)
        self.assertLessEqual(len(self.client.get("/api/assets?limit=2").json()), 2)
        self.assertEqual(self.client.get("/api/overview?asset=NOT_REAL").status_code, 422)

    def test_all_aggregate_endpoints_and_filtered_invariants(self):
        base = self.client.get("/api/overview").json()
        filtered = self.client.get("/api/overview?asset=BTC&sentiment=Fear&side=BUY&start=2024-01-01&end=2024-12-31")
        self.assertEqual(filtered.status_code, 200)
        payload = filtered.json()
        self.assertLessEqual(payload["valid_records"], base["valid_records"])
        self.assertEqual(payload["valid_records"], payload["matched_records"] + payload["unmatched_records"])
        for endpoint in ("/api/trends", "/api/sentiment", "/api/sides", "/api/assets?limit=3", "/api/quality", "/api/filters", "/api/manifest"):
            self.assertEqual(self.client.get(endpoint).status_code, 200, endpoint)

    def test_invalid_filters_and_empty_population(self):
        for query in ("?start=bad", "?start=2025-01-02&end=2025-01-01", "?sentiment=Happy", "?side=HOLD", "?asset=NOPE"):
            self.assertEqual(self.client.get("/api/overview" + query).status_code, 422, query)
        response = self.client.get("/api/trends?start=2023-01-01&end=2023-01-02")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_api_is_aggregate_only_and_json_safe(self):
        import json
        for endpoint in ("/api/overview", "/api/trends", "/api/sentiment", "/api/sides", "/api/assets", "/api/quality", "/api/filters"):
            body = self.client.get(endpoint).content.decode()
            json.loads(body)
            self.assertNotIn("Account", body)
            self.assertNotIn("Transaction Hash", body)

    def test_report_manifest_is_full_dataset_and_input_bound(self):
        manifest = self.client.get("/api/manifest").json()
        self.assertEqual(manifest["reconciliation"]["source_records"], 211_224)
        self.assertEqual(len(manifest["inputs"]), 2)
        self.assertNotIn("Account", self.client.get("/api/reports/executive_report.md").text)
