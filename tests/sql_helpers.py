"""Backwards-compatible wrapper: query parsing now lives in src/sql_tools.py."""
from src.sql_tools import SQL_DIR, all_queries, parse_queries  # noqa: F401
