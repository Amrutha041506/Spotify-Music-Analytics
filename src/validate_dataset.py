"""Validate a downloaded Spotify CSV *before* cleaning: structure, types, missing values, duplicates, provenance.

Usage:  python -m src.validate_dataset [path\\to\\file.csv] [--nrows 200000]
Writes reports/dataset_validation.md. Nothing is assumed about the file: all findings come from the file itself.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from src.config import load_config, resolve_path
from src.data_loader import OPTIONAL_COLUMNS, REQUIRED_COLUMNS, find_raw_file, normalise_columns

# Column list from the original project brief (the 114k "Spotify Tracks Dataset").
BRIEF_COLUMNS = [
    "track_id", "artists", "album_name", "track_name", "popularity", "duration_ms", "explicit", "danceability",
    "energy", "key", "loudness", "mode", "speechiness", "acousticness", "instrumentalness", "liveness",
    "valence", "tempo", "time_signature", "track_genre",
]
# Column list of the ~1M dataset as I remember it - UNVERIFIED, so a mismatch is reported, not assumed wrong.
MILLION_COLUMNS_UNVERIFIED = [
    "artist_name", "track_name", "track_id", "popularity", "year", "genre", "danceability", "energy", "key",
    "loudness", "mode", "speechiness", "acousticness", "instrumentalness", "liveness", "valence", "tempo",
    "duration_ms", "time_signature",
]
SPOTIFY_ID = re.compile(r"^[0-9A-Za-z]{22}$")
UNIT = ["danceability", "energy", "speechiness", "acousticness", "instrumentalness", "liveness", "valence"]


def detect_layout(raw_columns: List[str]) -> str:
    cols = {str(c).strip().lower() for c in raw_columns} - {c for c in map(str.lower, map(str, raw_columns)) if c.startswith("unnamed")}
    if set(BRIEF_COLUMNS) <= cols:
        return "matches the column list from the project brief (114k-style)"
    if set(MILLION_COLUMNS_UNVERIFIED) <= cols:
        return "matches the unverified 1M-style column list"
    return "UNKNOWN layout - compare the header below with docs/data_dictionary.md and add aliases if needed"


def profile_csv(path: Path, aliases: Optional[Dict[str, str]] = None, nrows: Optional[int] = None) -> Dict[str, Any]:
    raw = pd.read_csv(path, nrows=nrows, low_memory=False, dtype={"track_id": str, "id": str})
    raw_columns = list(raw.columns)
    inferred = {c: str(t) for c, t in raw.dtypes.items()}
    df = normalise_columns(raw, aliases or {})
    report: Dict[str, Any] = {
        "file": str(path), "size_mb": round(path.stat().st_size / 1e6, 2), "rows_read": int(len(raw)),
        "partial_read": nrows is not None, "raw_columns": raw_columns, "layout": detect_layout(raw_columns),
        "missing_required": [c for c in REQUIRED_COLUMNS if c not in df.columns],
        "missing_optional": [c for c in OPTIONAL_COLUMNS if c not in df.columns],
        "ignored_columns": [c for c in raw_columns if str(c).strip().lower() not in df.columns
                            and aliases.get(str(c).strip().lower()) not in df.columns],
        "inferred_dtypes": inferred,
        "missing_values": {c: int(v) for c, v in raw.isna().sum().items() if v},
    }
    report["exact_duplicate_rows"] = int(raw.duplicated().sum())
    if {"track_id"} <= set(df.columns):
        report["duplicate_track_ids"] = int(df["track_id"].duplicated().sum())
        ids = df["track_id"].dropna().astype(str)
        report["pct_ids_spotify_format"] = round(float(ids.map(lambda s: bool(SPOTIFY_ID.match(s))).mean() * 100), 2) if len(ids) else 0.0
    if {"track_id", "track_genre"} <= set(df.columns):
        report["duplicate_track_genre_pairs"] = int(df.duplicated(subset=["track_id", "track_genre"]).sum())
    ranges: Dict[str, int] = {}
    numeric = df.apply(pd.to_numeric, errors="coerce")
    for col in UNIT:
        if col in numeric:
            ranges[f"{col} outside 0-1"] = int((~numeric[col].between(0, 1) & numeric[col].notna()).sum())
    if "popularity" in numeric:
        ranges["popularity outside 0-100"] = int((~numeric["popularity"].between(0, 100) & numeric["popularity"].notna()).sum())
    if "duration_ms" in numeric:
        ranges["duration_ms <= 0"] = int((numeric["duration_ms"] <= 0).sum())
    non_numeric = {c: int((numeric[c].isna() & df[c].notna()).sum()) for c in numeric.columns
                   if c in UNIT + ["popularity", "duration_ms", "tempo", "loudness", "key", "mode", "time_signature", "year"]}
    report["range_violations"] = ranges
    report["non_numeric_in_numeric_columns"] = {k: v for k, v in non_numeric.items() if v}
    report["verdict"] = ("OK to clean" if not report["missing_required"]
                         else f"BLOCKED - missing required columns {report['missing_required']}")
    if report.get("pct_ids_spotify_format", 100) < 99:
        report["provenance_warning"] = ("Most track_id values do not look like real 22-character Spotify IDs - "
                                        "this may be synthetic or modified data; do not treat results as real Spotify findings.")
    return report


def to_markdown(r: Dict[str, Any]) -> str:
    L = ["# Dataset Validation Report", "",
         f"- File: `{r['file']}` ({r['size_mb']} MB), rows read: **{r['rows_read']:,}**" + (" (partial read)" if r["partial_read"] else ""),
         f"- Layout: {r['layout']}", f"- Verdict: **{r['verdict']}**",
         f"- Missing required columns: {r['missing_required'] or 'none'}",
         f"- Missing optional columns: {r['missing_optional'] or 'none'}",
         f"- Columns ignored by the pipeline: {r['ignored_columns'] or 'none'}",
         f"- Exact duplicate rows: {r['exact_duplicate_rows']:,}",
         f"- Duplicate track_ids: {r.get('duplicate_track_ids', 'n/a')}; duplicate (track_id, genre): {r.get('duplicate_track_genre_pairs', 'n/a')}",
         f"- Track IDs in Spotify 22-char format: {r.get('pct_ids_spotify_format', 'n/a')}% (format check only - it cannot prove the data is genuine Spotify data)"]
    if "provenance_warning" in r:
        L.append(f"- ⚠️ {r['provenance_warning']}")
    L += ["", "## Header as found", "", ", ".join(f"`{c}`" for c in r["raw_columns"]), "",
          "## Missing values", "", *([f"- {k}: {v:,}" for k, v in r["missing_values"].items()] or ["- none"]), "",
          "## Range violations (before cleaning)", "", *[f"- {k}: {v:,}" for k, v in r["range_violations"].items()], "",
          "## Non-numeric text in numeric columns", "", *([f"- {k}: {v:,}" for k, v in r["non_numeric_in_numeric_columns"].items()] or ["- none"]), "",
          "## Inferred dtypes", "", "| Column | dtype |", "|---|---|", *[f"| {k} | {v} |" for k, v in r["inferred_dtypes"].items()], ""]
    return "\n".join(L)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a downloaded Spotify CSV.")
    parser.add_argument("path", nargs="?", help="CSV path (default: auto-detect in dataset/raw)")
    parser.add_argument("--nrows", type=int, default=None)
    args = parser.parse_args()
    cfg = load_config()
    path = Path(args.path) if args.path else find_raw_file(cfg)
    report = profile_csv(path, cfg.get("column_aliases", {}), args.nrows)
    out = resolve_path(cfg["paths"]["reports_dir"]) / "dataset_validation.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(to_markdown(report), encoding="utf-8")
    print(to_markdown(report)[:1800], f"\n... full report: {out}")
    return 0 if not report["missing_required"] else 1


if __name__ == "__main__":
    sys.exit(main())
