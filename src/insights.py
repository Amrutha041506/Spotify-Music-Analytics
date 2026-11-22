"""Compute verifiable facts from the cleaned data and turn them into insights.

Everything in `facts` is computed by pandas - nothing is estimated. The same facts
feed (a) the non-AI insight generator below and (b) the optional Ollama service,
so the LLM can only talk about numbers that were really computed.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

import pandas as pd

from src import eda

CAUSATION_NOTE = (
    "Correlation does not imply causation: these figures describe associations in this "
    "dataset, not reasons why tracks become popular."
)


def describe_correlation(r: float) -> str:
    """Plain-language label for a correlation coefficient (rule of thumb)."""
    if pd.isna(r):
        return "undefined"
    size = abs(r)
    if size < 0.10:
        strength = "negligible"
    elif size < 0.30:
        strength = "weak"
    elif size < 0.50:
        strength = "moderate"
    else:
        strength = "strong"
    if strength == "negligible":
        return strength
    return f"{strength} {'positive' if r > 0 else 'negative'}"


def _records(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """DataFrame -> list of plain-python dicts (JSON-safe)."""
    out = []
    for row in df.to_dict(orient="records"):
        out.append({k: (v.item() if hasattr(v, "item") else v) for k, v in row.items()})
    return out


def compute_facts(
    df: pd.DataFrame, min_tracks_artist: int = 5, min_tracks_genre: int = 20, popular_quantile: float = 0.90
) -> Dict[str, Any]:
    """Compute the facts dictionary from a cleaned DataFrame."""
    tracks = eda.unique_tracks(df)
    explicit = eda.explicit_share(df)
    corr = eda.popularity_correlations(df)
    corr["pearson_label"] = corr["pearson_r"].map(describe_correlation)
    profile = eda.popular_vs_rest_profile(df, popular_quantile)

    facts: Dict[str, Any] = {
        "dataset": {
            "rows": int(len(df)),
            "unique_tracks": int(len(tracks)),
            "unique_artists": int(tracks["primary_artist"].nunique()),
            "unique_genres": int(df["track_genre"].nunique()),
            "avg_popularity": round(float(tracks["popularity"].mean()), 2),
            "median_popularity": round(float(tracks["popularity"].median()), 2),
            "avg_duration_min": eda.duration_summary(df)["mean_min"],
            "median_duration_min": eda.duration_summary(df)["median_min"],
            "explicit_available": explicit["available"],
            "explicit_pct": explicit["explicit_pct"],
        },
        "top_tracks": _records(eda.top_tracks(df, 10)),
        "top_artists_by_avg_popularity": _records(
            eda.top_artists_by_avg_popularity(df, 10, min_tracks_artist)),
        "artists_with_most_tracks": _records(eda.artist_track_counts(df, 10)),
        "top_genres_by_popularity": _records(
            eda.genre_metric_ranking(df, "popularity", 10, min_tracks_genre)),
        "top_genres_by_danceability": _records(
            eda.genre_metric_ranking(df, "danceability", 5, min_tracks_genre)),
        "top_genres_by_energy": _records(eda.genre_metric_ranking(df, "energy", 5, min_tracks_genre)),
        "top_genres_by_valence": _records(eda.genre_metric_ranking(df, "valence", 5, min_tracks_genre)),
        "top_genres_by_instrumentalness": _records(
            eda.genre_metric_ranking(df, "instrumentalness", 5, min_tracks_genre)),
        "popularity_correlations": _records(corr),
        "popular_profile": {
            "definition": f"top {int(round((1 - popular_quantile) * 100))}% of tracks by popularity",
            "popularity_threshold": round(profile.attrs["threshold"], 2),
            "popular_track_count": profile.attrs["popular_count"],
            "feature_differences": _records(profile),
        },
        "explicit_vs_popularity": _records(eda.explicit_vs_popularity(df)),
        "settings": {"min_tracks_artist": min_tracks_artist, "min_tracks_genre": min_tracks_genre},
        "notes": [
            CAUSATION_NOTE,
            f"Artists need at least {min_tracks_artist} tracks and genres at least "
            f"{min_tracks_genre} tracks to appear in rankings.",
            "Popularity is a Spotify-defined score (0-100) tied to recent play counts at the "
            "time the dataset was collected.",
        ],
    }
    return facts


def generate_insights(facts: Dict[str, Any], max_items: int = 8) -> List[str]:
    """Rule-based insights written only from computed facts (no LLM needed)."""
    d = facts["dataset"]
    insights: List[str] = [
        f"The cleaned dataset holds {d['unique_tracks']:,} unique tracks by {d['unique_artists']:,} "
        f"artists across {d['unique_genres']:,} genres; average popularity is {d['avg_popularity']} "
        f"(median {d['median_popularity']}).",
        f"The average track lasts {d['avg_duration_min']} minutes (median {d['median_duration_min']}).",
    ]
    if facts["top_genres_by_popularity"]:
        g = facts["top_genres_by_popularity"][0]
        insights.append(
            f"'{g['track_genre']}' has the highest average popularity ({g['avg_popularity']}) among genres "
            f"with at least {facts['settings']['min_tracks_genre']} tracks."
        )
    if facts["top_artists_by_avg_popularity"]:
        a = facts["top_artists_by_avg_popularity"][0]
        insights.append(
            f"{a['primary_artist']} leads artists with at least {facts['settings']['min_tracks_artist']} "
            f"tracks, averaging {a['avg_popularity']} popularity over {a['track_count']} tracks."
        )
    corr = facts["popularity_correlations"]
    if corr:
        top = corr[0]
        insights.append(
            f"{top['feature']} shows the strongest linear association with popularity "
            f"(Pearson r = {top['pearson_r']}, {top['pearson_label']}). {CAUSATION_NOTE}"
        )
    if d["explicit_available"] and facts["explicit_vs_popularity"]:
        rows = {int(r["explicit"]): r for r in facts["explicit_vs_popularity"]}
        if 0 in rows and 1 in rows:
            insights.append(
                f"{d['explicit_pct']}% of tracks are explicit; mean popularity is "
                f"{rows[1]['mean_popularity']} for explicit vs {rows[0]['mean_popularity']} for non-explicit tracks."
            )
    elif not d["explicit_available"]:
        insights.append("This dataset has no 'explicit' column, so explicit-content analysis was skipped.")
    # rank by the standardised difference so features on different scales (tempo vs 0-1) compare fairly
    diffs = sorted(facts["popular_profile"]["feature_differences"], key=lambda r: abs(r["std_difference"]), reverse=True)
    if diffs:
        f = diffs[0]
        insights.append(
            f"Compared with other tracks, the {facts['popular_profile']['definition']} differ most in "
            f"{f['feature']} (mean {f['popular_mean']} vs {f['rest_mean']})."
        )
    return insights[:max_items]


def strategy_suggestions(facts: Dict[str, Any]) -> List[str]:
    """Hypotheses for recommendation platforms, explicitly framed as untested."""
    suggestions = []
    corr = facts["popularity_correlations"]
    if corr:
        c = corr[0]
        suggestions.append(
            f"Treat {c['feature']} as a candidate input feature for ranking models (association r = "
            f"{c['pearson_r']}); validate it with A/B tests before relying on it."
        )
    if facts["top_genres_by_popularity"]:
        names = ", ".join(g["track_genre"] for g in facts["top_genres_by_popularity"][:3])
        suggestions.append(f"Review editorial and playlist coverage for the highest-popularity genres: {names}.")
    suggestions.append(
        "Use genre-level audio profiles (danceability, energy, valence) to build mood-based playlists."
    )
    suggestions.append("These are hypotheses from observational data, not proven causes of popularity.")
    return suggestions


def answer_question_rule_based(question: str, facts: Dict[str, Any]) -> str:
    """Keyword-routed answer used when Ollama is unavailable."""
    q = question.lower()
    if "genre" in q and ("popular" in q or "highest" in q):
        rows = facts["top_genres_by_popularity"][:5]
        if rows:
            listing = "; ".join(f"{r['track_genre']} ({r['avg_popularity']})" for r in rows)
            return f"Genres with the highest average popularity: {listing}."
    if "artist" in q:
        rows = facts["top_artists_by_avg_popularity"][:5]
        if rows:
            listing = "; ".join(f"{r['primary_artist']} ({r['avg_popularity']})" for r in rows)
            return (f"Top artists by average popularity (min. {facts['settings']['min_tracks_artist']} tracks): "
                    f"{listing}.")
    if "correlat" in q or "feature" in q:
        rows = facts["popularity_correlations"][:5]
        if rows:
            listing = "; ".join(f"{r['feature']} (r={r['pearson_r']}, {r['pearson_label']})" for r in rows)
            return f"Audio features most associated with popularity: {listing}. {CAUSATION_NOTE}"
    if "strateg" in q or "recommend" in q:
        return " ".join(strategy_suggestions(facts))
    if "insight" in q or "trend" in q or "five" in q or "summary" in q:
        return "\n".join(f"{i}. {t}" for i, t in enumerate(generate_insights(facts, 5), 1))
    return ("I can answer questions about top genres, top artists, feature correlations, trends/insights "
            "and strategy ideas using the computed results. Try one of those topics.")
