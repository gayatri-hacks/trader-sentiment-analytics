"""Synthetic fixtures exercise reporting logic; they are never production evidence."""
from pathlib import Path
import sys
import tempfile
import unittest
import subprocess

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from reporting import analyze, quality_table, report_markdown, write_reports


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

    def test_invalid_nonfinite_overlap_and_reconciliation(self):
        pd.DataFrame([
            {"Timestamp IST": "01-05-2025 10:00", "Account": "A", "Coin": "BTC", "Side": "BUY", "Closed PnL": "inf"},
            {"Timestamp IST": "bad", "Account": "A", "Coin": "BTC", "Side": "BUY", "Closed PnL": "-inf"},
            {"Timestamp IST": "2025-05-01", "Account": "A", "Coin": "BTC", "Side": "BUY", "Closed PnL": "nan"},
        ]).to_csv(self.dir / "trades.csv", index=False)
        _, _, _, metrics = analyze(self.dir / "trades.csv", self.dir / "sentiment.csv")
        self.assertEqual(metrics["invalid_nonfinite_pnl_records"], 3)
        self.assertEqual(metrics["invalid_timestamp_records"], 2)
        self.assertEqual(metrics["excluded_invalid_records"], 3)
        self.assertEqual(metrics["source_records"], metrics["valid_records"] + metrics["excluded_invalid_records"])

    def test_exact_duplicates_and_identifier_duplicates_are_retained(self):
        rows = [
            {"Timestamp IST": "01-05-2025 10:00", "Account": "A", "Coin": "BTC", "Side": "BUY", "Closed PnL": 3, "Trade ID": "one"},
            {"Timestamp IST": "01-05-2025 10:00", "Account": "A", "Coin": "BTC", "Side": "BUY", "Closed PnL": 3, "Trade ID": "one"},
            {"Timestamp IST": "01-05-2025 11:00", "Account": "A", "Coin": "BTC", "Side": "SELL", "Closed PnL": -1, "Trade ID": "one"},
        ]
        pd.DataFrame(rows).to_csv(self.dir / "trades.csv", index=False)
        sentiment, _, _, metrics = analyze(self.dir / "trades.csv", self.dir / "sentiment.csv")
        self.assertEqual(metrics["exact_duplicate_source_records"], 2)
        self.assertEqual(metrics["duplicate_trade_id_records"], 3)
        self.assertEqual(metrics["matched_sentiment_records"], 3)
        self.assertEqual(float(sentiment.set_index("classification").loc["Fear", "total_closed_pnl_usd"]), 5)

    def test_empty_and_missing_schema_fail_clearly(self):
        (self.dir / "trades.csv").write_text("", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "empty"):
            analyze(self.dir / "trades.csv", self.dir / "sentiment.csv")
        pd.DataFrame({"Timestamp IST": ["01-05-2025 10:00"]}).to_csv(self.dir / "trades.csv", index=False)
        with self.assertRaisesRegex(ValueError, "missing required"):
            analyze(self.dir / "trades.csv", self.dir / "sentiment.csv")

    def test_unknown_side_missing_fields_and_unmatched_not_imputed(self):
        pd.DataFrame([
            {"Timestamp IST": "03-05-2025 10:00", "Account": "", "Coin": "", "Side": "", "Closed PnL": 4},
        ]).to_csv(self.dir / "trades.csv", index=False)
        _, side, _, metrics = analyze(self.dir / "trades.csv", self.dir / "sentiment.csv")
        self.assertEqual(metrics["unmatched_sentiment_records"], 1)
        self.assertEqual(metrics["missing_account_valid_records"], 1)
        self.assertEqual(metrics["missing_asset_valid_records"], 1)
        self.assertEqual(metrics["missing_side_valid_records"], 1)
        self.assertTrue(side.empty)

    def test_outputs_are_deterministic_and_csv_safe(self):
        pd.DataFrame([
            {"Timestamp IST": "01-05-2025 10:00", "Account": "A", "Coin": "BTC", "Side": "=formula", "Closed PnL": 2},
        ]).to_csv(self.dir / "trades.csv", index=False)
        first, second = self.dir / "one", self.dir / "two"
        write_reports(self.dir / "trades.csv", self.dir / "sentiment.csv", first)
        write_reports(self.dir / "trades.csv", self.dir / "sentiment.csv", second)
        self.assertEqual((first / "verification_manifest.json").read_text(), (second / "verification_manifest.json").read_text())
        self.assertIn("'=FORMULA", (first / "pnl_by_side.csv").read_text())

    def test_cli_invalid_input_has_failure_exit_code(self):
        result = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / "scripts" / "reporting.py"), "--trades", str(self.dir / "missing.csv"), "--sentiment", str(self.dir / "sentiment.csv"), "--out", str(self.dir / "out")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("does not exist", result.stderr)


class RealDatasetRegressionTests(unittest.TestCase):
    """Regression check against tracked real inputs, never synthetic fixtures."""

    def test_tracked_dataset_reconciliation_baseline(self):
        root = Path(__file__).resolve().parents[1]
        trades, sentiment = root / "historical_data (1).csv", root / "fear_greed_index.csv"
        if not trades.exists() or not sentiment.exists():
            self.skipTest("tracked real input CSVs are unavailable")
        _, _, _, metrics = analyze(trades, sentiment)
        self.assertEqual(metrics["source_records"], 211_224)
        self.assertEqual(metrics["matched_sentiment_records"], 211_218)
        self.assertEqual(metrics["unmatched_sentiment_records"], 6)
        self.assertEqual(metrics["valid_records"], metrics["matched_sentiment_records"] + metrics["unmatched_sentiment_records"])


if __name__ == "__main__":
    unittest.main()
