"""Configuration loading (YAML + optional .env + environment overrides)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"

try:  # python-dotenv is optional; the project works without a .env file
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:  # pragma: no cover
    pass

_PATH_ENV_OVERRIDES = {
    "raw_dir": "SPOTIFY_RAW_DIR",
    "processed_dir": "SPOTIFY_PROCESSED_DIR",
    "reports_dir": "SPOTIFY_REPORTS_DIR",
    "powerbi_dir": "SPOTIFY_POWERBI_DIR",
    "raw_filename": "SPOTIFY_RAW_FILE",
}


def load_config(path: Optional[Path] = None) -> Dict[str, Any]:
    """Read config.yaml and apply environment-variable overrides."""
    with open(path or CONFIG_PATH, encoding="utf-8") as handle:
        cfg = yaml.safe_load(handle)

    for key, env_name in _PATH_ENV_OVERRIDES.items():
        if os.getenv(env_name):
            cfg["paths"][key] = os.environ[env_name]

    ollama = cfg.setdefault("ollama", {})
    if os.getenv("OLLAMA_HOST"):
        ollama["host"] = os.environ["OLLAMA_HOST"]
    if os.getenv("OLLAMA_MODEL"):
        ollama["model"] = os.environ["OLLAMA_MODEL"]
    return cfg


def resolve_path(path_like: str | Path) -> Path:
    """Turn a config path into an absolute path anchored at the project root."""
    path = Path(path_like)
    return path if path.is_absolute() else PROJECT_ROOT / path
