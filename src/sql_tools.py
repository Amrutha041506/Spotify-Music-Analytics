"""SQL helpers: parse the project's .sql files, lint for MySQL 8 pitfalls, and run a verification report.

The runner is database-agnostic (it only needs an `execute(sql) -> (columns, rows)` callable) so the same
code is unit-tested on SQLite and used for the real MySQL 8 report (`python -m src.mysql_verify`).
"""
from __future__ import annotations

import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Sequence, Tuple

from src.config import PROJECT_ROOT

SQL_DIR = PROJECT_ROOT / "sql"
QUERY_FILES = ("03_data_validation.sql", "04_basic_analysis.sql", "05_advanced_analysis.sql")
_HEADER = re.compile(r"^-- (Q\d+) \| (.+)$", re.MULTILINE)

# Words that are reserved in MySQL 8 and must not be used as unquoted aliases/identifiers.
MYSQL_RESERVED_ALIASES = {
    "rank", "dense_rank", "row_number", "lead", "lag", "ntile", "percent_rank", "cume_dist", "first_value",
    "last_value", "nth_value", "groups", "window", "system", "rows", "row", "over", "of", "empty", "function",
    "key", "keys", "index", "order", "group", "usage", "rank", "lateral", "recursive", "except",
}


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #
def parse_queries(path: Path) -> List[Dict[str, Any]]:
    """Return [{id, title, question, explanation, sql, file}] for every `-- Qnn | title` block."""
    text = Path(path).read_text(encoding="utf-8")
    matches = list(_HEADER.finditer(text))
    queries = []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[match.start():end]
        comments = "\n".join(ln for ln in block.splitlines() if ln.startswith("--"))
        sql = "\n".join(ln for ln in block.splitlines() if not ln.startswith("--")).strip().rstrip(";").strip()
        question = re.search(r"-- Question: (.+)", comments)
        explanation = re.search(r"-- Explanation: (.+)", comments)
        queries.append({
            "id": match.group(1), "title": match.group(2).strip(),
            "question": question.group(1).strip() if question else "",
            "explanation": explanation.group(1).strip() if explanation else "",
            "mysql_only": "@mysql-only" in match.group(0), "sql": sql, "file": Path(path).name,
        })
    return queries


def all_queries(sql_dir: Path = SQL_DIR) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for name in QUERY_FILES:
        out.extend(parse_queries(sql_dir / name))
    return out


# --------------------------------------------------------------------------- #
# Static MySQL-compatibility lint (heuristic - NOT a substitute for running on MySQL)
# --------------------------------------------------------------------------- #
def lint_mysql_compat(sql: str) -> List[str]:
    """Return a list of constructs that commonly break on MySQL 8. Empty list = nothing suspicious found."""
    body = re.sub(r"`[^`]*`", "``", sql)           # ignore backtick-quoted identifiers
    body = re.sub(r"'[^']*'", "''", body)          # ignore string literals
    issues = []
    checks = [
        (r"\^", "'^' is XOR in MySQL, not exponentiation"),
        (r"\|\|", "'||' is logical OR in MySQL (use CONCAT)"),
        (r"\bFULL\s+(OUTER\s+)?JOIN\b", "FULL OUTER JOIN is not supported by MySQL"),
        (r"\bILIKE\b", "ILIKE is not supported by MySQL"),
        (r"::", "'::' cast syntax is not supported by MySQL"),
        (r"\bRETURNING\b", "RETURNING is not supported by MySQL"),
        (r"\bIN\s*\(\s*SELECT[^()]*(\([^()]*\)[^()]*)*\bLIMIT\b", "LIMIT inside an IN (subquery) is not supported by MySQL"),
        (r"\bFILTER\s*\(\s*WHERE\b", "aggregate FILTER (WHERE ...) is not supported by MySQL"),
        (r"\bDISTINCT\s+ON\b", "DISTINCT ON is not supported by MySQL"),
    ]
    for pattern, message in checks:
        if re.search(pattern, body, re.IGNORECASE):
            issues.append(message)
    for alias in re.findall(r"\bAS\s+([A-Za-z_][A-Za-z0-9_]*)", body, re.IGNORECASE):
        if alias.lower() in MYSQL_RESERVED_ALIASES:
            issues.append(f"alias '{alias}' is a reserved word in MySQL 8 - quote it or rename it")
    if re.search(r"(?<![`\w])key(?![`\w])", body, re.IGNORECASE):
        issues.append("unquoted KEY (reserved word) - write `key`")
    return issues


# --------------------------------------------------------------------------- #
# Verification runner
# --------------------------------------------------------------------------- #
Executor = Callable[[str], Tuple[Sequence[str], List[Sequence[Any]]]]


def verify_queries(execute: Executor, queries: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Execute each query once and record outcome, row count and runtime."""
    results = []
    for q in queries:
        started = time.perf_counter()
        record: Dict[str, Any] = {"id": q["id"], "file": q.get("file", ""), "title": q["title"]}
        try:
            columns, rows = execute(q["sql"])
            record.update(status="ok" if rows else "ok-empty", rows=len(rows), columns=list(columns),
                          preview=[tuple(r) for r in rows[:1]], error="")
        except Exception as exc:  # noqa: BLE001 - any driver error must be reported, not raised
            record.update(status="error", rows=0, columns=[], preview=[], error=f"{type(exc).__name__}: {exc}")
        record["seconds"] = round(time.perf_counter() - started, 3)
        results.append(record)
    return results


def results_markdown(results: List[Dict[str, Any]], environment: Dict[str, str]) -> str:
    ok = sum(r["status"].startswith("ok") for r in results)
    lines = [
        "# SQL Verification Report", "",
        f"_Generated {datetime.now():%Y-%m-%d %H:%M} by `src/sql_tools.py` - every row below is a real execution result._", "",
        "## Environment", "", *[f"- **{k}:** {v}" for k, v in environment.items()], "",
        f"## Summary: {ok} of {len(results)} queries executed without error", "",
        "| ID | File | Status | Rows | Seconds | Error |", "|---|---|---|---:|---:|---|",
    ]
    for r in results:
        err = r["error"].replace("|", "/")[:160]
        lines.append(f"| {r['id']} | {r['file']} | {r['status']} | {r['rows']} | {r['seconds']} | {err} |")
    lines += ["", "`ok-empty` = ran successfully but returned no rows (expected for some checks, e.g. duplicate detection, "
              "or datasets without `year`/`explicit`).", ""]
    return "\n".join(lines)
