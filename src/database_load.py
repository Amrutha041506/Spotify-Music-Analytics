"""One-command MySQL setup: create DB + tables, then load the cleaned CSV.

Usage:  python -m src.database_load
Requires MYSQL_* variables (see .env.example) and `pip install sqlalchemy pymysql cryptography`.
"""
from __future__ import annotations

import logging
import sys

from src.config import PROJECT_ROOT, load_config
from src.data_loader import processed_paths
from src.database import (check_connection, create_db_engine, get_mysql_url, load_clean_csv_to_mysql,
                          run_sql_file)

logger = logging.getLogger("spotify.database_load")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    csv_path = processed_paths(load_config())["csv"]
    if not csv_path.exists():
        logger.error("Cleaned CSV not found: %s. Run `python -m src.pipeline` first.", csv_path)
        return 1

    # 1) create the database using a server-level connection
    server_engine = create_db_engine(get_mysql_url(include_database=False))
    if not check_connection(server_engine):
        logger.error("Cannot connect to MySQL. Check MYSQL_HOST / MYSQL_USER / MYSQL_PASSWORD in .env.")
        return 1
    from sqlalchemy import text

    with server_engine.begin() as conn:
        conn.execute(text("CREATE DATABASE IF NOT EXISTS spotify_analytics CHARACTER SET utf8mb4 "
                          "COLLATE utf8mb4_unicode_ci"))

    # 2) create tables, 3) load rows
    engine = create_db_engine()
    run_sql_file(engine, PROJECT_ROOT / "sql" / "02_create_tables.sql")
    rows = load_clean_csv_to_mysql(engine, csv_path)
    logger.info("Loaded %s rows into spotify_analytics.tracks", f"{rows:,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
