"""Tests for the dataset validator and Ollama checker (SYNTHETIC data, mocked servers)."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.config import load_config
from src.ollama_check import run_checks
from src.ollama_service import OllamaClient, OllamaSettings
from src.validate_dataset import detect_layout, profile_csv, to_markdown
from tests.synthetic import make_raw_tracks
from tests.test_ollama_service import fake_response


class TestDatasetValidator(unittest.TestCase):
    def test_profile_of_brief_style_file_and_synthetic_provenance_warning(self):
        raw = make_raw_tracks(300, seed=31)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "x.csv")
            raw.to_csv(path, index=False)
            report = profile_csv(path, load_config()["column_aliases"])
        self.assertIn("brief", report["layout"])
        self.assertEqual(report["missing_required"], [])
        self.assertEqual(report["exact_duplicate_rows"], 10)
        self.assertEqual(report["range_violations"]["energy outside 0-1"], 1)
        self.assertEqual(report["non_numeric_in_numeric_columns"], {"valence": 1})
        self.assertIn("provenance_warning", report)  # ids like 'id00001' are not Spotify-format IDs
        self.assertIn("OK to clean", to_markdown(report))

    def test_real_looking_ids_do_not_trigger_warning(self):
        raw = make_raw_tracks(50, seed=32, inject_defects=False)
        raw["track_id"] = [f"{i:022d}" for i in range(len(raw))]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "y.csv")
            raw.to_csv(path, index=False)
            self.assertNotIn("provenance_warning", profile_csv(path, load_config()["column_aliases"]))

    def test_missing_required_columns_blocks(self):
        raw = make_raw_tracks(50, inject_defects=False).drop(columns=["energy"])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "z.csv")
            raw.to_csv(path, index=False)
            report = profile_csv(path, load_config()["column_aliases"])
        self.assertTrue(report["verdict"].startswith("BLOCKED"))
        self.assertIn("UNKNOWN", detect_layout(["a", "b"]))


class TestOllamaCheck(unittest.TestCase):
    FACTS = {"dataset": {"avg_popularity": 40.0}, "top_genres_by_popularity": [{"track_genre": "pop", "avg_popularity": 55.5}],
             "settings": {"min_tracks_genre": 20}, "popularity_correlations": [], "top_artists_by_avg_popularity": []}

    def test_not_installed_and_not_running_reports_failures_and_still_proves_fallback(self):
        checks = run_checks(OllamaSettings(host="http://127.0.0.1:9"), self.FACTS, which=lambda name: None)
        status = {c["check"]: c["status"] for c in checks}
        self.assertEqual(status["ollama binary on PATH"], "FAIL")
        self.assertEqual(status["server reachable"], "FAIL")
        self.assertEqual(status["fallback when Ollama is unreachable"], "PASS")
        self.assertEqual(status["unsupported-number detection"], "PASS")

    def test_live_path_with_mocked_server_flags_invented_numbers(self):
        session = mock.Mock()
        session.get.return_value = fake_response(payload={"models": [{"name": "llama3.1:latest"}]})
        session.post.return_value = fake_response(payload={"message": {"content": "pop leads with 55.5 and 91.7 listeners"}})
        client = OllamaClient(OllamaSettings(model="llama3.1"), session=session)
        checks = run_checks(OllamaSettings(model="llama3.1"), self.FACTS, which=lambda name: None, client=client)
        live = [c for c in checks if c["check"].startswith("live answer")]
        self.assertEqual(len(live), 3)
        self.assertTrue(all("91.7" in c["detail"] for c in live))


if __name__ == "__main__":
    unittest.main()
