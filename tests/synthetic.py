"""SYNTHETIC test fixtures.

These rows are randomly generated so unit tests can run without the real Kaggle
file. They must NEVER be used as analysis data or quoted as findings.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def make_raw_tracks(n: int = 600, seed: int = 0, inject_defects: bool = True) -> pd.DataFrame:
    """Return a raw-looking DataFrame using the 114k-dataset column names."""
    rng = np.random.default_rng(seed)
    genres = ["pop", "rock", "jazz", "edm", "folk", "metal"]
    artists = [f"Artist {i}" for i in range(40)]
    artists[0] = "Collab A;Collab B"
    df = pd.DataFrame(
        {
            "track_id": [f"id{i:05d}" for i in range(n)],
            "artists": rng.choice(artists, n),
            "album_name": rng.choice([f"Album {i}" for i in range(60)], n),
            "track_name": [f"Song {i}" for i in range(n)],
            "popularity": rng.integers(0, 100, n),
            "duration_ms": rng.integers(90_000, 420_000, n),
            "explicit": rng.choice([True, False], n, p=[0.15, 0.85]),
            "danceability": rng.random(n).round(3),
            "energy": rng.random(n).round(3),
            "key": rng.integers(0, 12, n),
            "loudness": rng.uniform(-30, 0, n).round(3),
            "mode": rng.integers(0, 2, n),
            "speechiness": (rng.random(n) * 0.5).round(3),
            "acousticness": rng.random(n).round(3),
            "instrumentalness": (rng.random(n) ** 3).round(3),
            "liveness": (rng.random(n) * 0.6).round(3),
            "valence": rng.random(n).round(3),
            "tempo": rng.uniform(60, 190, n).round(3),
            "time_signature": rng.choice([3, 4, 5], n, p=[0.1, 0.8, 0.1]),
            "track_genre": rng.choice(genres, n),
        }
    )
    # make popularity weakly related to energy so correlations are not all ~0
    df["popularity"] = (df["popularity"] * 0.7 + df["energy"] * 30).clip(0, 100).round().astype(int)
    df.loc[:49, "artists"] = "Prolific Artist"  # an artist with many tracks

    if inject_defects:
        extra_dups = df.iloc[100:110].copy()                       # 10 exact duplicates
        same_id_lower_pop = df.iloc[120:125].copy()                # same id+genre, lower popularity
        same_id_lower_pop["popularity"] = same_id_lower_pop["popularity"] // 2
        multi_genre = df.iloc[130:135].copy()                      # same id, different genre (kept)
        multi_genre["track_genre"] = "multi-genre"
        df = pd.concat([df, extra_dups, same_id_lower_pop, multi_genre], ignore_index=True)

        df["valence"] = df["valence"].astype(object)               # raw CSVs can hold text in numeric columns
        df.loc[200, "track_name"] = None                           # missing identifier
        df.loc[201, "energy"] = None                               # missing core numeric
        df.loc[202, "energy"] = 1.7                                # invalid range
        df.loc[203, "popularity"] = 150                            # invalid range
        df.loc[204, "duration_ms"] = 0                             # invalid duration
        df.loc[205, "tempo"] = 0                                   # soft-invalid (kept, tempo -> NaN)
        df.loc[206, "time_signature"] = 0                          # soft-invalid
        df.loc[207, "valence"] = "not-a-number"                    # non-numeric -> coerced -> dropped
        df.loc[208, "album_name"] = None                           # filled with Unknown Album
        df.loc[209, "track_genre"] = None                          # -> 'unknown'
        df.loc[210, "artists"] = "  Padded Artist  "               # whitespace trimmed
        df.loc[211, "duration_ms"] = 3_000_000                     # 50 min: valid but outlier
    return df
