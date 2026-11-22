"""Run the project's SQL on a REAL MySQL 8 server and write reports/mysql_test_report.md.

Usage (after `python -m src.pipeline` and filling MYSQL_* in .env):
    python -m src.mysql_verify --setup --load     # create DB/tables, load cleaned CSV, run all queries
    python -m src.mysql_verify                    # only run the queries
    python -m src.mysql_verify --dry-run          # parse + lint only, no database needed
The report only contains what the server actually returned.
"""
from __future__ import annotations

import argparse
import logging
import sys
from typing import Any, Dict, List

from src import sql_tools
from src.config import PROJECT_ROOT, load_config, resolve_path
from src.data_loader import processed_paths

logger = logging.getLogger("spotify.mysql_verify")


def _dry_run() -> int:
    queries = sql_tools.all_queries()
    problems = {q["id"]: sql_tools.lint_mysql_compat(q["sql"]) for q in queries}
    flagged = {k: v for k, v in problems.items() if v}
    print(f"Parsed {len(queries)} queries; lint findings: {flagged or 'none'}")
    print("Dry run only - this does NOT prove the queries run on MySQL.")
    return 1 if flagged else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the SQL scripts on MySQL 8.")
    parser.add_argument("--setup", action="store_true", help="create database/tables first (drops existing tables!)")
    parser.add_argument("--load", action="store_true", help="load the cleaned CSV into `tracks`")
    parser.add_argument("--dry-run", action="store_true", help="parse and lint only")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if args.dry_run:
        return _dry_run()

    from sqlalchemy import text
    from src.database import (check_connection, create_db_engine, get_mysql_url, load_clean_csv_to_mysql, run_sql_file)

    if args.setup:
        server = create_db_engine(get_mysql_url(include_database=False))
        if not check_connection(server):
            logger.error("Cannot connect to MySQL - check MYSQL_* in .env")
            return 1
        with server.begin() as conn:
            conn.execute(text("CREATE DATABASE IF NOT EXISTS spotify_analytics CHARACTER SET utf8mb4 "
                              "COLLATE utf8mb4_unicode_ci"))
    engine = create_db_engine()
    if not check_connection(engine):
        logger.error("Cannot connect to the spotify_analytics database - run with --setup first?")
        return 1
    if args.setup:
        run_sql_file(engine, PROJECT_ROOT / "sql" / "02_create_tables.sql")
    if args.load:
        csv_path = processed_paths(load_config())["csv"]
        logger.info("Loaded %s rows", f"{load_clean_csv_to_mysql(engine, csv_path):,}")

    def execute(sql: str):
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            return list(result.keys()), result.fetchall()

    env: Dict[str, str] = {}
    cols, rows = execute("SELECT VERSION(), @@sql_mode")
    env["MySQL version"], env["sql_mode"] = str(rows[0][0]), str(rows[0][1])
    env["rows in tracks"] = str(execute("SELECT COUNT(*) FROM tracks")[1][0][0])
    env["indexes on tracks"] = ", ".join(sorted({str(r[2]) for r in execute("SHOW INDEX FROM tracks")[1]}))

    results = sql_tools.verify_queries(execute, sql_tools.all_queries())
    report = sql_tools.results_markdown(results, env)
    out = resolve_path(load_config()["paths"]["reports_dir"]) / "mysql_test_report.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")
    failed = [r["id"] for r in results if r["status"] == "error"]
    print(f"Report: {out}\nFailed queries: {failed or 'none'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
