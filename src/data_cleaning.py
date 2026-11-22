"""Cleaning, validation and data-quality reporting for Spotify track data.

Cleaning policy (also documented in docs/data_dictionary.md):
  * text columns: trim whitespace, blank -> missing
  * numeric columns: coerce to numbers; unparseable values become missing
  * invalid ranges: rows dropped (popularity, 0-1 audio features, loudness,
    duration, key, mode); tempo / time_signature / year set to missing instead
  * missing identifiers (track_id, track_name, artists) or core numerics: rows dropped
  * duplicates: exact duplicate rows removed, then one row kept per
    (track_id, track_genre) - the one with the highest popularity
  * outliers: NOT deleted. Extreme duration is flagged in `is_duration_outlier`
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.data_loader import (
    CLEAN_COLUMNS,
    OPTIONAL_COLUMNS,
    REQUIRED_COLUMNS,
    ensure_required_columns,
)

UNIT_INTERVAL = [
    "danceability", "energy", "speechiness", "acousticness",
    "instrumentalness", "liveness", "valence",
]
TEXT_COLUMNS = ["track_id", "track_name", "artists", "album_name", "track_genre"]
NUMERIC_COLUMNS = [
    "popularity", "duration_ms", "danceability", "energy", "key", "loudness",
    "mode", "speechiness", "acousticness", "instrumentalness", "liveness",
    "valence", "tempo", "time_signature", "year",
]
IDENTIFIER_COLUMNS = ["track_id", "track_name", "artists"]
# Rows missing any of these are dropped; tempo / time_signature / year may stay missing.
CORE_NUMERIC = [
    "popularity", "duration_ms", "key", "loudness", "mode", *UNIT_INTERVAL,
]

DEFAULT_CLEANING = {
    "max_duration_min": 60,
    "min_year": 1900,
    "tempo_range": [30, 300],
    "loudness_range": [-60, 5],
    "duration_outlier_iqr": 3.0,
    "fill_unknown_genre": True,
}


class _StepLog:
    """Records how many rows each cleaning step removed."""

    def __init__(self) -> None:
        self.steps: List[Dict[str, Any]] = []

    def record(self, name: str, before: int, after: int, detail: str = "") -> None:
        self.steps.append(
            {"step": name, "rows_before": before, "rows_after": after,
             "rows_removed": before - after, "detail": detail}
        )


def _normalise_explicit(series: pd.Series) -> pd.Series:
    mapping = {"true": 1, "false": 0, "1": 1, "0": 0, "1.0": 1, "0.0": 0, "yes": 1, "no": 0}
    text = series.astype("string").str.strip().str.lower()
    return text.map(mapping).astype("Int8")


def clean_dataset(
    raw: pd.DataFrame, cleaning_cfg: Optional[Dict[str, Any]] = None
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Clean a raw tracks DataFrame. Returns (clean_df, quality_report)."""
    cfg = {**DEFAULT_CLEANING, **(cleaning_cfg or {})}
    ensure_required_columns(raw)
    log = _StepLog()
    df = raw.copy()

    report: Dict[str, Any] = {
        "rows_raw": int(len(df)),
        "columns_raw": list(raw.columns),
        "missing_before": {c: int(v) for c, v in raw.isna().sum().items()},
    }

    absent_optional = [c for c in OPTIONAL_COLUMNS if c not in df.columns]
    for col in absent_optional:
        df[col] = pd.NA
    report["absent_optional_columns"] = absent_optional

    # ---- 1. text columns ---------------------------------------------------
    for col in TEXT_COLUMNS:
        if df[col].isna().all():
            continue
        df[col] = df[col].astype("string").str.strip().replace("", pd.NA)

    # ---- 2. numeric coercion ----------------------------------------------
    coerced_to_missing: Dict[str, int] = {}
    for col in NUMERIC_COLUMNS:
        before_na = int(df[col].isna().sum())
        df[col] = pd.to_numeric(df[col], errors="coerce")
        newly_missing = int(df[col].isna().sum()) - before_na
        if newly_missing:
            coerced_to_missing[col] = newly_missing
    report["non_numeric_values_coerced_to_missing"] = coerced_to_missing

    if df["explicit"].notna().any():
        df["explicit"] = _normalise_explicit(df["explicit"])
    else:
        df["explicit"] = pd.array([pd.NA] * len(df), dtype="Int8")

    # ---- 3. invalid values ------------------------------------------------
    n = len(df)
    invalid_flags = pd.Series(False, index=df.index)
    invalid_counts: Dict[str, int] = {}

    def flag(name: str, mask: pd.Series) -> None:
        nonlocal invalid_flags
        mask = mask.fillna(False)
        invalid_counts[name] = int(mask.sum())
        invalid_flags |= mask

    flag("popularity_outside_0_100", ~df["popularity"].between(0, 100) & df["popularity"].notna())
    for col in UNIT_INTERVAL:
        flag(f"{col}_outside_0_1", ~df[col].between(0, 1) & df[col].notna())
    lo, hi = cfg["loudness_range"]
    flag("loudness_out_of_range", ~df["loudness"].between(lo, hi) & df["loudness"].notna())
    max_ms = cfg["max_duration_min"] * 60_000
    flag("duration_non_positive_or_too_long", ~df["duration_ms"].between(1, max_ms) & df["duration_ms"].notna())
    flag("key_outside_-1_11", ~df["key"].between(-1, 11) & df["key"].notna())
    flag("mode_not_0_or_1", ~df["mode"].isin([0, 1]) & df["mode"].notna())
    df = df.loc[~invalid_flags].copy()
    log.record("drop_invalid_value_rows", n, len(df), "range violations (see invalid_value_counts)")

    # Soft-invalid: keep the row, blank the value.
    t_lo, t_hi = cfg["tempo_range"]
    bad_tempo = ~df["tempo"].between(t_lo, t_hi) & df["tempo"].notna()
    invalid_counts["tempo_set_to_missing"] = int(bad_tempo.sum())
    df.loc[bad_tempo, "tempo"] = np.nan
    bad_ts = ~df["time_signature"].between(1, 7) & df["time_signature"].notna()
    invalid_counts["time_signature_set_to_missing"] = int(bad_ts.sum())
    df.loc[bad_ts, "time_signature"] = np.nan
    max_year = pd.Timestamp.today().year + 1
    bad_year = ~df["year"].between(cfg["min_year"], max_year) & df["year"].notna()
    invalid_counts["year_set_to_missing"] = int(bad_year.sum())
    df.loc[bad_year, "year"] = np.nan
    report["invalid_value_counts"] = invalid_counts

    # ---- 4. missing values -------------------------------------------------
    n = len(df)
    df = df.dropna(subset=IDENTIFIER_COLUMNS)
    log.record("drop_missing_identifiers", n, len(df), f"missing any of {IDENTIFIER_COLUMNS}")
    n = len(df)
    df = df.dropna(subset=CORE_NUMERIC)
    log.record("drop_missing_core_numeric", n, len(df), f"missing any of {CORE_NUMERIC}")

    if cfg["fill_unknown_genre"]:
        df["track_genre"] = df["track_genre"].fillna("unknown")
    else:
        df = df.dropna(subset=["track_genre"])
    if df["album_name"].notna().any():  # only fill when the column really exists in the data
        df["album_name"] = df["album_name"].fillna("Unknown Album")

    # ---- 5. duplicates -----------------------------------------------------
    n = len(df)
    df = df.drop_duplicates()
    log.record("drop_exact_duplicates", n, len(df), "all columns identical")
    n = len(df)
    df = (
        df.sort_values(["popularity", "track_id"], ascending=[False, True], kind="mergesort")
        .drop_duplicates(subset=["track_id", "track_genre"], keep="first")
    )
    log.record("drop_duplicate_track_genre_pairs", n, len(df),
               "kept highest-popularity row per (track_id, track_genre)")
    df = df.reset_index(drop=True)

    # ---- 6. derived columns & types ---------------------------------------
    df["primary_artist"] = df["artists"].str.split(";").str[0].str.strip().astype("string")
    df["duration_min"] = (df["duration_ms"] / 60_000).round(3)
    q1, q3 = df["duration_min"].quantile([0.25, 0.75])
    upper = q3 + cfg["duration_outlier_iqr"] * (q3 - q1)
    df["is_duration_outlier"] = (df["duration_min"] > upper).astype("int8")

    int_types = {"popularity": "int16", "duration_ms": "int32", "key": "int8", "mode": "int8"}
    for col, dtype in int_types.items():
        df[col] = df[col].astype(dtype)
    df["time_signature"] = df["time_signature"].round().astype("Int8")
    df["year"] = df["year"].round().astype("Int16")

    df = df[CLEAN_COLUMNS]

    # ---- 7. report ----------------------------------------------------------
    report.update(
        {
            "rows_clean": int(len(df)),
            "rows_removed_total": int(report["rows_raw"] - len(df)),
            "steps": log.steps,
            "missing_after": {c: int(v) for c, v in df.isna().sum().items()},
            "dtypes_after": {c: str(t) for c, t in df.dtypes.items()},
            "duration_outlier_upper_bound_min": round(float(upper), 3),
            "duration_outliers_flagged": int(df["is_duration_outlier"].sum()),
            "unique_tracks": int(df["track_id"].nunique()),
            "tracks_in_multiple_genres": int((df.groupby("track_id")["track_genre"].nunique() > 1).sum()),
            "rows_sharing_name_and_artist_informational": int(
                df.duplicated(subset=["track_name", "primary_artist"], keep=False).sum()
            ),
        }
    )
    return df, report


def validate_clean(df: pd.DataFrame) -> List[str]:
    """Check a cleaned DataFrame; returns a list of problems (empty list = valid)."""
    problems: List[str] = []
    missing_cols = [c for c in CLEAN_COLUMNS if c not in df.columns]
    if missing_cols:
        return [f"missing columns: {missing_cols}"]

    for col in ["track_id", "track_name", "artists", "primary_artist", "track_genre", *CORE_NUMERIC]:
        if df[col].isna().any():
            problems.append(f"null values in '{col}'")
    if df.duplicated(subset=["track_id", "track_genre"]).any():
        problems.append("duplicate (track_id, track_genre) pairs")
    if not df["popularity"].between(0, 100).all():
        problems.append("popularity outside 0-100")
    for col in UNIT_INTERVAL:
        if not df[col].dropna().between(0, 1).all():
            problems.append(f"'{col}' outside 0-1")
    if (df["duration_ms"] <= 0).any():
        problems.append("non-positive duration")
    if not np.allclose(df["duration_min"], df["duration_ms"] / 60_000, atol=1e-3):
        problems.append("duration_min inconsistent with duration_ms")
    if df["time_signature"].dropna().lt(1).any() or df["time_signature"].dropna().gt(7).any():
        problems.append("time_signature outside 1-7")
    return problems


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def quality_report_markdown(report: Dict[str, Any]) -> str:
    lines = [
        "# Data Quality Report",
        "",
        f"- Raw rows: **{report['rows_raw']:,}**",
        f"- Clean rows: **{report['rows_clean']:,}**",
        f"- Rows removed: **{report['rows_removed_total']:,}**",
        f"- Unique tracks (by track_id): **{report['unique_tracks']:,}**",
        f"- Tracks appearing in more than one genre: **{report['tracks_in_multiple_genres']:,}**",
        f"- Optional columns absent from this dataset: {report['absent_optional_columns'] or 'none'}",
        "",
        "## Cleaning steps",
        "",
        "| Step | Rows before | Rows after | Removed | Detail |",
        "|---|---:|---:|---:|---|",
    ]
    for s in report["steps"]:
        lines.append(
            f"| {s['step']} | {s['rows_before']:,} | {s['rows_after']:,} | {s['rows_removed']:,} | {s['detail']} |"
        )
    lines += ["", "## Invalid values detected", "", "| Check | Count |", "|---|---:|"]
    for k, v in report["invalid_value_counts"].items():
        lines.append(f"| {k} | {v:,} |")
    lines += ["", "## Non-numeric values coerced to missing", ""]
    coerced = report["non_numeric_values_coerced_to_missing"]
    lines += [f"- {k}: {v:,}" for k, v in coerced.items()] or ["- none"]
    lines += ["", "## Missing values (raw vs clean)", "", "| Column | Raw | Clean |", "|---|---:|---:|"]
    for col in report["missing_after"]:
        lines.append(f"| {col} | {report['missing_before'].get(col, 'n/a')} | {report['missing_after'][col]} |")
    lines += [
        "",
        "## Outliers",
        "",
        f"- Duration outliers flagged (kept): {report['duration_outliers_flagged']:,} "
        f"(> {report['duration_outlier_upper_bound_min']} min)",
        "",
    ]
    return "\n".join(lines)


def write_quality_report(report: Dict[str, Any], reports_dir: Path) -> Dict[str, Path]:
    reports_dir.mkdir(parents=True, exist_ok=True)
    json_path = reports_dir / "data_quality_report.json"
    md_path = reports_dir / "data_quality_report.md"
    json_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    md_path.write_text(quality_report_markdown(report), encoding="utf-8")
    return {"json": json_path, "markdown": md_path}
