"""End-to-end pipeline: raw CSV -> cleaned data -> reports -> Power BI tables.

Usage (from the project root):
    python -m src.pipeline                 # full run
    python -m src.pipeline --nrows 50000   # quick trial on the first 50k rows
    python -m src.pipeline --skip-powerbi
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from src import insights
from src.config import load_config, resolve_path
from src.data_cleaning import clean_dataset, validate_clean, write_quality_report
from src.data_loader import find_raw_file, read_raw_csv, save_processed, validate_schema
from src.powerbi_export import export_powerbi_tables

logger = logging.getLogger("spotify.pipeline")


def key_findings_markdown(facts: Dict[str, Any], source_file: str) -> str:
    lines = [
        "# Key Findings (generated from the cleaned dataset)",
        "",
        f"_Source file: `{source_file}`. Every statement below was computed by `src/insights.py`._",
        "",
    ]
    lines += [f"{i}. {text}" for i, text in enumerate(insights.generate_insights(facts, 10), 1)]
    lines += ["", "## Top 10 tracks", "", "| Track | Artist | Genre | Popularity |", "|---|---|---|---:|"]
    for t in facts["top_tracks"]:
        lines.append(f"| {t['track_name']} | {t['primary_artist']} | {t['track_genre']} | {t['popularity']} |")
    lines += ["", "## Popularity correlations", "", "| Feature | Pearson r | Spearman rho | Strength |", "|---|---:|---:|---|"]
    for c in facts["popularity_correlations"]:
        lines.append(f"| {c['feature']} | {c['pearson_r']} | {c['spearman_rho']} | {c['pearson_label']} |")
    lines += ["", "## Caveats", ""] + [f"- {n}" for n in facts["notes"]]
    return "\n".join(lines) + "\n"


def run_pipeline(cfg: Optional[Dict[str, Any]] = None, nrows: Optional[int] = None,
                 export_powerbi: bool = True) -> Dict[str, Any]:
    cfg = cfg or load_config()
    raw_path = find_raw_file(cfg)
    logger.info("Reading %s", raw_path)
    raw = read_raw_csv(raw_path, cfg.get("column_aliases", {}), cfg["loading"]["chunk_size"], nrows)

    schema = validate_schema(raw)
    if not schema["ok"]:
        raise SystemExit(f"Missing required columns: {schema['missing_required']}")

    clean, report = clean_dataset(raw, cfg["cleaning"])
    problems = validate_clean(clean)
    if problems:
        raise SystemExit(f"Cleaned data failed validation: {problems}")

    outputs = save_processed(clean, cfg)
    reports_dir = resolve_path(cfg["paths"]["reports_dir"])
    write_quality_report(report, reports_dir)

    a = cfg["analysis"]
    facts = insights.compute_facts(clean, a["min_tracks_per_artist"], a["min_tracks_per_genre"], a["popular_quantile"])
    (reports_dir / "key_findings.md").write_text(key_findings_markdown(facts, raw_path.name), encoding="utf-8")

    powerbi_files = {}
    if export_powerbi:
        powerbi_files = export_powerbi_tables(clean, resolve_path(cfg["paths"]["powerbi_dir"]))
    logger.info("Done: %s raw rows -> %s clean rows", report["rows_raw"], report["rows_clean"])
    return {"report": report, "outputs": outputs, "powerbi": powerbi_files, "facts": facts}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Spotify analytics pipeline.")
    parser.add_argument("--nrows", type=int, default=None, help="only read the first N rows (trial run)")
    parser.add_argument("--skip-powerbi", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    result = run_pipeline(nrows=args.nrows, export_powerbi=not args.skip_powerbi)
    print(f"Clean rows: {result['report']['rows_clean']:,}  ->  {result['outputs']['csv']}")


if __name__ == "__main__":
    main()
