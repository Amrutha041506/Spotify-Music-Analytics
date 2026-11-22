"""Tests for schema validation, the validate_clean checker and processed-file I/O."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

from src.config import load_config
from src.data_cleaning import clean_dataset, validate_clean
from src.data_loader import (REQUIRED_COLUMNS, find_raw_file, load_processed, normalise_columns,
                             read_raw_csv, save_processed, validate_schema)
from tests.synthetic import make_raw_tracks


class TestSchemaValidation(unittest.TestCase):
    def test_valid_schema(self):
        report = validate_schema(make_raw_tracks(50, inject_defects=False))
        self.assertTrue(report["ok"])
        self.assertEqual(report["missing_required"], [])

    def test_missing_columns_detected(self):
        report = validate_schema(make_raw_tracks(50, inject_defects=False).drop(columns=["energy", "explicit"]))
        self.assertFalse(report["ok"])
        self.assertEqual(report["missing_required"], ["energy"])
        self.assertIn("explicit", report["missing_optional"])

    def test_alias_and_index_column_normalisation(self):
        df = pd.DataFrame({"Unnamed: 0": [0], "Artist_Name": ["x"], "Genre": ["pop"], "Track_Name": ["t"], "junk": [1]})
        out = normalise_columns(df, load_config()["column_aliases"])
        self.assertEqual(sorted(out.columns), ["artists", "track_genre", "track_name"])


class TestValidateClean(unittest.TestCase):
    def setUp(self):
        self.clean, _ = clean_dataset(make_raw_tracks(300, seed=5))

    def test_valid_dataset_has_no_problems(self):
        self.assertEqual(validate_clean(self.clean), [])

    def test_detects_null_in_required_column(self):
        bad = self.clean.copy()
        bad.loc[bad.index[0], "energy"] = None
        self.assertIn("null values in 'energy'", validate_clean(bad))

    def test_detects_duplicate_pairs(self):
        bad = pd.concat([self.clean, self.clean.head(1)], ignore_index=True)
        self.assertIn("duplicate (track_id, track_genre) pairs", validate_clean(bad))

    def test_detects_out_of_range_values(self):
        bad = self.clean.copy()
        bad.loc[bad.index[0], "popularity"] = 130
        bad.loc[bad.index[1], "valence"] = 2.0
        problems = validate_clean(bad)
        self.assertIn("popularity outside 0-100", problems)
        self.assertIn("'valence' outside 0-1", problems)

    def test_detects_inconsistent_duration(self):
        bad = self.clean.copy()
        bad.loc[bad.index[0], "duration_min"] = 99.0
        self.assertIn("duration_min inconsistent with duration_ms", validate_clean(bad))

    def test_detects_missing_columns(self):
        self.assertTrue(validate_clean(self.clean.drop(columns=["duration_min"]))[0].startswith("missing columns"))


class TestFilesystemHandling(unittest.TestCase):
    def test_find_raw_file_reports_download_help_when_empty(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"SPOTIFY_RAW_DIR": tmp}):
            with self.assertRaises(FileNotFoundError) as ctx:
                find_raw_file(load_config())
            self.assertIn("Download", str(ctx.exception))

    def test_find_raw_file_prefers_largest_csv(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"SPOTIFY_RAW_DIR": tmp}):
            Path(tmp, "small.csv").write_text("a\n1\n")
            Path(tmp, "big.csv").write_text("a\n" + "1\n" * 100)
            self.assertEqual(find_raw_file(load_config()).name, "big.csv")

    def test_chunked_read_equals_single_read(self):
        raw = make_raw_tracks(400, seed=2)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "t.csv")
            raw.to_csv(path, index=False)
            aliases = load_config()["column_aliases"]
            small_chunks = read_raw_csv(path, aliases, chunk_size=70)
            one_chunk = read_raw_csv(path, aliases, chunk_size=10_000)
            self.assertEqual(len(small_chunks), len(one_chunk))
            # raw dtypes can differ when one chunk holds a stray text value; the cleaned result must not
            clean_a, _ = clean_dataset(small_chunks)
            clean_b, _ = clean_dataset(one_chunk)
            pd.testing.assert_frame_equal(clean_a, clean_b)
            self.assertEqual(len(read_raw_csv(path, aliases, nrows=25)), 25)

    def test_processed_round_trip(self):
        clean, _ = clean_dataset(make_raw_tracks(200, seed=4))
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"SPOTIFY_PROCESSED_DIR": tmp}):
            outputs = save_processed(clean, load_config())
            self.assertTrue(outputs["csv"].exists())
            loaded = load_processed(load_config())
            self.assertEqual(len(loaded), len(clean))
            self.assertEqual(validate_clean(loaded), [])

    def test_load_processed_without_file_gives_helpful_error(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"SPOTIFY_PROCESSED_DIR": tmp}):
            with self.assertRaises(FileNotFoundError) as ctx:
                load_processed(load_config())
            self.assertIn("src.pipeline", str(ctx.exception))


class TestAlternativeDatasetSchema(unittest.TestCase):
    """The ~1M-track Kaggle file uses different column names and has no explicit/album columns."""

    def test_million_track_style_file_runs_through_the_pipeline(self):
        raw = make_raw_tracks(500, seed=8, inject_defects=False)
        alt = raw.rename(columns={"artists": "artist_name", "track_genre": "genre"}).drop(columns=["explicit", "album_name"])
        alt["year"] = 2015
        alt.insert(0, "Unnamed: 0", range(len(alt)))
        with tempfile.TemporaryDirectory() as tmp:
            dirs = {k: str(Path(tmp, v)) for k, v in {"SPOTIFY_RAW_DIR": "r", "SPOTIFY_PROCESSED_DIR": "p",
                                                      "SPOTIFY_REPORTS_DIR": "rep", "SPOTIFY_POWERBI_DIR": "pbi"}.items()}
            for d in dirs.values():
                Path(d).mkdir()
            alt.to_csv(Path(dirs["SPOTIFY_RAW_DIR"], "spotify_data.csv"), index=False)
            with mock.patch.dict(os.environ, dirs):
                from src.pipeline import run_pipeline
                result = run_pipeline(load_config())
            self.assertEqual(sorted(result["report"]["absent_optional_columns"]), ["album_name", "explicit"])
            self.assertFalse(result["facts"]["dataset"]["explicit_available"])
            self.assertEqual(int(pd.read_csv(Path(dirs["SPOTIFY_POWERBI_DIR"], "fact_tracks.csv"))["year"].iloc[0]), 2015)


if __name__ == "__main__":
    unittest.main()
