# Data Dictionary

## Supported source datasets

| Dataset (Kaggle) | Approx. rows | Notes |
|---|---:|---|
| Spotify Tracks Dataset - `maharshipandya/-spotify-tracks-dataset` | 114,000 | the dataset named in the original brief; has `explicit`, `album_name`, `track_genre`; no `year` |
| Spotify 1 Million Tracks - `amitanshjoshi/spotify-1million-tracks` *(verify the link on Kaggle)* | ~1,000,000 | has `year`, `genre`, `artist_name`; **no** `explicit` or `album_name`; includes an unnamed index column |

Column names are mapped by `column_aliases` in `config/config.yaml` (e.g. `artist_name -> artists`, `genre -> track_genre`).
Required columns must exist; optional columns (`album_name`, `explicit`, `year`) are added as empty when absent, and the
analyses that depend on them are skipped with a message.
Check the exact columns of the file you downloaded - dataset owners can change files after this project was written.

## Cleaned dataset columns (`dataset/processed/tracks_clean.csv`)

| Column | Type | Range / values | Description |
|---|---|---|---|
| `track_id` | text | - | Spotify track ID |
| `track_name` | text | - | Track title |
| `artists` | text | - | Artist(s); multiple artists separated by `;` in the 114k file |
| `primary_artist` | text | - | **derived**: first artist in `artists` |
| `album_name` | text, nullable | - | Album (missing values -> `Unknown Album` when the column exists) |
| `track_genre` | text | - | Genre label (missing -> `unknown`) |
| `year` | int, nullable | 1900 - next year | Release year (only in some datasets) |
| `popularity` | int | 0-100 | Spotify popularity score, derived from recent play counts at collection time |
| `duration_ms` | int | 1 - 3,600,000 | Duration in milliseconds |
| `duration_min` | decimal | - | **derived**: `duration_ms / 60000`, 3 decimals |
| `explicit` | 0/1, nullable | 0, 1 | 1 = explicit lyrics |
| `danceability` | float | 0-1 | Suitability for dancing (tempo, rhythm stability, beat strength) |
| `energy` | float | 0-1 | Intensity and activity |
| `key` | int | -1 - 11 | Pitch class (0 = C, 1 = C#...; -1 = no key detected) |
| `loudness` | float | -60 - 5 dB | Overall loudness |
| `mode` | int | 0, 1 | 1 = major, 0 = minor |
| `speechiness` | float | 0-1 | Presence of spoken words |
| `acousticness` | float | 0-1 | Confidence the track is acoustic |
| `instrumentalness` | float | 0-1 | Likelihood of no vocals |
| `liveness` | float | 0-1 | Presence of a live audience |
| `valence` | float | 0-1 | Musical positivity |
| `tempo` | float, nullable | 30 - 300 BPM | Estimated tempo (invalid values -> missing) |
| `time_signature` | int, nullable | 1-7 | Beats per bar (invalid values -> missing) |
| `is_duration_outlier` | 0/1 | 0, 1 | **derived**: 1 if `duration_min` > Q3 + 3 x IQR (row kept) |

## Cleaning rules (`src/data_cleaning.py`)

| Issue | Rule | Where reported |
|---|---|---|
| Whitespace / empty strings | trim / treat as missing | - |
| Non-numeric text in numeric column | coerce to missing | `non_numeric_values_coerced_to_missing` |
| `popularity` outside 0-100; 0-1 features outside 0-1; `loudness` outside -60..5; `duration_ms` <= 0 or > 60 min; `key` outside -1..11; `mode` not 0/1 | drop row | `invalid_value_counts` |
| `tempo` outside 30-300; `time_signature` outside 1-7; `year` outside 1900..next year | set value to missing, keep row | `invalid_value_counts` |
| Missing `track_id`, `track_name` or `artists` | drop row | `steps` |
| Missing any core numeric column | drop row | `steps` |
| Exact duplicate rows | drop | `steps` |
| Same `(track_id, track_genre)` more than once | keep highest-popularity row | `steps` |
| Same `track_id` in several genres | **keep** (different genre rows) | `tracks_in_multiple_genres` |
| Extreme durations | **flag, do not delete** | `duration_outliers_flagged` |

All thresholds live in `config/config.yaml` (`cleaning:`). Choices such as dropping versus imputing are judgement calls -
change them there if your analysis needs different rules. Every run writes `reports/data_quality_report.md` with exact counts.

## Analysis conventions

* Track-level questions (top tracks, averages, correlations) use **one row per `track_id`** (`eda.unique_tracks`).
* Genre-level questions use every `(track, genre)` row.
* Rankings require minimum counts (`min_tracks_per_artist = 5`, `min_tracks_per_genre = 20`) so tiny groups do not dominate.
* Correlation results are associations only.
