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
        self.assertEqual(self.client.get("/api/overview?asset=NOT_REAL").json()["valid_records"], 0)
