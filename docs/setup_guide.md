# Setup Guide (Windows)

Commands below work in **Command Prompt** or **PowerShell** unless noted. Run them from the project folder.

## 1. Install Python
1. Download Python 3.11 or newer from <https://www.python.org/downloads/windows/>.
2. In the installer tick **Add python.exe to PATH**, then *Install Now*.
3. Check: `python --version`

## 2. Create a virtual environment
```bat
cd path\to\Spotify-Music-Analytics
python -m venv .venv
.venv\Scripts\activate
```
(PowerShell may need once: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.)

## 3. Install dependencies
```bat
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 4. Download the dataset
Data is not bundled. Choose one:

| Option | Size | Kaggle page |
|---|---|---|
| Spotify Tracks Dataset (spec default) | ~114k rows | <https://www.kaggle.com/datasets/maharshipandya/-spotify-tracks-dataset> |
| Spotify 1 Million Tracks (large) | ~1M rows | search Kaggle for "Spotify 1 Million Tracks" by amitanshjoshi *(verify columns and licence)* |

**Manual:** open the page (free Kaggle login) -> *Download* -> unzip -> copy the `.csv` into `dataset\raw\`.

**Kaggle CLI (optional):** create an API token in Kaggle *Settings > API*, save it as `%USERPROFILE%\.kaggle\kaggle.json`, then
```bat
pip install kaggle
kaggle datasets download -d maharshipandya/-spotify-tracks-dataset -p dataset\raw --unzip
```
Keep one CSV in `dataset\raw\` (or set `SPOTIFY_RAW_FILE` in `.env`).

**Validate the file first** (structure, data types, missing values, duplicates):
```bat
python -m src.validate_dataset
```
Read `reports\dataset_validation.md`. If it says BLOCKED, add column aliases in `config\config.yaml`.

## 5. Run the pipeline (and/or the notebooks)
```bat
python -m src.pipeline --nrows 20000   :: quick trial
python -m src.pipeline                 :: full run
```
Outputs: `dataset\processed\tracks_clean.csv` (+ `.parquet`), `reports\data_quality_report.md`, `reports\key_findings.md`,
`dashboard\powerbi\data\*.csv`.

Notebooks (run in order 01 -> 02 -> 03):
```bat
jupyter lab
```
Open the `notebooks` folder. Charts are saved to `reports\figures\`.

## 6. Configure MySQL (optional)
1. Install MySQL Server 8 (MySQL Installer for Windows) and remember the root password.
2. Copy `.env.example` to `.env` and fill in `MYSQL_PASSWORD` etc.
3. Create database + tables and load the data:
```bat
python -m src.database_load
```
`database_load` creates the database, runs `sql\02_create_tables.sql` and streams the cleaned CSV in chunks.

## 7. Execute SQL scripts
```bat
mysql -u root -p -e "source sql/01_create_database.sql"
mysql -u root -p -e "source sql/02_create_tables.sql"
mysql -u root -p spotify_analytics -e "source sql/03_data_validation.sql"
mysql -u root -p spotify_analytics -e "source sql/04_basic_analysis.sql"
mysql -u root -p spotify_analytics -e "source sql/05_advanced_analysis.sql"
```
**Automated verification on your server** (writes a real report, nothing pre-filled):
```bat
python -m src.mysql_verify --setup --load
type reports\mysql_test_report.md
```
(Or open the files in MySQL Workbench and run query by query - recommended, results are easier to read.)
Fast alternative to the Python loader: the `LOAD DATA LOCAL INFILE` block at the end of `sql\02_create_tables.sql`
(needs `local_infile` enabled). Check Q01 in `03_data_validation.sql` equals `rows_clean` in the quality report.

## 8. Power BI
1. Install Power BI Desktop (Microsoft Store). Windows only.
2. Make sure `dashboard\powerbi\data\` exists (created by the pipeline).
3. *Home > Transform data > Manage Parameters* -> add `DataFolder` (see `dashboard\powerbi\load_data.pq`), then add the five queries.
4. *View > Themes > Browse for themes* -> `dashboard\powerbi\spotify_theme.json`.
5. Build relationships and measures from `data_model.md` and `dax_measures.md`; follow `docs\dashboard_documentation.md` for the pages.

## 9. Streamlit app (optional)
```bat
streamlit run dashboard\streamlit_app.py
```
Opens <http://localhost:8501>. It needs the cleaned data from step 5.

## 10. Ollama (optional)
1. Install from <https://ollama.com/download/windows>.
2. Download a model: `ollama pull llama3.1` (any local model works; set `OLLAMA_MODEL` in `.env` or type it in the app).
3. Make sure the server runs (the Windows app starts it; otherwise `ollama serve`). Check: `curl.exe http://localhost:11434/api/tags`
4. In the Streamlit page **Ask the Data (Ollama)** tick *Use Ollama* and press *Check Ollama connection*.

Run `python -m src.ollama_check` for a full check (binary, server, model, grounded answers, fallback).

If Ollama is off or the model is missing you get a clear message plus a rule-based answer - nothing else breaks.

## 11. Run the tests
```bat
pytest -q
```
or without pytest: `python -m unittest discover -s tests -t .`

Expected: all tests pass; one Streamlit test is skipped if Streamlit is not installed.
Tests use small **synthetic** data - they check code, not Spotify facts.

## Troubleshooting
| Symptom | Fix |
|---|---|
| `No raw CSV found` | put the CSV into `dataset\raw\` or set `SPOTIFY_RAW_FILE` |
| `Dataset is missing required columns` | the file's columns differ; add aliases under `column_aliases` in `config\config.yaml` |
| `MemoryError` on huge files | run with `--nrows`, close other apps, or use the 114k dataset |
| MySQL `Access denied` | check `.env`; MySQL 8 needs the `cryptography` package (in requirements) |
| `LOAD DATA LOCAL INFILE` disabled | `SET GLOBAL local_infile = 1;` and connect with `--local-infile=1`, or use `python -m src.database_load` |
