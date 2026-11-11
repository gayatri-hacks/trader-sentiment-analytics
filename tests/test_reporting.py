"""Synthetic fixtures exercise reporting logic; they are never production evidence."""
from pathlib import Path
import sys
import tempfile
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from reporting import analyze, quality_table, report_markdown


class ReportingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        pd.DataFrame([
            {"Timestamp IST": "01-05-2025 10:00:00", "Account": "A", "Coin": "BTC", "Side": "BUY", "Closed PnL": 10},
            {"Timestamp IST": "01-05-2025 11:00:00", "Account": "B", "Coin": "ETH", "Side": "SELL", "Closed PnL": -5},
            {"Timestamp IST": "02-05-2025 10:00:00", "Account": "A", "Coin": "BTC", "Side": "BUY", "Closed PnL": 0},
            {"Timestamp IST": "03-05-2025 10:00:00", "Account": "A", "Coin": "BTC", "Side": "BUY", "Closed PnL": 7},
            {"Timestamp IST": "bad", "Account": "A", "Coin": "BTC", "Side": "BUY", "Closed PnL": 8},
            {"Timestamp IST": "02-05-2025 12:00:00", "Account": "B", "Coin": "ETH", "Side": "SELL", "Closed PnL": "bad"},
        ]).to_csv(self.dir / "trades.csv", index=False)
        pd.DataFrame([
            {"date": "2025-05-01", "classification": "Fear"},
            {"date": "2025-05-02", "classification": "Greed"},
        ]).to_csv(self.dir / "sentiment.csv", index=False)

    def test_counts_denominator_and_exports(self):
        sentiment, side, detail, metrics = analyze(self.dir / "trades.csv", self.dir / "sentiment.csv")
        self.assertEqual(metrics["source_records"], 6)
        self.assertEqual(metrics["valid_records"], 4)
        self.assertEqual(metrics["matched_sentiment_records"], 3)
        self.assertEqual(metrics["nonzero_pnl_matched_records"], 2)
        self.assertEqual(metrics["zero_pnl_matched_records"], 1)
        self.assertEqual(metrics["unmatched_sentiment_records"], 1)
        fear = sentiment.set_index("classification").loc["Fear"]
        self.assertEqual(int(fear["nonzero_pnl_records"]), 2)
        self.assertAlmostEqual(fear["total_closed_pnl_usd"], 5)
        self.assertAlmostEqual(fear["win_rate_nonzero_pnl_pct"], 50)
        self.assertEqual(len(side), 2)
        self.assertEqual(len(detail), 2)
        self.assertEqual(len(quality_table(metrics)), len(metrics))
        report = report_markdown(sentiment, side, metrics)
        self.assertIn("observational", report)
        self.assertIn("cannot be assumed", report)

    def test_conflicting_sentiment_rejected(self):
        pd.DataFrame([
            {"date": "2025-05-01", "classification": "Fear"},
            {"date": "2025-05-01", "classification": "Greed"},
        ]).to_csv(self.dir / "sentiment.csv", index=False)
        with self.assertRaisesRegex(ValueError, "conflicting"):
            analyze(self.dir / "trades.csv", self.dir / "sentiment.csv")

    def test_duplicate_consistent_sentiment_allowed(self):
        pd.DataFrame([
            {"date": "2025-05-01", "classification": "Fear"},
            {"date": "2025-05-01", "classification": "Fear"},
            {"date": "2025-05-02", "classification": "Greed"},
        ]).to_csv(self.dir / "sentiment.csv", index=False)
        _, _, _, metrics = analyze(self.dir / "trades.csv", self.dir / "sentiment.csv")
        self.assertEqual(metrics["matched_sentiment_records"], 3)
        self.assertEqual(metrics["duplicate_consistent_sentiment_rows"], 1)


if __name__ == "__main__":
    unittest.main()
