"""Tests for src/eda.py and src/insights.py (SYNTHETIC data)."""
import json
import unittest

import pandas as pd

from src import eda, insights
from src.data_cleaning import clean_dataset
from src.ollama_service import find_unsupported_numbers
from tests.synthetic import make_raw_tracks


class TestInsights(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.clean, _ = clean_dataset(make_raw_tracks(800, seed=11))
        cls.facts = insights.compute_facts(cls.clean, min_tracks_artist=5, min_tracks_genre=20)

    def test_facts_are_json_serialisable_and_complete(self):
        json.dumps(self.facts)
        for key in ("dataset", "top_tracks", "top_genres_by_popularity", "popularity_correlations", "notes"):
            self.assertIn(key, self.facts)

    def test_facts_match_direct_pandas_calculation(self):
        tracks = eda.unique_tracks(self.clean)
        self.assertEqual(self.facts["dataset"]["unique_tracks"], tracks["track_id"].nunique())
        self.assertAlmostEqual(self.facts["dataset"]["avg_popularity"], round(tracks["popularity"].mean(), 2), places=2)
        self.assertEqual(self.facts["top_tracks"][0]["popularity"], int(tracks["popularity"].max()))

    def test_unique_tracks_has_one_row_per_id(self):
        self.assertTrue(eda.unique_tracks(self.clean)["track_id"].is_unique)

    def test_ranking_respects_minimum_track_count(self):
        ranked = eda.genre_metric_ranking(self.clean, "popularity", n=50, min_tracks=10_000)
        self.assertTrue(ranked.empty)

    def test_correlation_labels(self):
        cases = {0.02: "negligible", 0.2: "weak positive", -0.4: "moderate negative", 0.8: "strong positive"}
        for r, expected in cases.items():
            self.assertEqual(insights.describe_correlation(r), expected)
        self.assertEqual(insights.describe_correlation(float("nan")), "undefined")

    def test_insights_contain_causation_caveat_and_no_invented_numbers(self):
        texts = insights.generate_insights(self.facts)
        self.assertGreaterEqual(len(texts), 5)
        self.assertTrue(any("causation" in t for t in texts))
        for text in texts:
            self.assertEqual(find_unsupported_numbers(text, self.facts), [], text)

    def test_rule_based_answers_route_by_keyword(self):
        self.assertIn("Genres with the highest average popularity", insights.answer_question_rule_based("Which genre is most popular?", self.facts))
        self.assertIn("Top artists", insights.answer_question_rule_based("top artists?", self.facts))
        self.assertIn("causation", insights.answer_question_rule_based("which features correlate with popularity", self.facts))
        self.assertIn("1.", insights.answer_question_rule_based("Give me five insights", self.facts))
        self.assertIn("I can answer", insights.answer_question_rule_based("what is the weather", self.facts))

    def test_strategy_suggestions_are_framed_as_hypotheses(self):
        self.assertTrue(any("hypotheses" in s for s in insights.strategy_suggestions(self.facts)))

    def test_explicit_analysis_skipped_gracefully_when_column_missing(self):
        no_explicit, _ = clean_dataset(make_raw_tracks(400, seed=12).drop(columns=["explicit"]))
        facts = insights.compute_facts(no_explicit)
        self.assertFalse(facts["dataset"]["explicit_available"])
        self.assertIsNone(facts["dataset"]["explicit_pct"])
        self.assertTrue(any("no 'explicit' column" in t for t in insights.generate_insights(facts)))

    def test_popularity_distribution_covers_all_tracks(self):
        dist = eda.popularity_distribution(self.clean)
        self.assertEqual(int(dist["track_count"].sum()), self.facts["dataset"]["unique_tracks"])

    def test_charts_have_title_and_axis_labels(self):
        import matplotlib
        matplotlib.use("Agg")
        tracks = eda.unique_tracks(self.clean)
        figures = [
            eda.histogram(tracks["popularity"], "T", "X", "Y"),
            eda.bar_chart(eda.top_tracks(self.clean, 5), "track_name", "popularity", "T", "X", "Y"),
            eda.density_scatter(tracks, "energy", "popularity", "T", "X", "Y"),
        ]
        for fig in figures:
            ax = fig.axes[0]
            self.assertTrue(ax.get_title() and ax.get_xlabel() and ax.get_ylabel())


if __name__ == "__main__":
    unittest.main()
