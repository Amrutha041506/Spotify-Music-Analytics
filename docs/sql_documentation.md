# SQL Documentation

All scripts target **MySQL 8.0+** and the table `tracks` created by `sql/02_create_tables.sql`.

## Run order

| Order | File | Purpose |
|---|---|---|
| 1 | `01_create_database.sql` | create the `spotify_analytics` database |
| 2 | `02_create_tables.sql` | create `tracks` (PK `track_id, track_genre`), indexes, `popularity_band` lookup, CSV-import instructions |
| 3 | `03_data_validation.sql` | Q01-Q10 data quality checks |
| 4 | `04_basic_analysis.sql` | Q11-Q28 aggregates, GROUP BY / HAVING |
| 5 | `05_advanced_analysis.sql` | Q29-Q50 joins, subqueries, CTEs, window functions |

```bat
mysql -u root -p -e "source sql/01_create_database.sql"
mysql -u root -p -e "source sql/02_create_tables.sql"
python -m src.database_load
mysql -u root -p spotify_analytics -e "source sql/03_data_validation.sql"
```

## Table `tracks`

One row per `(track_id, track_genre)`. Column names equal the cleaned CSV headers (`src/data_loader.py::CLEAN_COLUMNS`). `key` and `mode` are quoted with backticks in DDL because `KEY` is a reserved word in MySQL. `album_name`, `year`, `explicit` are NULL for datasets that lack them, so Q23, Q24, Q27, Q39 and Q47 return empty/NULL results on those datasets.

## Verification status (read this)

| Check | Result | Where |
|---|---|---|
| All 50 queries execute on **SQLite 3.45** loaded with the project DDL and *synthetic* cleaned data | ✅ 50/50 | `tests/test_sql_queries.py` |
| Q46 (Pearson r) equals pandas' correlation on the same data | ✅ | `test_q46_matches_pandas_pearson` |
| Genre averages, explicit share, band and decile counts equal pandas | ✅ | `test_sql_results_match_pandas` |
| Heuristic MySQL-8 lint (`^` XOR, `||`, FULL JOIN, LIMIT in IN, reserved aliases, unquoted `key`) | ✅ nothing found | `src/sql_tools.py::lint_mysql_compat` |
| **Execution on a real MySQL 8 server** | ❌ **not done** - no MySQL available where this was built | run `python -m src.mysql_verify --setup --load` |

### What changed to reduce MySQL risk
* Q25, Q28, Q38, Q42, Q43 grouped by a `CASE` expression repeated in `GROUP BY`. They now compute the label in a CTE and `GROUP BY` the named column (unambiguous under `ONLY_FULL_GROUP_BY`).
* Q46 previously used `STDDEV_POP` and was never executed anywhere. It is now plain `AVG`/`SQRT` arithmetic that runs on both engines. The old `^` operator is deliberately avoided (it is XOR in MySQL).

### Verify on your MySQL 8 server
```bat
python -m src.pipeline
python -m src.mysql_verify --setup --load   :: creates tables (drops existing `tracks`), loads data, runs all 50 queries
type reports\mysql_test_report.md           :: real results: server version, sql_mode, indexes, per-query status/rows/seconds
python -m src.mysql_verify --dry-run        :: no database: parse + lint only
```

## Query catalogue (50 queries)

| ID | File | Question | Explanation |
|---|---|---|---|
| Q01 | 03_data_validation.sql | How many rows were loaded? | Compare with `rows_clean` in reports/data_quality_report.md - they must match. |
| Q02 | 03_data_validation.sql | How many distinct tracks, artists and genres exist? | total_rows can exceed unique_tracks when a track is listed under several genres. |
| Q03 | 03_data_validation.sql | How many NULLs does each nullable column contain? | album_name, year, explicit are NULL for datasets that lack them; tempo and |
| Q04 | 03_data_validation.sql | Are any 0-1 audio features outside the valid range? | danceability, energy, speechiness, acousticness, instrumentalness, liveness and |
| Q05 | 03_data_validation.sql | Is popularity within 0-100 and what does its spread look like? | Confirms the CHECK constraint held and gives a first feel for the distribution. |
| Q06 | 03_data_validation.sql | Does any track_id + genre combination appear more than once? | The primary key prevents this, so the result must be empty. Useful as a |
| Q07 | 03_data_validation.sql | Which tracks appear in more than one genre? | Informational. Explains why track-level counts use COUNT(DISTINCT track_id). |
| Q08 | 03_data_validation.sql | Is duration_min consistent with duration_ms, and how long are the longest/shortest tracks? | duration_min was derived as duration_ms / 60000. `inconsistent_rows` must be 0. |
| Q09 | 03_data_validation.sql | Which time signatures occur and how often? | Values should only be 1-7 (or NULL). Most music is 4/4, so a skewed result is expected. |
| Q10 | 03_data_validation.sql | Which song name + artist combinations have more than one track_id? | Informational. Re-releases and remasters often share a name. These rows are NOT |
| Q11 | 04_basic_analysis.sql | What are the 10 most popular tracks? | Groups by track so a multi-genre track appears once; ties are broken by name. |
| Q12 | 04_basic_analysis.sql | Which artists have the highest average popularity (at least 5 tracks)? | The HAVING filter prevents one-hit artists from dominating the ranking. |
| Q13 | 04_basic_analysis.sql | Which genres are the most popular on average? | Genres with fewer than 20 tracks are excluded because their averages are unstable. |
| Q14 | 04_basic_analysis.sql | Which 10 tracks have the highest energy? | Many tracks can tie at the maximum, so popularity and name are used as tie-breakers. |
| Q15 | 04_basic_analysis.sql | Which 10 tracks have the highest danceability? | Same pattern as Q14 for a different feature. |
| Q16 | 04_basic_analysis.sql | Which artists have more than 50 distinct tracks? | Identifies prolific artists. May return no rows on small samples of the data. |
| Q17 | 04_basic_analysis.sql | Which are the longest tracks over 5 minutes? | Filters with WHERE before sorting; limited to 20 rows for readability. |
| Q18 | 04_basic_analysis.sql | What percentage of tracks last more than 5 minutes? | 100.0 forces decimal division in both MySQL and SQLite. |
| Q19 | 04_basic_analysis.sql | Which genres are the most danceable? | Genre means of a 0-1 feature, with a minimum-size filter. |
| Q20 | 04_basic_analysis.sql | Which genres have the highest average energy? | Mirrors Q19 for energy. |
| Q21 | 04_basic_analysis.sql | Which genres sound the most positive? | Valence near 1 means a happier/more cheerful sounding track. |
| Q22 | 04_basic_analysis.sql | Which genres are the most instrumental? | Instrumentalness is heavily skewed toward 0, so compare it only across genres. |
| Q23 | 04_basic_analysis.sql | What percentage of tracks are explicit? | COUNT(explicit) ignores NULLs, so tracks without a flag do not distort the share. |
| Q24 | 04_basic_analysis.sql | Do explicit tracks have a different average popularity? | Describes a difference only; it does not show that explicitness affects popularity. |
| Q25 | 04_basic_analysis.sql | How many tracks fall in each popularity band? | CASE builds readable bands; the leading digits keep the sort order correct. |
| Q26 | 04_basic_analysis.sql | What are the average, shortest and longest track durations in minutes? | Uses the derived duration_min column. |
| Q27 | 04_basic_analysis.sql | How many tracks exist for each year? | Only meaningful for datasets with a year column (e.g. the 1M-track file); |
| Q28 | 04_basic_analysis.sql | How do major (1) and minor (0) tracks compare on popularity and valence? | CASE translates the 0/1 mode flag into labels. |
| Q29 | 05_advanced_analysis.sql | How do tracks rank by popularity, with ties sharing a rank? | RANK() leaves gaps after ties (1,1,3...). Many tracks tie at the top scores. |
| Q30 | 05_advanced_analysis.sql | How do genres rank by average popularity without gaps in rank numbers? | DENSE_RANK() never skips numbers after ties; a window function can wrap an aggregate. |
| Q31 | 05_advanced_analysis.sql | Which three tracks lead each genre? | ROW_NUMBER() restarts for every genre (PARTITION BY); the CTE then keeps rn <= 3. |
| Q32 | 05_advanced_analysis.sql | Which genres beat the dataset-wide average popularity? | The scalar subquery in HAVING computes the global average once. |
| Q33 | 05_advanced_analysis.sql | Which tracks are at least 30 popularity points above their own genre's average? | INNER JOIN to a derived table of genre averages allows row-level comparison. |
| Q34 | 05_advanced_analysis.sql | How do average audio features change from low- to high-popularity bands? | INNER JOIN to the popularity_band lookup using a range condition (BETWEEN). |
| Q35 | 05_advanced_analysis.sql | Does every popularity band contain tracks (and which bands are empty)? | LEFT JOIN keeps bands with zero matching tracks; COUNT(t.track_id) then returns 0. |
| Q36 | 05_advanced_analysis.sql | How much of the catalogue do the largest genres make up? | SUM() OVER () gives the grand total; a running SUM ordered by size gives the cumulative share. |
| Q37 | 05_advanced_analysis.sql | What does each popularity decile look like? | NTILE(10) splits tracks into ten equal-size groups (1 = most popular). |
| Q38 | 05_advanced_analysis.sql | How do the most popular 10% of tracks differ in audio features from the rest? | Business question - "what do hits sound like?" Differences are associations, not causes. |
| Q39 | 05_advanced_analysis.sql | How does average popularity change from one release year to the next? | LAG() reads the previous year's value. Needs a year column (1M-track dataset). |
| Q40 | 05_advanced_analysis.sql | Which artists span the most genres? | Counts distinct genres per artist for artists with at least 10 tracks. |
| Q41 | 05_advanced_analysis.sql | How do genres rank on danceability, energy and valence at the same time? | Three RANK() windows over one CTE give a side-by-side comparison. |
| Q42 | 05_advanced_analysis.sql | Does average popularity differ between low-, mid- and high-energy tracks? | Banding a continuous feature is a simple way to inspect a relationship in SQL. |
| Q43 | 05_advanced_analysis.sql | How does acousticness relate to average popularity? | Same banding approach as Q42 for acousticness. |
| Q44 | 05_advanced_analysis.sql | Where does each established artist sit in the popularity distribution? | PERCENT_RANK() returns 0-1; artists need at least 5 tracks to be included. |
| Q45 | 05_advanced_analysis.sql | What is the longest track of every genre? | ROW_NUMBER() partitioned by genre and ordered by duration; keep rank 1. |
| Q46 | 05_advanced_analysis.sql | What is the linear correlation between energy and popularity? | Computes r = (E[xy] - E[x]E[y]) / (sigma_x * sigma_y) from plain AVG() terms and SQRT(), so it |
| Q47 | 05_advanced_analysis.sql | Which genres contain the highest share of explicit tracks? | Genres must have at least 20 rows with an explicit flag. Empty on datasets without 'explicit'. |
| Q48 | 05_advanced_analysis.sql | Which genres have the largest share of tracks with popularity >= 70? | A business-oriented view - where is a high-popularity track most likely to be found? |
| Q49 | 05_advanced_analysis.sql | How do tracks by artists with more than 50 tracks perform on average? | The IN subquery selects the prolific artists; the outer query aggregates their tracks. |
| Q50 | 05_advanced_analysis.sql | Which genres rank in the top half for popularity AND in the top half for energy? | Combines two RANK() windows in a CTE and filters on both - a recommendation-strategy style screen. |
