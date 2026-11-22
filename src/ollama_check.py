"""Check the Ollama setup end-to-end and write reports/ollama_check.md.

Usage:  python -m src.ollama_check [--model llama3.1] [--host http://localhost:11434]
Checks: ollama binary on PATH -> server reachable -> model installed -> live grounded answers (needs cleaned data)
        -> unsupported-number detection -> fallback when the server is unreachable.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from typing import Any, Callable, Dict, List, Optional

from src.config import load_config, resolve_path
from src.insights import compute_facts
from src.ollama_service import (OllamaClient, OllamaError, OllamaSettings, answer_with_fallback,
                                find_unsupported_numbers)

SETUP_HELP = ("Install Ollama (https://ollama.com/download/windows), then run: ollama pull {model} ; "
              "ollama serve (the Windows app starts it automatically).")
QUESTIONS = ["Which genre has the highest average popularity?", "Give me five important business insights.",
             "What is the average popularity of tracks in the genre 'zz-nonexistent-genre'?"]


def run_checks(settings: OllamaSettings, facts: Optional[Dict[str, Any]], which: Callable[[str], Optional[str]] = shutil.which,
               client: Optional[OllamaClient] = None) -> List[Dict[str, str]]:
    checks: List[Dict[str, str]] = []

    def add(name: str, status: str, detail: str) -> None:
        checks.append({"check": name, "status": status, "detail": detail})

    exe = which("ollama")
    if exe:
        try:
            version = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=10).stdout.strip()
        except Exception as exc:  # noqa: BLE001
            version = f"(version query failed: {exc})"
        add("ollama binary on PATH", "PASS", f"{exe} {version}")
    else:
        add("ollama binary on PATH", "FAIL", SETUP_HELP.format(model=settings.model))

    client = client or OllamaClient(settings)
    live = False
    try:
        models = client.list_models()
        add("server reachable", "PASS", f"{settings.host}; installed models: {', '.join(models) or 'none'}")
        if client.has_model():
            add("model installed", "PASS", settings.model)
            live = True
        else:
            add("model installed", "FAIL", f"run: ollama pull {settings.model}")
    except OllamaError as exc:
        add("server reachable", "FAIL", str(exc))
        add("model installed", "SKIPPED", "server not reachable")

    if live and facts is not None:
        for question in QUESTIONS:
            try:
                answer = client.ask(question, facts)
                flagged = answer.warnings or ["none"]
                add(f"live answer: {question[:45]}", "PASS", f"unsupported-number warnings: {flagged}; answer: {answer.text[:200]!r}")
            except OllamaError as exc:
                add(f"live answer: {question[:45]}", "FAIL", str(exc))
    elif live:
        add("live answers", "SKIPPED", "no cleaned dataset - run `python -m src.pipeline` first")
    else:
        add("live answers", "SKIPPED", "no live model available")

    # Always testable: the unsupported-number detector and the fallback path.
    sample = facts or {"dataset": {"avg_popularity": 40.0}}
    probe = find_unsupported_numbers("The average is 123456.789 and 40.0", sample)
    add("unsupported-number detection", "PASS" if probe == ["123456.789"] else "FAIL", f"flagged: {probe}")
    dead = OllamaClient(OllamaSettings(host="http://127.0.0.1:9", model=settings.model))
    fallback = answer_with_fallback("Which genre is most popular?", facts or {
        "top_genres_by_popularity": [], "settings": {}, "popularity_correlations": [], "top_artists_by_avg_popularity": []}, dead)
    add("fallback when Ollama is unreachable", "PASS" if fallback.source == "rule_based" and fallback.error else "FAIL",
        f"source={fallback.source}; message={str(fallback.error)[:120]}")
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Ollama integration.")
    parser.add_argument("--model")
    parser.add_argument("--host")
    args = parser.parse_args()
    cfg = load_config()
    if args.model:
        cfg["ollama"]["model"] = args.model
    if args.host:
        cfg["ollama"]["host"] = args.host
    settings = OllamaSettings.from_config(cfg)
    facts = None
    try:
        from src.data_loader import load_processed
        a = cfg["analysis"]
        facts = compute_facts(load_processed(cfg), a["min_tracks_per_artist"], a["min_tracks_per_genre"], a["popular_quantile"])
    except FileNotFoundError:
        pass
    checks = run_checks(settings, facts)
    lines = ["# Ollama Check", "", f"Host `{settings.host}`, model `{settings.model}`", "", "| Check | Status | Detail |", "|---|---|---|"]
    lines += [f"| {c['check']} | {c['status']} | {c['detail'].replace('|', '/')} |" for c in checks]
    out = resolve_path(cfg["paths"]["reports_dir"]) / "ollama_check.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    for c in checks:
        print(f"[{c['status']:7}] {c['check']}: {c['detail'][:150]}")
    return 1 if any(c["status"] == "FAIL" for c in checks if "binary" not in c["check"] and "server" not in c["check"] and "model" not in c["check"]) else 0


if __name__ == "__main__":
    sys.exit(main())
