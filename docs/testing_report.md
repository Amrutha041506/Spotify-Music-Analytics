# Testing Report

Everything below was actually executed in the build sandbox (Linux, Python 3.12, pandas 3.0, SQLite 3.45) unless marked
**NOT TESTED**. The sandbox had **no internet, MySQL, Power BI, Jupyter, Streamlit, Ollama, pytest or pyarrow**.
All test data is **synthetic** (`tests/synthetic.py`) - no real Spotify data was ever available, so nothing here says anything about Spotify music.

Automated suite: `python -m unittest discover -s tests -t .` -> **92 tests, OK, 1 skipped** (real-Streamlit start test; auto-runs when Streamlit is installed).
`pytest -q` runs the same tests but was not available here.

## Results by component

| Component | Test performed | Result | Errors found / fixed | Remaining limitation |
|---|---|---|---|---|
| Data pipeline | unit tests for cleaning rules (dupes, invalid, missing, outliers, idempotence, optional columns); chunked vs single read; round-trip I/O | ✅ pass | `track_id` could be read as a number (leading zeros lost) -> forced to text in loader and validator | not run on the real Kaggle files |
| Scale | full pipeline on a **synthetic** 1,000,000-row CSV (1M-dataset column layout) | ✅ 1,000,000 clean rows, **51.8 s, 0.94 GB peak RSS** | - | real data timing may differ; Parquet path not exercised (no pyarrow) |
| Notebooks | all code cells of 3 notebooks executed in order against synthetic data (`tests/test_notebooks.py`); structural nbformat checks | ✅ cells run; ≥18 figures written | **all notebooks declared nbformat 4.5 without cell `id`s (strict validators reject this) -> ids added** | **NOT run in real Jupyter** (not installed); rendering of `display()` output unverified |
| SQL (SQLite) | all **50** queries executed on SQLite with project DDL + synthetic data | ✅ 50/50 execute | - | SQLite is not MySQL |
| SQL (results) | Q46 vs pandas Pearson; genre averages, explicit %, band/decile counts vs pandas | ✅ match | Q46 used `STDDEV_POP`, never executed -> rewritten portably and now verified | - |
| SQL (MySQL-risk) | heuristic lint for MySQL 8 pitfalls; lint itself tested on known-bad snippets | ✅ nothing found | 5 queries grouped by a repeated `CASE` expression -> now group by CTE column | **MySQL 8 itself: NOT TESTED.** Use `python -m src.mysql_verify --setup --load` |
| MySQL loader / verifier | `split_sql_statements`, URL builder, verifier report logic (via SQLite executor) | ✅ logic | - | SQLAlchemy/PyMySQL path, `LOAD DATA`, PK/index creation **NOT TESTED** |
| Power BI assets | static cross-checks DAX <-> exported CSVs, M <-> CSVs, relationships, theme JSON; negative controls confirm the checks catch typos | ✅ pass | - | **PBIX not created; M/DAX/theme NOT run in Power BI Desktop; no screenshots** |
| Streamlit | page logic for all 6 pages driven with a mocked `streamlit` + synthetic data | ✅ pass | 4x `use_container_width` (deprecated in newer Streamlit) removed | **real `streamlit run` NOT TESTED**; layout/appearance unseen |
| Ollama | client logic with mocked HTTP; real refused connection; number checker; fallback; `src.ollama_check` run in sandbox | ✅ logic pass; checker reports "not installed / not reachable" | - | **never run against a real model**; number checker only catches numbers absent from facts |
| Dataset validation | `src.validate_dataset` on synthetic brief-style and 1M-style files | ✅ pass | - | **Kaggle URLs/columns NOT verified (no internet)**; ID-format check cannot prove data is real |
| Docs | SQL docs regenerated from the `.sql` files | ✅ | - | screenshots: none exist |

## Tests by file
`test_data_cleaning` 19 · `test_data_validation` 12 · `test_insights` 11 · `test_ollama_service` 11 · `test_sql_queries` 14 · `test_powerbi_assets` 8 ·
`test_verification_tools` 5 · `test_imports` 6 · plus `test_notebooks` and `test_streamlit_app` (mocked run + skipped real run).

## Failures encountered during testing (and fixes)
1. Mixed-type chunk comparison test failed (a stray text value gave different raw dtypes per chunk) -> test now compares the **cleaned** output, which is the real contract.
2. Fake-Streamlit test corrupted matplotlib imports (`patch.dict(sys.modules)` dropped lazily imported modules) -> patch only the `streamlit` key.
3. `track_id` numeric inference lost leading zeros (found by the new validator test) -> read as text.
4. A syntax error introduced while fixing (3) was caught immediately by the suite and corrected.

## Manual verification still required (not possible here)
| Item | Command / action |
|---|---|
| Real dataset structure | `python -m src.validate_dataset` after downloading the CSV |
| MySQL 8 | `python -m src.mysql_verify --setup --load` -> `reports\mysql_test_report.md` |
| Notebooks in Jupyter | `jupyter lab`, Run All on 01 -> 02 -> 03 (or `pip install nbconvert` then `jupyter nbconvert --to notebook --execute notebooks\*.ipynb --inplace`) |
| Streamlit | `pip install -r requirements.txt` then `streamlit run dashboard\streamlit_app.py`; click all six pages; `pytest tests/test_streamlit_app.py` |
| Ollama | `ollama pull llama3.1` then `python -m src.ollama_check` -> `reports\ollama_check.md` |
| Power BI | follow `docs/dashboard_documentation.md`; compare KPIs with `reports\key_findings.md`; save `.pbix`; take screenshots |
