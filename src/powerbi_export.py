"""Create Power BI-ready CSV tables (star-schema style) from the cleaned dataset."""
from __future__ import annotations

from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd

from src import eda

POPULARITY_BANDS = [
    ("00-19 Low", 0, 19, 1), ("20-39 Below avg", 20, 39, 2), ("40-59 Medium", 40, 59, 3),
    ("60-79 High", 60, 79, 4), ("80-100 Very high", 80, 100, 5),
]
FACT_COLUMNS = [
    "track_id", "track_name", "artists", "primary_artist", "album_name", "track_genre", "year",
    "popularity", "popularity_band", "duration_min", "explicit", "danceability", "energy", "key",
    "loudness", "mode", "speechiness", "acousticness", "instrumentalness", "liveness", "valence",
    "tempo", "tempo_bin", "tempo_bin_order", "time_signature",
]


def _band_labels(popularity: pd.Series) -> pd.Series:
    edges = [-1, 19, 39, 59, 79, 100]
    labels = [b[0] for b in POPULARITY_BANDS]
    return pd.cut(popularity, bins=edges, labels=labels).astype(str)


def _tempo_bins(tempo: pd.Series) -> pd.Series:
    edges = [0, 80, 100, 120, 140, 160, 180, 400]
    labels = ["<80", "80-99", "100-119", "120-139", "140-159", "160-179", "180+"]
    return pd.cut(tempo, bins=edges, labels=labels, right=False).astype("string")


def build_powerbi_tables(df: pd.DataFrame, min_tracks_artist: int = 1) -> Dict[str, pd.DataFrame]:
    fact = df.copy()
    fact["popularity_band"] = _band_labels(fact["popularity"])
    fact["tempo_bin"] = _tempo_bins(fact["tempo"])
    fact["tempo_bin_order"] = pd.cut(fact["tempo"], bins=[0, 80, 100, 120, 140, 160, 180, 400], labels=False, right=False).astype("Int8") + 1
    fact = fact[FACT_COLUMNS]

    genre_cols = ["popularity", "danceability", "energy", "valence", "acousticness", "instrumentalness", "speechiness"]
    dim_genre = df.groupby("track_genre").agg(
        track_count=("track_id", "nunique"), **{f"avg_{c}": (c, "mean") for c in genre_cols}
    ).round(4).reset_index()

    tracks = eda.unique_tracks(df)
    dim_artist = tracks.groupby("primary_artist").agg(
        track_count=("track_id", "nunique"), avg_popularity=("popularity", "mean")
    ).round(3).reset_index()
    dim_artist = dim_artist[dim_artist["track_count"] >= min_tracks_artist]

    corr = eda.feature_correlation_matrix(df)
    corr_long = corr.stack().rename("correlation").rename_axis(["feature_x", "feature_y"]).reset_index()

    bands = pd.DataFrame(POPULARITY_BANDS, columns=["popularity_band", "min_popularity", "max_popularity", "sort_order"])
    return {"fact_tracks": fact, "dim_genre": dim_genre, "dim_artist": dim_artist,
            "feature_correlation": corr_long, "dim_popularity_band": bands}


def export_powerbi_tables(df: pd.DataFrame, out_dir: Path) -> Dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, table in build_powerbi_tables(df).items():
        path = out_dir / f"{name}.csv"
        table.to_csv(path, index=False)
        paths[name] = path
    return paths
