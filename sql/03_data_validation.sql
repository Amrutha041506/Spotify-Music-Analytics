-- =====================================================================
-- 03_data_validation.sql  -  Data validation queries (Q01-Q10)
-- Run after loading data. Most checks should return 0 / empty results
-- if the cleaning pipeline worked. Table: tracks (see 02_create_tables.sql)
-- =====================================================================
-- USE spotify_analytics;

-- ---------------------------------------------------------------------
-- Q01 | Row count
-- Question: How many rows were loaded?
-- Explanation: Compare with `rows_clean` in reports/data_quality_report.md - they must match.
-- Concepts: COUNT
-- ---------------------------------------------------------------------
SELECT COUNT(*) AS total_rows FROM tracks;

-- ---------------------------------------------------------------------
-- Q02 | Entity counts
-- Question: How many distinct tracks, artists and genres exist?
-- Explanation: total_rows can exceed unique_tracks when a track is listed under several genres.
-- Concepts: COUNT(DISTINCT)
-- ---------------------------------------------------------------------
SELECT COUNT(DISTINCT track_id)       AS unique_tracks,
       COUNT(DISTINCT primary_artist) AS unique_artists,
       COUNT(DISTINCT track_genre)    AS unique_genres
FROM tracks;

-- ---------------------------------------------------------------------
-- Q03 | NULL audit
-- Question: How many NULLs does each nullable column contain?
-- Explanation: album_name, year, explicit are NULL for datasets that lack them; tempo and
--              time_signature are NULL where the raw value was invalid. Non-nullable columns must be 0.
-- Concepts: SUM + CASE
-- ---------------------------------------------------------------------
SELECT SUM(CASE WHEN album_name     IS NULL THEN 1 ELSE 0 END) AS null_album_name,
       SUM(CASE WHEN year           IS NULL THEN 1 ELSE 0 END) AS null_year,
       SUM(CASE WHEN explicit       IS NULL THEN 1 ELSE 0 END) AS null_explicit,
       SUM(CASE WHEN tempo          IS NULL THEN 1 ELSE 0 END) AS null_tempo,
       SUM(CASE WHEN time_signature IS NULL THEN 1 ELSE 0 END) AS null_time_signature,
       SUM(CASE WHEN track_name     IS NULL THEN 1 ELSE 0 END) AS null_track_name,
       SUM(CASE WHEN popularity     IS NULL THEN 1 ELSE 0 END) AS null_popularity
FROM tracks;

-- ---------------------------------------------------------------------
-- Q04 | Audio-feature range check
-- Question: Are any 0-1 audio features outside the valid range?
-- Explanation: danceability, energy, speechiness, acousticness, instrumentalness, liveness and
--              valence are defined on 0-1. Every count should be 0.
-- Concepts: SUM + CASE, boolean logic
-- ---------------------------------------------------------------------
SELECT SUM(CASE WHEN danceability     < 0 OR danceability     > 1 THEN 1 ELSE 0 END) AS bad_danceability,
       SUM(CASE WHEN energy           < 0 OR energy           > 1 THEN 1 ELSE 0 END) AS bad_energy,
       SUM(CASE WHEN speechiness      < 0 OR speechiness      > 1 THEN 1 ELSE 0 END) AS bad_speechiness,
       SUM(CASE WHEN acousticness     < 0 OR acousticness     > 1 THEN 1 ELSE 0 END) AS bad_acousticness,
       SUM(CASE WHEN instrumentalness < 0 OR instrumentalness > 1 THEN 1 ELSE 0 END) AS bad_instrumentalness,
       SUM(CASE WHEN liveness         < 0 OR liveness         > 1 THEN 1 ELSE 0 END) AS bad_liveness,
       SUM(CASE WHEN valence          < 0 OR valence          > 1 THEN 1 ELSE 0 END) AS bad_valence
FROM tracks;

-- ---------------------------------------------------------------------
-- Q05 | Popularity range
-- Question: Is popularity within 0-100 and what does its spread look like?
-- Explanation: Confirms the CHECK constraint held and gives a first feel for the distribution.
-- Concepts: MIN, MAX, AVG, aggregate functions
-- ---------------------------------------------------------------------
SELECT MIN(popularity) AS min_popularity,
       MAX(popularity) AS max_popularity,
       ROUND(AVG(popularity), 2) AS avg_popularity,
       SUM(CASE WHEN popularity < 0 OR popularity > 100 THEN 1 ELSE 0 END) AS out_of_range_rows
FROM tracks;

-- ---------------------------------------------------------------------
-- Q06 | Duplicate (track_id, track_genre) pairs
-- Question: Does any track_id + genre combination appear more than once?
-- Explanation: The primary key prevents this, so the result must be empty. Useful as a
--              sanity check if the PK was dropped for a bulk load.
-- Concepts: GROUP BY, HAVING
-- ---------------------------------------------------------------------
SELECT track_id, track_genre, COUNT(*) AS occurrences
FROM tracks
GROUP BY track_id, track_genre
HAVING COUNT(*) > 1;

-- ---------------------------------------------------------------------
-- Q07 | Tracks listed under several genres
-- Question: Which tracks appear in more than one genre?
-- Explanation: Informational. Explains why track-level counts use COUNT(DISTINCT track_id).
-- Concepts: GROUP BY, HAVING, COUNT(DISTINCT)
-- ---------------------------------------------------------------------
SELECT track_id, COUNT(DISTINCT track_genre) AS genre_count
FROM tracks
GROUP BY track_id
HAVING COUNT(DISTINCT track_genre) > 1
ORDER BY genre_count DESC, track_id
LIMIT 20;

-- ---------------------------------------------------------------------
-- Q08 | Duration consistency
-- Question: Is duration_min consistent with duration_ms, and how long are the longest/shortest tracks?
-- Explanation: duration_min was derived as duration_ms / 60000. `inconsistent_rows` must be 0.
-- Concepts: arithmetic, ABS, aggregate functions
-- ---------------------------------------------------------------------
SELECT MIN(duration_min) AS shortest_min,
       MAX(duration_min) AS longest_min,
       SUM(CASE WHEN ABS(duration_min - duration_ms / 60000.0) > 0.001 THEN 1 ELSE 0 END) AS inconsistent_rows,
       SUM(is_duration_outlier) AS flagged_duration_outliers
FROM tracks;

-- ---------------------------------------------------------------------
-- Q09 | Time-signature distribution
-- Question: Which time signatures occur and how often?
-- Explanation: Values should only be 1-7 (or NULL). Most music is 4/4, so a skewed result is expected.
-- Concepts: GROUP BY, ORDER BY
-- ---------------------------------------------------------------------
SELECT time_signature, COUNT(*) AS track_rows
FROM tracks
GROUP BY time_signature
ORDER BY track_rows DESC;

-- ---------------------------------------------------------------------
-- Q10 | Possible duplicate songs with different IDs
-- Question: Which song name + artist combinations have more than one track_id?
-- Explanation: Informational. Re-releases and remasters often share a name. These rows are NOT
--              removed by the pipeline because they can be legitimately different releases.
-- Concepts: GROUP BY, HAVING, COUNT(DISTINCT)
-- ---------------------------------------------------------------------
SELECT track_name, primary_artist, COUNT(DISTINCT track_id) AS distinct_ids
FROM tracks
GROUP BY track_name, primary_artist
HAVING COUNT(DISTINCT track_id) > 1
ORDER BY distinct_ids DESC, track_name
LIMIT 20;
