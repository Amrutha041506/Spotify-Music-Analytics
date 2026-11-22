"""Static consistency checks between the Power BI assets and the CSVs the exporter really produces.

These do NOT replace opening the report in Power BI Desktop; they catch typos and drift
(a DAX column or Power Query column that does not exist in the exported tables).
"""
import json
import re
import unittest
from pathlib import Path

from src.data_cleaning import clean_dataset
from src.powerbi_export import build_powerbi_tables
from tests.synthetic import make_raw_tracks

PBI = Path(__file__).resolve().parents[1] / "dashboard" / "powerbi"


class TestPowerBiAssets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        clean, _ = clean_dataset(make_raw_tracks(400, seed=41))
        cls.tables = build_powerbi_tables(clean)
        cls.columns = {name: set(df.columns) for name, df in cls.tables.items()}
        cls.dax = (PBI / "dax_measures.md").read_text(encoding="utf-8")
        cls.model = (PBI / "data_model.md").read_text(encoding="utf-8")
        cls.mcode = (PBI / "load_data.pq").read_text(encoding="utf-8")

    def test_every_table_column_reference_in_dax_exists(self):
        refs = set(re.findall(r"\b(fact_tracks|dim_genre|dim_artist|dim_popularity_band|feature_correlation)\[(\w+)\]", self.dax))
        self.assertGreater(len(refs), 10)
        missing = [(t, c) for t, c in refs if c not in self.columns[t]]
        self.assertEqual(missing, [])

    def test_measure_references_resolve(self):
        code = "\n".join(re.findall(r"```dax\n(.*?)```", self.dax, re.S))
        defined = set(re.findall(r"^([A-Za-z][\w ()%]*?)\s*=", code, re.M))
        used = set(re.findall(r"(?<![\w\]])\[([A-Za-z][\w ()%]*)\]", code))
        self.assertEqual(sorted(used - defined), [])

    def test_dax_parentheses_and_vars_are_balanced(self):
        for block in re.findall(r"```dax\n(.*?)```", self.dax, re.S):
            clean = re.sub(r'"[^"]*"', "", re.sub(r"--[^\n]*", "", block))
            self.assertEqual(clean.count("("), clean.count(")"), block[:60])
            for var in re.findall(r"^VAR\s+(\w+)", clean, re.M):
                self.assertIn(var, re.sub(r"^VAR\s+\w+", "", clean, flags=re.M), f"unused VAR {var}")

    def test_power_query_columns_exist_in_exported_csvs(self):
        sections = re.split(r"^// -{10,} (\w+)\n", self.mcode, flags=re.M)[1:]
        self.assertEqual(sorted(sections[0::2]), sorted(self.tables))
        for name, body in zip(sections[0::2], sections[1::2]):
            typed = set(re.findall(r'\{"(\w+)",\s*(?:type|Int64)', body))
            self.assertTrue(typed, name)
            self.assertEqual(typed - self.columns[name], set(), name)
        fact_typed = set(re.findall(r'\{"(\w+)",\s*(?:type|Int64)', sections[1]))
        self.assertEqual(self.columns["fact_tracks"] - fact_typed, set())  # nothing left untyped

    def test_relationship_columns_exist_on_both_sides(self):
        for one_t, one_c, many_t, many_c in [("dim_genre", "track_genre", "fact_tracks", "track_genre"),
                                             ("dim_artist", "primary_artist", "fact_tracks", "primary_artist"),
                                             ("dim_popularity_band", "popularity_band", "fact_tracks", "popularity_band")]:
            self.assertIn(one_c, self.columns[one_t])
            self.assertIn(many_c, self.columns[many_t])
            self.assertIn(f"`{one_t}[{one_c}]`", self.model)
        # the "one" side must really be unique
        self.assertTrue(self.tables["dim_genre"]["track_genre"].is_unique)
        self.assertTrue(self.tables["dim_artist"]["primary_artist"].is_unique)
        self.assertTrue(self.tables["dim_popularity_band"]["popularity_band"].is_unique)

    def test_every_fact_popularity_band_has_a_dimension_row(self):
        facts = set(self.tables["fact_tracks"]["popularity_band"])
        self.assertTrue(facts <= set(self.tables["dim_popularity_band"]["popularity_band"]))

    def test_tempo_bin_sort_column_is_consistent(self):
        fact = self.tables["fact_tracks"].dropna(subset=["tempo_bin"])
        self.assertEqual(fact.groupby("tempo_bin")["tempo_bin_order"].nunique().max(), 1)

    def test_theme_is_valid_json_with_required_keys(self):
        theme = json.loads((PBI / "spotify_theme.json").read_text(encoding="utf-8"))
        for key in ("name", "dataColors", "background", "foreground", "visualStyles"):
            self.assertIn(key, theme)
        for colour in theme["dataColors"]:
            self.assertRegex(colour, r"^#[0-9A-Fa-f]{6}$")


if __name__ == "__main__":
    unittest.main()
