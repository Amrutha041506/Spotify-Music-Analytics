"""Exploratory data analysis helpers: pure computation functions + plotting.

Computation functions return DataFrames/dicts so they are easy to test and to
reuse from notebooks, the Streamlit app and the insights module.
Track-level questions use `unique_tracks` (one row per track_id) because a
track can appear under several genres in some datasets.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence


import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from src.data_loader import AUDIO_FEATURES

SPOTIFY_GREEN = "#1DB954"
SPOTIFY_BLACK = "#191414"
SPOTIFY_GREY = "#B3B3B3"

CORRELATION_FEATURES: List[str] = [
    "popularity", "danceability", "energy", "loudness", "speechiness",
    "acousticness", "instrumentalness", "liveness", "valence", "tempo", "duration_min",
]


# --------------------------------------------------------------------------- #
# Computation
# --------------------------------------------------------------------------- #
def unique_tracks(df: pd.DataFrame) -> pd.DataFrame:
    """One row per track_id (the highest-popularity row wins)."""
    return (
        df.sort_values(["popularity", "track_id"], ascending=[False, True], kind="mergesort")
        .drop_duplicates("track_id")
        .reset_index(drop=True)
    )


def top_tracks(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """Q1 - most popular tracks."""
    tracks = unique_tracks(df)
    tracks = tracks.sort_values(["popularity", "track_name"], ascending=[False, True])
    return tracks[["track_name", "primary_artist", "track_genre", "popularity"]].head(n).reset_index(drop=True)


def top_artists_by_avg_popularity(df: pd.DataFrame, n: int = 10, min_tracks: int = 5) -> pd.DataFrame:
    """Q2 - artists ranked by mean popularity (minimum track count avoids 1-hit noise)."""
    grouped = unique_tracks(df).groupby("primary_artist").agg(
        track_count=("track_id", "nunique"), avg_popularity=("popularity", "mean")
    )
    grouped = grouped[grouped["track_count"] >= min_tracks]
    return grouped.sort_values(["avg_popularity", "track_count"], ascending=False).head(n).round(2).reset_index()


def genre_metric_ranking(df: pd.DataFrame, metric: str, n: int = 10, min_tracks: int = 20) -> pd.DataFrame:
    """Q3/4/5/17/19 - genres ranked by the mean of `metric`."""
    grouped = df.groupby("track_genre").agg(
        track_count=("track_id", "nunique"), average=(metric, "mean")
    )
    grouped = grouped[grouped["track_count"] >= min_tracks]
    out = grouped.sort_values("average", ascending=False).head(n).round(3).reset_index()
    return out.rename(columns={"average": f"avg_{metric}"})


def duration_summary(df: pd.DataFrame) -> Dict[str, float]:
    """Q6 / Q16 - duration statistics in minutes (track level)."""
    d = unique_tracks(df)["duration_min"]
    return {"mean_min": round(float(d.mean()), 3), "median_min": round(float(d.median()), 3),
            "std_min": round(float(d.std()), 3), "p95_min": round(float(d.quantile(0.95)), 3)}


def top_tracks_by_feature(df: pd.DataFrame, feature: str, n: int = 10) -> pd.DataFrame:
    """Q7 / Q8 - tracks with the highest value of an audio feature."""
    tracks = unique_tracks(df).sort_values([feature, "track_name"], ascending=[False, True])
    return tracks[["track_name", "primary_artist", "track_genre", feature, "popularity"]].head(n).reset_index(drop=True)


def popularity_correlations(
    df: pd.DataFrame, features: Optional[Sequence[str]] = None, sample_n: int = 300_000, seed: int = 42
) -> pd.DataFrame:
    """Q9/10/11 - Pearson (all rows) and Spearman (sampled if huge) vs popularity."""
    features = [f for f in (features or AUDIO_FEATURES + ["duration_min"]) if f in df.columns]
    tracks = unique_tracks(df)
    cols = ["popularity", *features]
    pearson = tracks[cols].corr(method="pearson")["popularity"].drop("popularity")
    base = tracks if len(tracks) <= sample_n else tracks.sample(sample_n, random_state=seed)
    spearman = base[cols].corr(method="spearman")["popularity"].drop("popularity")
    out = pd.DataFrame({"pearson_r": pearson, "spearman_rho": spearman}).round(4)
    out["abs_pearson"] = out["pearson_r"].abs()
    return out.sort_values("abs_pearson", ascending=False).drop(columns="abs_pearson").rename_axis("feature").reset_index()


def artist_track_counts(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """Q12 - artists with the most distinct tracks."""
    counts = unique_tracks(df).groupby("primary_artist")["track_id"].nunique()
    return counts.sort_values(ascending=False).head(n).rename("track_count").reset_index()


def explicit_share(df: pd.DataFrame) -> Dict[str, object]:
    """Q13 - share of explicit tracks (None when the dataset has no explicit flag)."""
    flag = unique_tracks(df)["explicit"].dropna()
    if flag.empty:
        return {"available": False, "explicit_pct": None, "explicit_tracks": 0, "tracks_with_flag": 0}
    return {"available": True, "explicit_pct": round(float(flag.mean() * 100), 2),
            "explicit_tracks": int(flag.sum()), "tracks_with_flag": int(len(flag))}


def explicit_vs_popularity(df: pd.DataFrame) -> pd.DataFrame:
    """Q14 - popularity summary by explicit flag (empty if unavailable)."""
    tracks = unique_tracks(df).dropna(subset=["explicit"])
    if tracks.empty:
        return pd.DataFrame(columns=["explicit", "track_count", "mean_popularity", "median_popularity"])
    out = tracks.groupby("explicit")["popularity"].agg(["count", "mean", "median"]).round(2)
    out.columns = ["track_count", "mean_popularity", "median_popularity"]
    return out.reset_index()


def popularity_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """Q15 - popularity bucketed in bands of 10."""
    pop = unique_tracks(df)["popularity"]
    bins = list(range(0, 101, 10))
    bands = pd.cut(pop, bins=bins, include_lowest=True, right=True)
    return bands.value_counts(sort=False).rename("track_count").rename_axis("popularity_band").reset_index().astype({"popularity_band": str})


def feature_correlation_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Q18 - Pearson correlation between numeric audio features."""
    cols = [c for c in CORRELATION_FEATURES if c in df.columns]
    return unique_tracks(df)[cols].corr().round(3)


def genre_feature_means(df: pd.DataFrame, features: Sequence[str], min_tracks: int = 20) -> pd.DataFrame:
    grouped = df.groupby("track_genre")
    out = grouped[list(features)].mean()
    out["track_count"] = grouped["track_id"].nunique()
    return out[out["track_count"] >= min_tracks].round(3).reset_index()


def popular_vs_rest_profile(df: pd.DataFrame, quantile: float = 0.90) -> pd.DataFrame:
    """Q20 - mean audio profile of top-quantile tracks vs all other tracks."""
    tracks = unique_tracks(df)
    threshold = tracks["popularity"].quantile(quantile)
    popular = tracks[tracks["popularity"] >= threshold]
    rest = tracks[tracks["popularity"] < threshold]
    feats = [f for f in AUDIO_FEATURES + ["duration_min"] if f in tracks.columns]
    out = pd.DataFrame({
        "popular_mean": popular[feats].mean(),
        "rest_mean": rest[feats].mean(),
    })
    out["difference"] = out["popular_mean"] - out["rest_mean"]
    # difference in units of the overall standard deviation, so features on different scales compare fairly
    out["std_difference"] = out["difference"] / tracks[feats].std()
    out.attrs.update({"threshold": float(threshold), "popular_count": int(len(popular)), "rest_count": int(len(rest))})
    return out.round(4).rename_axis("feature").reset_index()


def sample_for_plot(df: pd.DataFrame, n: int = 50_000, seed: int = 42) -> pd.DataFrame:
    return df if len(df) <= n else df.sample(n, random_state=seed)


# --------------------------------------------------------------------------- #
# Plotting (every chart gets a title, axis labels and a Spotify-style theme)
# --------------------------------------------------------------------------- #
def apply_theme() -> None:
    sns.set_theme(style="whitegrid")
    plt.rcParams.update({"figure.dpi": 110, "axes.titlesize": 13, "axes.titleweight": "bold",
                         "axes.labelsize": 11, "axes.spines.top": False, "axes.spines.right": False})


def save_figure(fig: plt.Figure, name: str, out_dir: Optional[Path]) -> None:
    if out_dir is None:
        return
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / f"{name}.png", bbox_inches="tight")


def bar_chart(data: pd.DataFrame, label_col: str, value_col: str, title: str, xlabel: str,
              ylabel: str, color: str = SPOTIFY_GREEN, figsize=(9, 5)) -> plt.Figure:
    """Horizontal bar chart (best for long category labels). xlabel = value axis."""
    apply_theme()
    fig, ax = plt.subplots(figsize=figsize)
    ordered = data.iloc[::-1]
    ax.barh(ordered[label_col].astype(str), ordered[value_col], color=color)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    fig.tight_layout()
    return fig


def histogram(series: pd.Series, title: str, xlabel: str, ylabel: str = "Number of tracks",
              bins: int = 40, color: str = SPOTIFY_GREEN, figsize=(8, 4.5)) -> plt.Figure:
    apply_theme()
    fig, ax = plt.subplots(figsize=figsize)
    ax.hist(series.dropna(), bins=bins, color=color, edgecolor="white")
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    fig.tight_layout()
    return fig


def density_scatter(df: pd.DataFrame, x: str, y: str, title: str, xlabel: str, ylabel: str,
                    sample_n: int = 50_000, seed: int = 42, figsize=(7, 5)) -> plt.Figure:
    """Hexbin density plot - readable even with hundreds of thousands of points."""
    apply_theme()
    data = sample_for_plot(df[[x, y]].dropna(), sample_n, seed)
    fig, ax = plt.subplots(figsize=figsize)
    hb = ax.hexbin(data[x], data[y], gridsize=40, cmap="Greens", mincnt=1)
    fig.colorbar(hb, ax=ax, label="Tracks per cell")
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    fig.tight_layout()
    return fig


def heatmap(corr: pd.DataFrame, title: str, xlabel: str = "Feature", ylabel: str = "Feature",
            figsize=(9, 7)) -> plt.Figure:
    apply_theme()
    fig, ax = plt.subplots(figsize=figsize)
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="RdYlGn", center=0, vmin=-1, vmax=1,
                linewidths=0.5, ax=ax, cbar_kws={"label": "Pearson r"})
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    fig.tight_layout()
    return fig


def box_by_group(df: pd.DataFrame, group_col: str, value_col: str, title: str, xlabel: str,
                 ylabel: str, figsize=(6, 5)) -> plt.Figure:
    apply_theme()
    fig, ax = plt.subplots(figsize=figsize)
    sns.boxplot(data=df, x=group_col, y=value_col, color=SPOTIFY_GREEN, ax=ax)
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    fig.tight_layout()
    return fig
