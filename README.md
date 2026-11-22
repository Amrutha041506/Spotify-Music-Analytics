# 🎧 Spotify Music Analytics – End-to-End Data Analysis

Python · SQL (MySQL 8) · Power BI · Streamlit · optional local AI (Ollama)

> **Transparency note.** This package was built and tested in an environment with **no internet, MySQL, Power BI, Jupyter,
> Streamlit or Ollama**, so the real Kaggle data was never analysed and several components could only be tested partially.
> Every number in the project is computed *when you run it* on your own download. This README contains **no results,
> metrics or screenshots** that were not produced by code - see [Actual testing results](#actual-testing-results) and
> [`docs/testing_report.md`](docs/testing_report.md).

## 1. Project overview
A complete analytics project on Spotify track data: cleaning pipeline, 20-question EDA, 50 documented SQL queries,
Power BI model/DAX/theme, a Streamlit explorer and an optional Ollama Q&A assistant grounded in computed facts.
It supports the ~114k-track Kaggle dataset **and** a ~1M-track dataset (chunked loading, Parquet, indexes, sampled plots).

## 2. Business problem
A streaming or recommendation team wants to know which genres, artists and sound characteristics go with high popularity,
and wants a repeatable way to explore the answer without writing code each time.

## 3. Objectives
* Discover popular tracks, artists and genres · compare genre audio profiles · measure associations between features and popularity
* Demonstrate Python, SQL, statistics, visualisation and BI skills · never overstate correlation as causation

## 4. Dataset source
| Dataset | Rows | Link |
|---|---:|---|
| Spotify Tracks Dataset (original brief) | ~114k | <https://www.kaggle.com/datasets/maharshipandya/-spotify-tracks-dataset> |
| Spotify 1 Million Tracks (large option) | ~1M | search Kaggle: "Spotify 1 Million Tracks" (amitanshjoshi) – verify before use |

Not bundled. Follow `docs/setup_guide.md`. Respect each dataset's licence.

## 5. Dataset description
Track metadata (id, name, artists, album, genre), `popularity` (0-100), `duration_ms`, `explicit` and Spotify audio features
(danceability, energy, key, loudness, mode, speechiness, acousticness, instrumentalness, liveness, valence, tempo, time signature).
Full field list and cleaning rules: [`docs/data_dictionary.md`](docs/data_dictionary.md).

## 6. Technologies
| Area | Tools |
|---|---|
| Analysis | Python 3.11+, pandas, NumPy, Matplotlib, Seaborn, JupyterLab |
| Database | MySQL 8, SQLAlchemy, PyMySQL |
| BI | Power BI Desktop (DAX, Power Query) |
| Apps | Streamlit |
| Optional AI | Ollama (llama3.1 or any local model) via REST API |
| Quality | pytest / unittest, YAML config, `.env` |

## 7. Architecture
```
Kaggle CSV ──► src.data_loader ──► src.data_cleaning ──► dataset/processed/tracks_clean.(csv|parquet)
 (raw/)        chunked read         rules + report          │
                                                            ├─► notebooks 01-03 (EDA, figures → reports/figures)
                                                            ├─► src.insights ─► reports/key_findings.md
                                                            │        └─► src.ollama_service (optional Q&A)
                                                            ├─► src.database_load ─► MySQL ─► sql/03-05 queries
                                                            ├─► src.powerbi_export ─► dashboard/powerbi/data ─► Power BI
                                                            └─► dashboard/streamlit_app.py
```

## 8. Folder structure
```
Spotify-Music-Analytics/
├── config/config.yaml          settings (paths, thresholds, Ollama)
├── dataset/{raw,processed}/    data (git-ignored)
├── notebooks/                  01_data_understanding · 02_data_cleaning · 03_exploratory_data_analysis
├── src/                        data_loader · data_cleaning · eda · insights · database · database_load
│                               ollama_service · powerbi_export · pipeline · config · sql_tools
│                               validate_dataset · mysql_verify · ollama_check
├── sql/                        01_create_database … 05_advanced_analysis (50 queries)
├── dashboard/                  streamlit_app.py · powerbi/ (theme, DAX, model, Power Query) · assets/
├── tests/                      cleaning, validation, insights, SQL, Ollama, notebooks, imports, Streamlit
├── docs/                       requirements · data dictionary · SQL docs · dashboard docs · setup guide
│                               testing_report · project_completion_report
├── reports/                    generated quality report, key findings, figures (git-ignored)
├── README.md · requirements.txt · .env.example · .gitignore · LICENSE
```

## 9. Data cleaning process
Trim text → coerce numerics → drop range-invalid rows → blank invalid tempo/time-signature/year → drop rows missing identifiers
or core values → remove exact duplicates → keep the most popular row per `(track_id, track_genre)` → derive `primary_artist`,
`duration_min`, `is_duration_outlier` (flagged, not deleted) → validate → write cleaned data and `reports/data_quality_report.md`.
Details: [`docs/data_dictionary.md`](docs/data_dictionary.md#cleaning-rules-srcdata_cleaningpy).

## 10. Exploratory data analysis
`notebooks/03_exploratory_data_analysis.ipynb` answers 20 questions (top tracks/artists/genres, danceability, energy, duration,
energy/danceability/acousticness vs popularity, explicit share and popularity, distributions, instrumentalness, valence,
correlation matrix, profile of popular songs). Every chart has a title, axis labels and an interpretation line that is **printed from the
computed values** and states associations only.

## 11. SQL analysis
50 queries with a question and explanation each (portable MySQL 8 / SQLite SQL): validation (Q01-10), basic aggregates (Q11-28), joins, subqueries, CTEs, `RANK`,
`DENSE_RANK`, `ROW_NUMBER`, `NTILE`, `LAG`, `PERCENT_RANK` (Q29-50). See [`docs/sql_documentation.md`](docs/sql_documentation.md).

## 12. Power BI dashboard
Three pages (Overview · Artist & Genre · Audio Features), Spotify dark/green theme, slicers for genre, artist, popularity, explicit.
Power BI-ready CSVs, Power Query, data model, DAX and layout are provided; the `.pbix` itself is **not** included
([why](docs/dashboard_documentation.md)).

## 13. Business questions answered
Which genres/artists/tracks are most popular? Which genres are most danceable/energetic/positive/instrumental? How long are songs?
Do energy, danceability or acousticness move with popularity? Is explicit content more or less popular? What do top-10 % tracks look like?

## 14. Key findings
**None are pre-written.** After you run the pipeline, they are generated into `reports/key_findings.md` (and printed at the end of notebook 03):

```bat
python -m src.pipeline
type reports\key_findings.md
```
Paste your own results here once you have run the project:

| Question | Your result |
|---|---|
| Most popular genre (avg) | _run the pipeline_ |
| Feature most associated with popularity | _run the pipeline_ |

## 15. Screenshots
**No screenshots are included**: Power BI and Streamlit could not be run where this package was built, and fabricated images would be misleading.
After you run them, save real captures to `dashboard/assets/` (e.g. `streamlit_overview.png`, `powerbi_overview.png`) and link them here.

## 16. Optional Ollama integration
```bat
ollama pull llama3.1
set OLLAMA_MODEL=llama3.1
streamlit run dashboard\streamlit_app.py     :: page "Ask the Data (Ollama)"
```
```python
from src.ollama_service import OllamaClient, OllamaSettings, answer_with_fallback
from src.insights import compute_facts
from src.data_loader import load_processed

facts = compute_facts(load_processed())
print(answer_with_fallback("Give me five important business insights", facts, OllamaClient(OllamaSettings(model="llama3.1"))).text)
```
Safeguards: the model only receives pre-computed facts; the system prompt forbids invented numbers and causal wording; replies are
scanned and unmatched numbers are flagged; any Ollama failure returns a clear message plus a rule-based answer (`src/insights.py`).

## 17. Installation
```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

## 18. How to run
```bat
:: 1. put the Kaggle CSV in dataset\raw\
python -m src.pipeline                      :: clean + reports + Power BI tables
jupyter lab                                 :: notebooks 01 → 03
python -m src.database_load                 :: optional MySQL load
streamlit run dashboard\streamlit_app.py    :: optional app
pytest -q                                   :: tests
```

## 19. MySQL configuration
Set `MYSQL_*` in `.env`; run `python -m src.database_load` or the scripts in `sql/` (see `docs/setup_guide.md` §6-7).
Table `tracks` has composite PK `(track_id, track_genre)` and indexes on genre, artist, popularity, year.

## 20. Power BI setup
`dashboard/powerbi/load_data.pq` → `data_model.md` → `dax_measures.md` → `spotify_theme.json` → layout in `docs/dashboard_documentation.md`.

## Actual testing results
Full detail (component, test, result, errors fixed, limitations): [`docs/testing_report.md`](docs/testing_report.md).

| Item | Status |
|---|---|
| Automated suite | ✅ **92 tests pass, 1 skipped** (`python -m unittest discover -s tests -t .`) - all on **synthetic** data |
| Pipeline scale | ✅ synthetic 1,000,000-row CSV -> 1,000,000 clean rows in **51.8 s**, **0.94 GB** peak RAM (sandbox; real data may differ) |
| Notebooks | ✅ all code cells run in order (via `exec`); notebook structure fixed (cell ids). ⚠️ **not run in real Jupyter** |
| SQL on SQLite | ✅ **50/50** queries execute; Q46 and several aggregates match pandas |
| SQL on **MySQL 8** | ❌ **not tested** - run `python -m src.mysql_verify --setup --load` |
| Streamlit | ✅ page logic of all 6 pages (mocked `streamlit`). ❌ **real `streamlit run` not tested** |
| Ollama | ✅ client logic (mocks + real refused connection), number checker, fallback. ❌ **no live model tested** |
| Power BI | ✅ static DAX/M/model cross-checks. ❌ **no `.pbix`, M/DAX not run in Power BI Desktop, no screenshots** |
| Real Kaggle data | ❌ not available offline - run `python -m src.validate_dataset` on your download |

### Verify it yourself (these commands generate the real evidence)
```bat
python -m src.validate_dataset                    :: structure, types, missing, duplicates of YOUR csv
python -m src.pipeline
python -m src.mysql_verify --setup --load         :: real MySQL 8 results -> reports\mysql_test_report.md
python -m src.ollama_check                        :: Ollama installed/running/model/grounding -> reports\ollama_check.md
streamlit run dashboard\streamlit_app.py
pytest -q
```

## 21. Future improvements
Parquet-first Power BI model · artist-level dimension handling for multi-artist tracks · time-series analysis with the `year` column ·
audio-feature clustering · popularity prediction model with proper validation · scheduled refresh · CI for tests.

## 22. Limitations
Popularity is a point-in-time score; the data is a sample; correlations are not causal; genre labels are dataset-specific;
decisions such as dropping rather than imputing rows are documented but debatable (configurable in `config/config.yaml`).

## 23. Author
**Your Name** · your.email@example.com · [GitHub](https://github.com/your-username) · [LinkedIn](https://linkedin.com/in/your-profile)

Licensed under the MIT License (see `LICENSE`).
