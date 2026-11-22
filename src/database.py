"""MySQL helpers (SQLAlchemy + PyMySQL). Credentials come from environment / .env only."""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import List, Mapping, Optional
from urllib.parse import quote_plus

import pandas as pd

from src.data_loader import CLEAN_COLUMNS

logger = logging.getLogger(__name__)


def get_mysql_url(env: Optional[Mapping[str, str]] = None, include_database: bool = True) -> str:
    """Build a SQLAlchemy URL from MYSQL_* variables (see .env.example)."""
    env = env if env is not None else os.environ
    user = env.get("MYSQL_USER", "root")
    password = quote_plus(env.get("MYSQL_PASSWORD", ""))
    host = env.get("MYSQL_HOST", "localhost")
    port = env.get("MYSQL_PORT", "3306")
    database = env.get("MYSQL_DATABASE", "spotify_analytics")
    suffix = f"/{database}" if include_database else ""
    return f"mysql+pymysql://{user}:{password}@{host}:{port}{suffix}?charset=utf8mb4"


def create_db_engine(url: Optional[str] = None):
    """Create a SQLAlchemy engine; raises a clear error if dependencies are missing."""
    try:
        from sqlalchemy import create_engine
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Install database dependencies: pip install sqlalchemy pymysql cryptography") from exc
    return create_engine(url or get_mysql_url(), pool_pre_ping=True)


def split_sql_statements(sql_text: str) -> List[str]:
    """Split a SQL script into statements (drops `--` comments; no ';' inside strings assumed)."""
    no_comments = re.sub(r"--[^\n]*", "", sql_text)
    return [s.strip() for s in no_comments.split(";") if s.strip()]


def run_sql_file(engine, path: Path) -> int:
    """Execute every statement in a .sql file. Returns the number executed."""
    from sqlalchemy import text

    statements = split_sql_statements(Path(path).read_text(encoding="utf-8"))
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))
    return len(statements)


def check_connection(engine) -> bool:
    from sqlalchemy import text

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # noqa: BLE001 - report any driver error to the user
        logger.error("MySQL connection failed: %s", exc)
        return False


def load_clean_csv_to_mysql(engine, csv_path: Path, table: str = "tracks", chunk_size: int = 50_000) -> int:
    """Stream the cleaned CSV into an existing table (create it first with sql/02_create_tables.sql)."""
    total = 0
    for chunk in pd.read_csv(csv_path, chunksize=chunk_size, low_memory=False):
        chunk = chunk[CLEAN_COLUMNS]
        chunk.to_sql(table, engine, if_exists="append", index=False, method="multi", chunksize=5_000)
        total += len(chunk)
        logger.info("Inserted %s rows so far", total)
    return total


def run_query(engine, sql: str) -> pd.DataFrame:
    return pd.read_sql(sql, engine)
