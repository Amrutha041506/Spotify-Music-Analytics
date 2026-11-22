"""Tests for src/data_cleaning.py (all data is SYNTHETIC - see tests/synthetic.py)."""
import unittest

import numpy as np
import pandas as pd

from src.data_cleaning import clean_dataset, validate_clean
from src.data_loader import CLEAN_COLUMNS, SchemaError
from tests.synthetic import make_raw_tracks


class TestCleaning(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = make_raw_tracks(n=600, seed=0)
        cls.clean, cls.report = clean_dataset(cls.raw)

    def row(self, track_id):
        return self.clean[self.clean["track_id"] == track_id]

    # ---- structure -------------------------------------------------------
    def test_output_columns_and_order(self):
        self.assertEqual(list(self.clean.columns), CLEAN_COLUMNS)

    def test_cleaned_data_passes_validation(self):
        self.assertEqual(validate_clean(self.clean), [])

    def test_row_accounting_adds_up(self):
        removed = sum(step["rows_removed"] for step in self.report["steps"])
        self.assertEqual(self.report["rows_raw"] - removed, self.report["rows_clean"])
        self.assertEqual(len(self.clean), self.report["rows_clean"])

    # ---- duplicates ------------------------------------------------------
    def test_exact_duplicates_removed(self):
        step = next(s for s in self.report["steps"] if s["step"] == "drop_exact_duplicates")
        self.assertEqual(step["rows_removed"], 10)

    def test_same_track_and_genre_keeps_highest_popularity(self):
        before = self.raw[self.raw["track_id"] == "id00120"]["popularity"].max()
        after = self.row("id00120")
        self.assertEqual(len(after), 1)
        self.assertEqual(int(after["popularity"].iloc[0]), int(before))

    def test_track_in_two_genres_keeps_both_rows(self):
        self.assertEqual(len(self.row("id00130")), 2)

    # ---- missing values --------------------------------------------------
    def test_missing_identifier_row_dropped(self):
        self.assertTrue(self.row("id00200").empty)

    def test_missing_core_numeric_row_dropped(self):
        self.assertTrue(self.row("id00201").empty)

    def test_missing_album_filled_and_genre_set_to_unknown(self):
        self.assertEqual(self.row("id00208")["album_name"].iloc[0], "Unknown Album")
        self.assertEqual(self.row("id00209")["track_genre"].iloc[0], "unknown")

    # ---- invalid values / outliers ---------------------------------------
    def test_out_of_range_rows_dropped(self):
        for track_id in ("id00202", "id00203", "id00204"):
            self.assertTrue(self.row(track_id).empty, track_id)

    def test_non_numeric_value_coerced_then_row_dropped(self):
        self.assertTrue(self.row("id00207").empty)
        self.assertEqual(self.report["non_numeric_values_coerced_to_missing"].get("valence"), 1)

    def test_soft_invalid_values_blanked_but_row_kept(self):
        self.assertTrue(pd.isna(self.row("id00205")["tempo"].iloc[0]))
        self.assertTrue(pd.isna(self.row("id00206")["time_signature"].iloc[0]))

    def test_long_track_is_flagged_not_removed(self):
        long_track = self.row("id00211")
        self.assertEqual(len(long_track), 1)
        self.assertEqual(int(long_track["is_duration_outlier"].iloc[0]), 1)

    # ---- transformations -------------------------------------------------
    def test_duration_minutes_conversion(self):
        np.testing.assert_allclose(self.clean["duration_min"], self.clean["duration_ms"] / 60000, atol=1e-3)

    def test_whitespace_trimmed_and_primary_artist_derived(self):
        self.assertEqual(self.row("id00210")["artists"].iloc[0], "Padded Artist")
        collab = self.clean[self.clean["artists"] == "Collab A;Collab B"]
        self.assertTrue((collab["primary_artist"] == "Collab A").all())

    def test_explicit_converted_to_zero_one(self):
        values = set(self.clean["explicit"].dropna().unique())
        self.assertTrue(values <= {0, 1})

    # ---- robustness --------------------------------------------------------
    def test_cleaning_is_idempotent(self):
        again, _ = clean_dataset(self.clean)
        self.assertEqual(len(again), len(self.clean))

    def test_missing_required_column_raises(self):
        with self.assertRaises(SchemaError):
            clean_dataset(self.raw.drop(columns=["popularity"]))

    def test_dataset_without_optional_columns_is_supported(self):
        slim = self.raw.drop(columns=["explicit", "album_name"])
        clean, report = clean_dataset(slim)
        self.assertEqual(set(report["absent_optional_columns"]), {"explicit", "album_name", "year"})
        self.assertTrue(clean["explicit"].isna().all())
        self.assertEqual(validate_clean(clean), [])


if __name__ == "__main__":
    unittest.main()
