# Project Requirements

## 1. Business requirements
* BR-1 Understand which genres, artists and tracks perform best on Spotify popularity.
* BR-2 Understand how audio characteristics relate to popularity (association, not causation).
* BR-3 Provide material a music-recommendation or editorial team could use to ask better questions.
* BR-4 Provide self-service exploration (Power BI, Streamlit) for non-programmers.

## 2. Functional requirements
| ID | Requirement |
|---|---|
| FR-1 | Load a raw Spotify tracks CSV (114k or ~1M rows), auto-detecting the file and mapping column aliases |
| FR-2 | Validate columns and data types; fail clearly when required columns are missing |
| FR-3 | Handle missing values, duplicates, invalid values and outliers by documented rules |
| FR-4 | Convert duration to minutes and write the cleaned dataset (CSV, plus Parquet when available) |
| FR-5 | Produce a data-quality report (Markdown + JSON) with counts for every step |
| FR-6 | Notebooks for data understanding, cleaning and 20 EDA questions with titled/labelled charts and interpretations |
| FR-7 | SQL scripts: database, tables with keys/indexes, CSV import, validation, and at least 25 documented queries (this project has 50) |
| FR-8 | Power BI-ready tables, theme, data model, DAX measures and layout instructions for a 3-page dashboard |
| FR-9 | Optional Streamlit app: overview, search, filters, charts, audio features, insights, optional Q&A |
| FR-10 | Optional Ollama Q&A grounded in computed facts, with number checking and a non-AI fallback |

## 3. Non-functional requirements
| ID | Requirement |
|---|---|
| NFR-1 | Reproducible: one command (`python -m src.pipeline`) regenerates every derived artefact |
| NFR-2 | Scalable: chunked CSV reading, integer downcasting, hexbin/sampled plots, indexed SQL tables |
| NFR-3 | No hard-coded paths; settings in `config/config.yaml`; secrets only in `.env` |
| NFR-4 | Core project works without Ollama, MySQL, Streamlit or Power BI |
| NFR-5 | Clear error messages (missing file, missing columns, Ollama down, MySQL unreachable) |
| NFR-6 | No fabricated results: all findings are computed from the user's data |
| NFR-7 | Windows-compatible instructions |

## 4. Technical requirements
Python 3.11+, pandas, NumPy, Matplotlib, Seaborn, JupyterLab, MySQL 8.0+, SQLAlchemy + PyMySQL,
Power BI Desktop (Windows), Streamlit, Ollama (optional), Git. Exact packages: `requirements.txt`.

## 5. Software prerequisites
Python 3.11+ (3.12 used for testing), Git, MySQL Server 8.0+ and MySQL Workbench *(optional)*, Power BI Desktop *(optional, Windows only)*,
Ollama *(optional)*, a Kaggle account to download the dataset.

## 6. Hardware requirements
| Dataset | RAM | Disk |
|---|---|---|
| 114k tracks | 4 GB | ~1 GB |
| ~1M tracks | 8 GB recommended (a 1M-row synthetic benchmark peaked at ~0.9 GB for the pipeline; the notebooks and Power BI need more) | ~2 GB (raw + cleaned + Power BI CSVs) |
| Ollama with an 8B model | 16 GB RAM recommended (GPU optional) | ~5 GB per model |

## 7. Dataset requirements
* A CSV with the required columns listed in `docs/data_dictionary.md`.
* Primary: Kaggle `maharshipandya/-spotify-tracks-dataset` (~114k). Large alternative: Kaggle Spotify 1 Million Tracks.
* Data is **not** bundled; download instructions are in `docs/setup_guide.md`. Check each dataset's Kaggle licence before redistributing it.

## 8. Expected deliverables
Source code (`src/`), three notebooks, five SQL scripts, Power BI assets, Streamlit app, optional Ollama service,
README, this document, data dictionary, SQL/dashboard documentation, setup guide, tests, ZIP archive.

## 9. Acceptance criteria
1. `python -m src.pipeline` finishes on the downloaded dataset and writes cleaned data, quality report and key findings.
2. `pytest` passes (Streamlit real-start test runs only if Streamlit is installed).
3. All three notebooks run top-to-bottom without errors.
4. SQL scripts 01-05 run on MySQL 8 (`python -m src.mysql_verify --setup --load` reports 0 failed queries); Q01 row count equals `rows_clean` in the quality report.
5. Power BI loads the five CSVs, relationships match `data_model.md`, KPI cards show values for the selected data.
6. The Streamlit app starts and every page renders.
7. With Ollama stopped, the Q&A page shows a clear message and a rule-based answer.

## 10. Project limitations
* Popularity is a snapshot tied to the collection date; it says nothing about causes.
* Datasets are Kaggle samples/snapshots, not the full Spotify catalogue, and may be biased toward genres or eras.
* Spotify has restricted audio-feature API access for new apps, so refreshing the data yourself may not be possible.
* A `.pbix` file is not included (see `dashboard/powerbi/`). Power BI steps were written, not executed, by the author of this package.
* LLM answers can be wrong; the number check only catches figures absent from the computed facts.
