"""Loading raw Spotify CSV files and reading/writing processed datasets."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd

from src.config import load_config, resolve_path

logger = logging.getLogger(__name__)

# Columns every supported dataset must provide (after alias renaming).
REQUIRED_COLUMNS: List[str] = [
    "track_id", "track_name", "artists", "popularity", "duration_ms",
    "danceability", "energy", "key", "loudness", "mode", "speechiness",
    "acousticness", "instrumentalness", "liveness", "valence", "tempo",
    "time_signature", "track_genre",
]
# Columns present in some datasets only (e.g. 'explicit' is absent in the 1M file).
OPTIONAL_COLUMNS: List[str] = ["album_name", "explicit", "year"]

# Order of columns in the cleaned CSV / MySQL `tracks` table.
CLEAN_COLUMNS: List[str] = [
    "track_id", "track_name", "artists", "primary_artist", "album_name",
    "track_genre", "year", "popularity", "duration_ms", "duration_min",
    "explicit", "danceability", "energy", "key", "loudness", "mode",
    "speechiness", "acousticness", "instrumentalness", "liveness", "valence",
    "tempo", "time_signature", "is_duration_outlier",
]

AUDIO_FEATURES: List[str] = [
    "danceability", "energy", "loudness", "speechiness", "acousticness",
    "instrumentalness", "liveness", "valence", "tempo",
]

DOWNLOAD_HELP = (
    "No raw CSV found in '{raw_dir}'. Download a Spotify tracks dataset from Kaggle "
    "(see docs/setup_guide.md), unzip it and place the .csv file in that folder."
)


class SchemaError(ValueError):
    """Raised when the dataset lacks columns the pipeline cannot work without."""


def find_raw_file(cfg: Optional[Dict[str, Any]] = None) -> Path:
    """Locate the raw CSV: explicit file name first, otherwise the largest CSV."""
    cfg = cfg or load_config()
    raw_dir = resolve_path(cfg["paths"]["raw_dir"])
    configured = cfg["paths"].get("raw_filename")
    if configured:
        candidate = Path(configured)
        candidate = candidate if candidate.is_absolute() else raw_dir / candidate
        if not candidate.exists():
            raise FileNotFoundError(f"Configured raw file not found: {candidate}")
        return candidate

    csv_files = sorted(raw_dir.glob("*.csv")) if raw_dir.exists() else []
    if not csv_files:
        raise FileNotFoundError(DOWNLOAD_HELP.format(raw_dir=raw_dir))
    if len(csv_files) > 1:
        logger.warning("Several CSV files found; using the largest. Set raw_filename to choose.")
    return max(csv_files, key=lambda p: p.stat().st_size)


def normalise_columns(df: pd.DataFrame, aliases: Dict[str, str]) -> pd.DataFrame:
    """Lower-case names, apply aliases, drop index-like and unknown columns."""
    renamed = {}
    for col in df.columns:
        clean = str(col).strip().lower()
        renamed[col] = aliases.get(clean, clean)
    df = df.rename(columns=renamed)
    df = df.loc[:, ~df.columns.str.startswith("unnamed")]
    df = df.loc[:, ~df.columns.duplicated()]
    known = set(REQUIRED_COLUMNS) | set(OPTIONAL_COLUMNS)
    return df[[c for c in df.columns if c in known]]


def read_raw_csv(
    path: Path,
    aliases: Optional[Dict[str, str]] = None,
    chunk_size: int = 200_000,
    nrows: Optional[int] = None,
) -> pd.DataFrame:
    """Read a raw CSV in chunks (keeps peak memory low for ~1M-row files)."""
    aliases = aliases or {}
    chunks = []
    # IDs are text; never let pandas turn them into numbers (would drop leading zeros)
    reader = pd.read_csv(path, chunksize=chunk_size, nrows=nrows, low_memory=False, dtype={"track_id": str, "id": str})
    for chunk in reader:
        chunks.append(normalise_columns(chunk, aliases))
    if not chunks:
        raise SchemaError(f"{path} contains no rows.")
    df = pd.concat(chunks, ignore_index=True)
    logger.info("Loaded %s rows x %s columns from %s", len(df), df.shape[1], path.name)
    return df


def validate_schema(df: pd.DataFrame) -> Dict[str, Any]:
    """Report which required/optional columns are present."""
    missing_required = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    missing_optional = [c for c in OPTIONAL_COLUMNS if c not in df.columns]
    return {
        "ok": not missing_required,
        "missing_required": missing_required,
        "missing_optional": missing_optional,
        "dtypes": {c: str(t) for c, t in df.dtypes.items()},
    }


def ensure_required_columns(df: pd.DataFrame) -> None:
    report = validate_schema(df)
    if not report["ok"]:
        raise SchemaError(f"Dataset is missing required columns: {report['missing_required']}")


# --------------------------------------------------------------------------- #
# Processed data
# --------------------------------------------------------------------------- #
def processed_paths(cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Path]:
    cfg = cfg or load_config()
    folder = resolve_path(cfg["paths"]["processed_dir"])
    return {
        "dir": folder,
        "csv": folder / cfg["paths"]["clean_csv"],
        "parquet": folder / cfg["paths"]["clean_parquet"],
    }


def save_processed(df: pd.DataFrame, cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Optional[Path]]:
    """Write the cleaned dataset as CSV (always) and Parquet (if pyarrow exists)."""
    paths = processed_paths(cfg)
    paths["dir"].mkdir(parents=True, exist_ok=True)
    ordered = df[[c for c in CLEAN_COLUMNS if c in df.columns]]
    ordered.to_csv(paths["csv"], index=False)
    parquet_path: Optional[Path] = paths["parquet"]
    try:
        ordered.to_parquet(parquet_path, index=False)
    except ImportError:
        logger.warning("pyarrow not installed - skipping Parquet output (CSV was written).")
        parquet_path = None
    return {"csv": paths["csv"], "parquet": parquet_path}


def load_processed(cfg: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
    """Load the cleaned dataset (Parquet preferred, CSV fallback)."""
    paths = processed_paths(cfg)
    if paths["parquet"].exists():
        try:
            return pd.read_parquet(paths["parquet"])
        except ImportError:
            logger.warning("pyarrow missing; falling back to CSV.")
    if paths["csv"].exists():
        return pd.read_csv(paths["csv"], low_memory=False)
    raise FileNotFoundError(
        f"Cleaned dataset not found in {paths['dir']}. Run `python -m src.pipeline` "
        "or notebook 02_data_cleaning.ipynb first."
    )
