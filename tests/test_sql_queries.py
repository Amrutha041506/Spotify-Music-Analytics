"""Run every SQL query against SQLite loaded with SYNTHETIC cleaned data.

This validates column names, DDL, and that each portable query executes and returns
the expected columns. It does NOT prove MySQL-specific behaviour: queries tagged
@mysql-only are skipped and the final proof must be done on a real MySQL 8 server
(see docs/sql_documentation.md).
"""
import re
import sqlite3
import unittest

import numpy as np

from src.data_cleaning import clean_dataset
from src.data_loader import CLEAN_COLUMNS
from tests.sql_helpers import SQL_DIR, all_queries
from tests.synthetic import make_raw_tracks


def _sqlite_ddl(sql_text: str):
    """Adapt 02_create_tables.sql for SQLite (drop USE / ENGINE clauses)."""
    no_comments = re.sub(r"--[^\n]*", "", sql_text)
    statements = [s.strip() for s in no_comments.split(";") if s.strip()]
    adapted = []
    for st in statements:
        if st.upper().startswith("USE "):
            continue
        st = re.sub(r"\)\s*ENGINE=InnoDB[^;]*$", ")", st, flags=re.IGNORECASE)
        adapted.append(st)
    return adapted


def build_database() -> sqlite3.Connection:
    raw = make_raw_tracks(n=1500, seed=1)
    rng = np.random.default_rng(1)
    raw["year"] = rng.integers(1990, 2021, len(raw))
    clean, _ = clean_dataset(raw)
    conn = sqlite3.connect(":memory:")
    for statement in _sqlite_ddl((SQL_DIR / "02_create_tables.sql").read_text(encoding="utf-8")):
        conn.execute(statement)
    clean[CLEAN_COLUMNS].astype(object).where(clean[CLEAN_COLUMNS].notna(), None).to_sql(
        "tracks", conn, if_exists="append", index=False)
    conn.commit()
    return conn


class TestSqlQueries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = build_database()
        cls.queries = all_queries()

    def test_at_least_25_queries_with_documentation(self):
        self.assertGreaterEqual(len(self.queries), 25)
        for q in self.queries:
            self.assertTrue(q["question"], f"{q['id']} has no Question line")
            self.assertTrue(q["explanation"], f"{q['id']} has no Explanation line")

    def test_query_ids_are_unique_and_sequential(self):
        ids = [q["id"] for q in self.queries]
        self.assertEqual(ids, [f"Q{i:02d}" for i in range(1, len(ids) + 1)])

    def test_table_columns_match_clean_columns(self):
        cols = [row[1] for row in self.conn.execute("PRAGMA table_info(tracks)")]
        self.assertEqual(cols, CLEAN_COLUMNS)

    def test_every_portable_query_executes(self):
        failures = []
        for q in self.queries:
            if q["mysql_only"]:
                continue
            try:
                cursor = self.conn.execute(q["sql"])
                cursor.fetchall()
            except sqlite3.Error as exc:
                failures.append(f"{q['id']}: {exc}")
        self.assertEqual(failures, [], "\n".join(failures))

    def test_row_count_and_primary_key(self):
        total = self.conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]
        self.assertGreater(total, 1000)
        dupes = self.conn.execute(
            "SELECT COUNT(*) FROM (SELECT track_id, track_genre FROM tracks "
            "GROUP BY track_id, track_genre HAVING COUNT(*) > 1)").fetchone()[0]
        self.assertEqual(dupes, 0)

    def test_validation_queries_report_clean_data(self):
        by_id = {q["id"]: q for q in self.queries}
        bad = self.conn.execute(by_id["Q04"]["sql"]).fetchone()
        self.assertEqual(sum(bad), 0)
        self.assertEqual(self.conn.execute(by_id["Q06"]["sql"]).fetchall(), [])
        inconsistent = self.conn.execute(by_id["Q08"]["sql"]).fetchone()[2]
        self.assertEqual(inconsistent, 0)

    def test_sql_matches_pandas_for_a_known_aggregate(self):
        by_id = {q["id"]: q for q in self.queries}
        sql_avg = self.conn.execute("SELECT ROUND(AVG(popularity), 2) FROM tracks").fetchone()[0]
        pandas_avg = round(float(np.mean([r[0] for r in self.conn.execute("SELECT popularity FROM tracks")])), 2)
        self.assertAlmostEqual(sql_avg, pandas_avg, places=2)
        top = self.conn.execute(by_id["Q11"]["sql"]).fetchall()
        self.assertEqual(len(top), 10)
        self.assertEqual([r[3] for r in top], sorted([r[3] for r in top], reverse=True))

    def test_join_queries_cover_all_bands(self):
        by_id = {q["id"]: q for q in self.queries}
        rows = self.conn.execute(by_id["Q35"]["sql"]).fetchall()
        self.assertEqual(len(rows), 5)


if __name__ == "__main__":
    unittest.main()


class TestSqlToolsAndPortability(unittest.TestCase):
    """Heuristic MySQL-compatibility lint, the verification runner, and result correctness vs pandas."""

    @classmethod
    def setUpClass(cls):
        cls.conn = build_database()
        cls.queries = all_queries()
        cls.by_id = {q["id"]: q for q in cls.queries}

    def test_no_query_is_mysql_only_any_more(self):
        self.assertEqual([q["id"] for q in self.queries if q["mysql_only"]], [])

    def test_lint_finds_nothing_suspicious_in_project_sql(self):
        from src.sql_tools import lint_mysql_compat
        findings = {q["id"]: lint_mysql_compat(q["sql"]) for q in self.queries}
        self.assertEqual({k: v for k, v in findings.items() if v}, {})

    def test_lint_detects_known_mysql_pitfalls(self):
        from src.sql_tools import lint_mysql_compat
        self.assertTrue(lint_mysql_compat("SELECT a ^ 2 FROM t"))
        self.assertTrue(lint_mysql_compat("SELECT a || b FROM t"))
        self.assertTrue(lint_mysql_compat("SELECT 1 FROM a FULL OUTER JOIN b ON 1=1"))
        self.assertTrue(lint_mysql_compat("SELECT x FROM t WHERE y IN (SELECT y FROM u LIMIT 3)"))
        self.assertTrue(lint_mysql_compat("SELECT RANK() OVER (ORDER BY a) AS rank FROM t"))
        self.assertTrue(lint_mysql_compat("SELECT key FROM t"))
        self.assertEqual(lint_mysql_compat("SELECT `key` FROM t WHERE a = 'x || y'"), [])

    def test_q46_matches_pandas_pearson(self):
        import pandas as pd
        frame = pd.read_sql("SELECT energy, popularity FROM tracks", self.conn)
        expected = round(float(frame["energy"].corr(frame["popularity"])), 4)
        actual = self.conn.execute(self.by_id["Q46"]["sql"]).fetchone()[0]
        self.assertAlmostEqual(actual, expected, places=3)

    def test_sql_results_match_pandas(self):
        import pandas as pd
        frame = pd.read_sql("SELECT * FROM tracks", self.conn)
        # Q13-style genre average popularity
        sql_rows = dict(self.conn.execute(
            "SELECT track_genre, ROUND(AVG(popularity), 2) FROM tracks GROUP BY track_genre").fetchall())
        pandas_rows = frame.groupby("track_genre")["popularity"].mean().round(2).to_dict()
        for genre, value in pandas_rows.items():
            self.assertAlmostEqual(sql_rows[genre], value, places=2)
        # Q23 explicit share
        explicit = self.conn.execute(self.by_id["Q23"]["sql"]).fetchone()
        self.assertAlmostEqual(explicit[2], round(float(frame["explicit"].mean() * 100), 2), places=2)
        # Q25 band counts add up to all rows
        self.assertEqual(sum(r[1] for r in self.conn.execute(self.by_id["Q25"]["sql"]).fetchall()), len(frame))
        # Q37 deciles cover every row
        self.assertEqual(sum(r[1] for r in self.conn.execute(self.by_id["Q37"]["sql"]).fetchall()), len(frame))

    def test_verification_runner_and_report(self):
        from src.sql_tools import results_markdown, verify_queries

        def execute(sql):
            cursor = self.conn.execute(sql)
            return [d[0] for d in cursor.description], cursor.fetchall()

        results = verify_queries(execute, self.queries + [{"id": "QX", "title": "bad", "sql": "SELECT nope FROM tracks"}])
        statuses = {r["id"]: r["status"] for r in results}
        self.assertEqual(statuses["QX"], "error")
        self.assertEqual([i for i, s in statuses.items() if s == "error"], ["QX"])
        report = results_markdown(results, {"database": "SQLite (test)"})
        self.assertIn("50 of 51 queries executed without error", report)
