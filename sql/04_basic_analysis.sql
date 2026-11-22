-- =====================================================================
-- 04_basic_analysis.sql  -  Basic analysis queries (Q11-Q28)
-- Aggregates, GROUP BY / HAVING, filtering, sorting.
-- Note: genre-level averages use all (track, genre) rows; artist/track-level
-- questions group by track_id so multi-genre tracks are not over-counted
-- (except where noted).
-- =====================================================================
-- USE spotify_analytics;

-- ---------------------------------------------------------------------
-- Q11 | Top 10 tracks by popularity
-- Question: What are the 10 most popular tracks?
-- Explanation: Groups by track so a multi-genre track appears once; ties are broken by name.
-- Concepts: GROUP BY, MAX, ORDER BY, LIMIT
-- ---------------------------------------------------------------------
SELECT track_id, track_name, primary_artist, MAX(popularity) AS popularity
FROM tracks
GROUP BY track_id, track_name, primary_artist
ORDER BY popularity DESC, track_name
LIMIT 10;

-- ---------------------------------------------------------------------
-- Q12 | Top artists by average popularity
-- Question: Which artists have the highest average popularity (at least 5 tracks)?
-- Explanation: The HAVING filter prevents one-hit artists from dominating the ranking.
--              AVG runs over rows, so a track listed in two genres counts twice.
-- Concepts: GROUP BY, HAVING, AVG, COUNT(DISTINCT)
-- ---------------------------------------------------------------------
SELECT primary_artist,
       COUNT(DISTINCT track_id) AS track_count,
       ROUND(AVG(popularity), 2) AS avg_popularity
FROM tracks
GROUP BY primary_artist
HAVING COUNT(DISTINCT track_id) >= 5
ORDER BY avg_popularity DESC, track_count DESC
LIMIT 10;

-- ---------------------------------------------------------------------
-- Q13 | Average popularity by genre
-- Question: Which genres are the most popular on average?
-- Explanation: Genres with fewer than 20 tracks are excluded because their averages are unstable.
-- Concepts: GROUP BY, HAVING, AVG
-- ---------------------------------------------------------------------
SELECT track_genre,
       COUNT(DISTINCT track_id) AS track_count,
       ROUND(AVG(popularity), 2) AS avg_popularity
FROM tracks
GROUP BY track_genre
HAVING COUNT(DISTINCT track_id) >= 20
ORDER BY avg_popularity DESC
LIMIT 20;

-- ---------------------------------------------------------------------
-- Q14 | Highest-energy songs
-- Question: Which 10 tracks have the highest energy?
-- Explanation: Many tracks can tie at the maximum, so popularity and name are used as tie-breakers.
-- Concepts: ORDER BY multiple columns, LIMIT
-- ---------------------------------------------------------------------
SELECT track_name, primary_artist, track_genre, energy, popularity
FROM tracks
ORDER BY energy DESC, popularity DESC, track_name
LIMIT 10;

-- ---------------------------------------------------------------------
-- Q15 | Most danceable songs
-- Question: Which 10 tracks have the highest danceability?
-- Explanation: Same pattern as Q14 for a different feature.
-- Concepts: ORDER BY, LIMIT
-- ---------------------------------------------------------------------
SELECT track_name, primary_artist, track_genre, danceability, popularity
FROM tracks
ORDER BY danceability DESC, popularity DESC, track_name
LIMIT 10;

-- ---------------------------------------------------------------------
-- Q16 | Artists with more than 50 tracks
-- Question: Which artists have more than 50 distinct tracks?
-- Explanation: Identifies prolific artists. May return no rows on small samples of the data.
-- Concepts: GROUP BY, HAVING
-- ---------------------------------------------------------------------
SELECT primary_artist, COUNT(DISTINCT track_id) AS track_count
FROM tracks
GROUP BY primary_artist
HAVING COUNT(DISTINCT track_id) > 50
ORDER BY track_count DESC, primary_artist;

-- ---------------------------------------------------------------------
-- Q17 | Songs longer than 5 minutes
-- Question: Which are the longest tracks over 5 minutes?
-- Explanation: Filters with WHERE before sorting; limited to 20 rows for readability.
-- Concepts: WHERE, ORDER BY, LIMIT
-- ---------------------------------------------------------------------
SELECT track_name, primary_artist, track_genre, duration_min
FROM tracks
WHERE duration_min > 5
ORDER BY duration_min DESC, track_name
LIMIT 20;

-- ---------------------------------------------------------------------
-- Q18 | Share of tracks longer than 5 minutes
-- Question: What percentage of tracks last more than 5 minutes?
-- Explanation: 100.0 forces decimal division in both MySQL and SQLite.
-- Concepts: SUM + CASE, percentage calculation
-- ---------------------------------------------------------------------
SELECT SUM(CASE WHEN duration_min > 5 THEN 1 ELSE 0 END) AS long_tracks,
       COUNT(*) AS all_tracks,
       ROUND(100.0 * SUM(CASE WHEN duration_min > 5 THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_long_tracks
FROM tracks;

-- ---------------------------------------------------------------------
-- Q19 | Average danceability by genre
-- Question: Which genres are the most danceable?
-- Explanation: Genre means of a 0-1 feature, with a minimum-size filter.
-- Concepts: GROUP BY, HAVING, AVG
-- ---------------------------------------------------------------------
SELECT track_genre, ROUND(AVG(danceability), 3) AS avg_danceability, COUNT(*) AS track_rows
FROM tracks
GROUP BY track_genre
HAVING COUNT(*) >= 20
ORDER BY avg_danceability DESC
LIMIT 15;

-- ---------------------------------------------------------------------
-- Q20 | Average energy by genre
-- Question: Which genres have the highest average energy?
-- Explanation: Mirrors Q19 for energy.
-- Concepts: GROUP BY, HAVING, AVG
-- ---------------------------------------------------------------------
SELECT track_genre, ROUND(AVG(energy), 3) AS avg_energy, COUNT(*) AS track_rows
FROM tracks
GROUP BY track_genre
HAVING COUNT(*) >= 20
ORDER BY avg_energy DESC
LIMIT 15;

-- ---------------------------------------------------------------------
-- Q21 | Average valence (positivity) by genre
-- Question: Which genres sound the most positive?
-- Explanation: Valence near 1 means a happier/more cheerful sounding track.
-- Concepts: GROUP BY, HAVING, AVG
-- ---------------------------------------------------------------------
SELECT track_genre, ROUND(AVG(valence), 3) AS avg_valence, COUNT(*) AS track_rows
FROM tracks
GROUP BY track_genre
HAVING COUNT(*) >= 20
ORDER BY avg_valence DESC
LIMIT 15;

-- ---------------------------------------------------------------------
-- Q22 | Average instrumentalness by genre
-- Question: Which genres are the most instrumental?
-- Explanation: Instrumentalness is heavily skewed toward 0, so compare it only across genres.
-- Concepts: GROUP BY, HAVING, AVG
-- ---------------------------------------------------------------------
SELECT track_genre, ROUND(AVG(instrumentalness), 3) AS avg_instrumentalness, COUNT(*) AS track_rows
FROM tracks
GROUP BY track_genre
HAVING COUNT(*) >= 20
ORDER BY avg_instrumentalness DESC
LIMIT 15;

-- ---------------------------------------------------------------------
-- Q23 | Explicit-content share
-- Question: What percentage of tracks are explicit?
-- Explanation: COUNT(explicit) ignores NULLs, so tracks without a flag do not distort the share.
--              Returns NULL percentages for datasets that have no explicit column.
-- Concepts: SUM, COUNT(column), percentage calculation
-- ---------------------------------------------------------------------
SELECT SUM(explicit) AS explicit_rows,
       COUNT(explicit) AS rows_with_flag,
       ROUND(100.0 * SUM(explicit) / NULLIF(COUNT(explicit), 0), 2) AS explicit_pct
FROM tracks;

-- ---------------------------------------------------------------------
-- Q24 | Explicit vs non-explicit popularity
-- Question: Do explicit tracks have a different average popularity?
-- Explanation: Describes a difference only; it does not show that explicitness affects popularity.
-- Concepts: WHERE IS NOT NULL, GROUP BY, AVG
-- ---------------------------------------------------------------------
SELECT explicit, COUNT(*) AS track_rows, ROUND(AVG(popularity), 2) AS avg_popularity
FROM tracks
WHERE explicit IS NOT NULL
GROUP BY explicit
ORDER BY explicit;

-- ---------------------------------------------------------------------
-- Q25 | Popularity distribution
-- Question: How many tracks fall in each popularity band?
-- Explanation: CASE builds readable bands; the leading digits keep the sort order correct.
-- Concepts: CASE, GROUP BY, COUNT
-- ---------------------------------------------------------------------
WITH banded AS (
    SELECT CASE WHEN popularity < 20 THEN '1: 00-19'
                WHEN popularity < 40 THEN '2: 20-39'
                WHEN popularity < 60 THEN '3: 40-59'
                WHEN popularity < 80 THEN '4: 60-79'
                ELSE '5: 80-100' END AS popularity_band
    FROM tracks
)
SELECT popularity_band, COUNT(*) AS track_rows
FROM banded
GROUP BY popularity_band
ORDER BY popularity_band;

-- ---------------------------------------------------------------------
-- Q26 | Overall duration statistics
-- Question: What are the average, shortest and longest track durations in minutes?
-- Explanation: Uses the derived duration_min column.
-- Concepts: AVG, MIN, MAX
-- ---------------------------------------------------------------------
SELECT ROUND(AVG(duration_min), 3) AS avg_duration_min,
       MIN(duration_min) AS min_duration_min,
       MAX(duration_min) AS max_duration_min
FROM tracks;

-- ---------------------------------------------------------------------
-- Q27 | Tracks per release year
-- Question: How many tracks exist for each year?
-- Explanation: Only meaningful for datasets with a year column (e.g. the 1M-track file);
--              returns no rows for the 114k dataset.
-- Concepts: WHERE IS NOT NULL, GROUP BY, ORDER BY
-- ---------------------------------------------------------------------
SELECT year, COUNT(*) AS track_rows
FROM tracks
WHERE year IS NOT NULL
GROUP BY year
ORDER BY year;

-- ---------------------------------------------------------------------
-- Q28 | Major vs minor mode
-- Question: How do major (1) and minor (0) tracks compare on popularity and valence?
-- Explanation: CASE translates the 0/1 mode flag into labels.
-- Concepts: CASE, GROUP BY, AVG
-- ---------------------------------------------------------------------
WITH labelled AS (
    SELECT CASE WHEN `mode` = 1 THEN 'Major' ELSE 'Minor' END AS musical_mode,
           popularity, valence
    FROM tracks
)
SELECT musical_mode,
       COUNT(*) AS track_rows,
       ROUND(AVG(popularity), 2) AS avg_popularity,
       ROUND(AVG(valence), 3) AS avg_valence
FROM labelled
GROUP BY musical_mode
ORDER BY musical_mode;
