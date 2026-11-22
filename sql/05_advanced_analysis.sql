-- =====================================================================
-- 05_advanced_analysis.sql  -  Advanced analysis queries (Q29-Q50)
-- Joins, subqueries, CTEs, window functions, ranking, business questions.
-- Every query uses portable SQL (MySQL 8 and SQLite 3.35+). No query is tagged @mysql-only any more.
-- =====================================================================
-- USE spotify_analytics;

-- ---------------------------------------------------------------------
-- Q29 | Popularity ranking with RANK()
-- Question: How do tracks rank by popularity, with ties sharing a rank?
-- Explanation: RANK() leaves gaps after ties (1,1,3...). Many tracks tie at the top scores.
-- Concepts: RANK() window function
-- ---------------------------------------------------------------------
SELECT track_name, primary_artist, popularity,
       RANK() OVER (ORDER BY popularity DESC) AS popularity_rank
FROM tracks
ORDER BY popularity_rank, track_name
LIMIT 20;

-- ---------------------------------------------------------------------
-- Q30 | Genre ranking with DENSE_RANK()
-- Question: How do genres rank by average popularity without gaps in rank numbers?
-- Explanation: DENSE_RANK() never skips numbers after ties; a window function can wrap an aggregate.
-- Concepts: DENSE_RANK(), GROUP BY, window over aggregate
-- ---------------------------------------------------------------------
SELECT track_genre,
       ROUND(AVG(popularity), 2) AS avg_popularity,
       DENSE_RANK() OVER (ORDER BY ROUND(AVG(popularity), 2) DESC) AS genre_rank
FROM tracks
GROUP BY track_genre
ORDER BY genre_rank, track_genre
LIMIT 20;

-- ---------------------------------------------------------------------
-- Q31 | Top 3 tracks within every genre
-- Question: Which three tracks lead each genre?
-- Explanation: ROW_NUMBER() restarts for every genre (PARTITION BY); the CTE then keeps rn <= 3.
-- Concepts: CTE, ROW_NUMBER(), PARTITION BY
-- ---------------------------------------------------------------------
WITH ranked AS (
    SELECT track_genre, track_name, primary_artist, popularity,
           ROW_NUMBER() OVER (PARTITION BY track_genre ORDER BY popularity DESC, track_name) AS rn
    FROM tracks
)
SELECT track_genre, rn AS rank_in_genre, track_name, primary_artist, popularity
FROM ranked
WHERE rn <= 3
ORDER BY track_genre, rn;

-- ---------------------------------------------------------------------
-- Q32 | Genres above the overall average popularity
-- Question: Which genres beat the dataset-wide average popularity?
-- Explanation: The scalar subquery in HAVING computes the global average once.
-- Concepts: Subquery, HAVING
-- ---------------------------------------------------------------------
SELECT track_genre, ROUND(AVG(popularity), 2) AS avg_popularity
FROM tracks
GROUP BY track_genre
HAVING AVG(popularity) > (SELECT AVG(popularity) FROM tracks)
ORDER BY avg_popularity DESC;

-- ---------------------------------------------------------------------
-- Q33 | Standout tracks versus their genre average
-- Question: Which tracks are at least 30 popularity points above their own genre's average?
-- Explanation: INNER JOIN to a derived table of genre averages allows row-level comparison.
-- Concepts: INNER JOIN, derived table (subquery in FROM)
-- ---------------------------------------------------------------------
SELECT t.track_name, t.primary_artist, t.track_genre, t.popularity,
       ROUND(g.genre_avg, 2) AS genre_avg,
       ROUND(t.popularity - g.genre_avg, 2) AS points_above_genre_avg
FROM tracks t
INNER JOIN (
    SELECT track_genre, AVG(popularity) AS genre_avg
    FROM tracks
    GROUP BY track_genre
) g ON g.track_genre = t.track_genre
WHERE t.popularity - g.genre_avg >= 30
ORDER BY points_above_genre_avg DESC, t.track_name
LIMIT 20;

-- ---------------------------------------------------------------------
-- Q34 | Audio profile per popularity band
-- Question: How do average audio features change from low- to high-popularity bands?
-- Explanation: INNER JOIN to the popularity_band lookup using a range condition (BETWEEN).
--              Shows association only - it does not prove which features drive popularity.
-- Concepts: INNER JOIN on range, GROUP BY, AVG
-- ---------------------------------------------------------------------
SELECT b.band_name,
       COUNT(*) AS track_rows,
       ROUND(AVG(t.danceability), 3) AS avg_danceability,
       ROUND(AVG(t.energy), 3) AS avg_energy,
       ROUND(AVG(t.valence), 3) AS avg_valence,
       ROUND(AVG(t.acousticness), 3) AS avg_acousticness
FROM tracks t
INNER JOIN popularity_band b
        ON t.popularity BETWEEN b.min_popularity AND b.max_popularity
GROUP BY b.band_name, b.sort_order
ORDER BY b.sort_order;

-- ---------------------------------------------------------------------
-- Q35 | Band coverage check with LEFT JOIN
-- Question: Does every popularity band contain tracks (and which bands are empty)?
-- Explanation: LEFT JOIN keeps bands with zero matching tracks; COUNT(t.track_id) then returns 0.
-- Concepts: LEFT JOIN, COUNT(column)
-- ---------------------------------------------------------------------
SELECT b.band_name, COUNT(t.track_id) AS track_rows
FROM popularity_band b
LEFT JOIN tracks t
       ON t.popularity BETWEEN b.min_popularity AND b.max_popularity
GROUP BY b.band_name, b.sort_order
ORDER BY b.sort_order;

-- ---------------------------------------------------------------------
-- Q36 | Genre share and cumulative share (Pareto view)
-- Question: How much of the catalogue do the largest genres make up?
-- Explanation: SUM() OVER () gives the grand total; a running SUM ordered by size gives the cumulative share.
-- Concepts: CTE, SUM() OVER, cumulative window
-- ---------------------------------------------------------------------
WITH genre_counts AS (
    SELECT track_genre, COUNT(*) AS n
    FROM tracks
    GROUP BY track_genre
)
SELECT track_genre, n AS track_rows,
       ROUND(100.0 * n / SUM(n) OVER (), 2) AS pct_of_rows,
       ROUND(100.0 * SUM(n) OVER (ORDER BY n DESC, track_genre) / SUM(n) OVER (), 2) AS cumulative_pct
FROM genre_counts
ORDER BY n DESC, track_genre
LIMIT 20;

-- ---------------------------------------------------------------------
-- Q37 | Popularity deciles
-- Question: What does each popularity decile look like?
-- Explanation: NTILE(10) splits tracks into ten equal-size groups (1 = most popular).
-- Concepts: CTE, NTILE()
-- ---------------------------------------------------------------------
WITH scored AS (
    SELECT popularity, danceability, energy, valence, acousticness,
           NTILE(10) OVER (ORDER BY popularity DESC) AS popularity_decile
    FROM tracks
)
SELECT popularity_decile,
       COUNT(*) AS track_rows,
       MIN(popularity) AS min_popularity,
       MAX(popularity) AS max_popularity,
       ROUND(AVG(energy), 3) AS avg_energy,
       ROUND(AVG(danceability), 3) AS avg_danceability
FROM scored
GROUP BY popularity_decile
ORDER BY popularity_decile;

-- ---------------------------------------------------------------------
-- Q38 | Top 10% versus everyone else
-- Question: How do the most popular 10% of tracks differ in audio features from the rest?
-- Explanation: Business question - "what do hits sound like?" Differences are associations, not causes.
-- Concepts: CTE, NTILE(), CASE, GROUP BY
-- ---------------------------------------------------------------------
WITH scored AS (
    SELECT danceability, energy, valence, acousticness, duration_min,
           NTILE(10) OVER (ORDER BY popularity DESC) AS popularity_decile
    FROM tracks
),
grouped AS (
    SELECT CASE WHEN popularity_decile = 1 THEN 'Top 10%' ELSE 'Other 90%' END AS track_group,
           danceability, energy, valence, acousticness, duration_min
    FROM scored
)
SELECT track_group,
       COUNT(*) AS track_rows,
       ROUND(AVG(danceability), 3) AS avg_danceability,
       ROUND(AVG(energy), 3) AS avg_energy,
       ROUND(AVG(valence), 3) AS avg_valence,
       ROUND(AVG(acousticness), 3) AS avg_acousticness,
       ROUND(AVG(duration_min), 2) AS avg_duration_min
FROM grouped
GROUP BY track_group
ORDER BY track_group DESC;

-- ---------------------------------------------------------------------
-- Q39 | Year-over-year popularity change
-- Question: How does average popularity change from one release year to the next?
-- Explanation: LAG() reads the previous year's value. Needs a year column (1M-track dataset).
-- Concepts: CTE, LAG()
-- ---------------------------------------------------------------------
WITH yearly AS (
    SELECT year, COUNT(*) AS n, AVG(popularity) AS avg_pop
    FROM tracks
    WHERE year IS NOT NULL
    GROUP BY year
)
SELECT year, n AS track_rows,
       ROUND(avg_pop, 2) AS avg_popularity,
       ROUND(avg_pop - LAG(avg_pop) OVER (ORDER BY year), 2) AS change_vs_previous_year
FROM yearly
ORDER BY year;

-- ---------------------------------------------------------------------
-- Q40 | Most genre-diverse artists
-- Question: Which artists span the most genres?
-- Explanation: Counts distinct genres per artist for artists with at least 10 tracks.
-- Concepts: GROUP BY, HAVING, COUNT(DISTINCT)
-- ---------------------------------------------------------------------
SELECT primary_artist,
       COUNT(DISTINCT track_genre) AS genres,
       COUNT(DISTINCT track_id) AS tracks
FROM tracks
GROUP BY primary_artist
HAVING COUNT(DISTINCT track_id) >= 10
ORDER BY genres DESC, tracks DESC, primary_artist
LIMIT 15;

-- ---------------------------------------------------------------------
-- Q41 | Audio-feature comparison across genres
-- Question: How do genres rank on danceability, energy and valence at the same time?
-- Explanation: Three RANK() windows over one CTE give a side-by-side comparison.
-- Concepts: CTE, multiple RANK() windows
-- ---------------------------------------------------------------------
WITH genre_features AS (
    SELECT track_genre,
           AVG(danceability) AS d, AVG(energy) AS e, AVG(valence) AS v, COUNT(*) AS n
    FROM tracks
    GROUP BY track_genre
    HAVING COUNT(*) >= 20
)
SELECT track_genre,
       ROUND(d, 3) AS avg_danceability, ROUND(e, 3) AS avg_energy, ROUND(v, 3) AS avg_valence,
       RANK() OVER (ORDER BY d DESC) AS danceability_rank,
       RANK() OVER (ORDER BY e DESC) AS energy_rank,
       RANK() OVER (ORDER BY v DESC) AS valence_rank
FROM genre_features
ORDER BY danceability_rank, track_genre
LIMIT 20;

-- ---------------------------------------------------------------------
-- Q42 | Popularity by energy band
-- Question: Does average popularity differ between low-, mid- and high-energy tracks?
-- Explanation: Banding a continuous feature is a simple way to inspect a relationship in SQL.
-- Concepts: CASE bands, GROUP BY, AVG
-- ---------------------------------------------------------------------
WITH banded AS (
    SELECT CASE WHEN energy < 0.33 THEN '1: low (<0.33)'
                WHEN energy < 0.66 THEN '2: medium (0.33-0.66)'
                ELSE '3: high (>=0.66)' END AS energy_band,
           popularity
    FROM tracks
)
SELECT energy_band, COUNT(*) AS track_rows, ROUND(AVG(popularity), 2) AS avg_popularity
FROM banded
GROUP BY energy_band
ORDER BY energy_band;

-- ---------------------------------------------------------------------
-- Q43 | Popularity by acousticness band
-- Question: How does acousticness relate to average popularity?
-- Explanation: Same banding approach as Q42 for acousticness.
-- Concepts: CASE bands, GROUP BY, AVG
-- ---------------------------------------------------------------------
WITH banded AS (
    SELECT CASE WHEN acousticness < 0.33 THEN '1: low (<0.33)'
                WHEN acousticness < 0.66 THEN '2: medium (0.33-0.66)'
                ELSE '3: high (>=0.66)' END AS acousticness_band,
           popularity
    FROM tracks
)
SELECT acousticness_band, COUNT(*) AS track_rows, ROUND(AVG(popularity), 2) AS avg_popularity
FROM banded
GROUP BY acousticness_band
ORDER BY acousticness_band;

-- ---------------------------------------------------------------------
-- Q44 | Artist popularity percentile
-- Question: Where does each established artist sit in the popularity distribution?
-- Explanation: PERCENT_RANK() returns 0-1; artists need at least 5 tracks to be included.
-- Concepts: CTE, PERCENT_RANK()
-- ---------------------------------------------------------------------
WITH artist_avg AS (
    SELECT primary_artist, COUNT(DISTINCT track_id) AS tracks, AVG(popularity) AS avg_pop
    FROM tracks
    GROUP BY primary_artist
    HAVING COUNT(DISTINCT track_id) >= 5
)
SELECT primary_artist, tracks,
       ROUND(avg_pop, 2) AS avg_popularity,
       ROUND(PERCENT_RANK() OVER (ORDER BY avg_pop), 3) AS popularity_percentile
FROM artist_avg
ORDER BY avg_pop DESC, primary_artist
LIMIT 20;

-- ---------------------------------------------------------------------
-- Q45 | Longest track in each genre
-- Question: What is the longest track of every genre?
-- Explanation: ROW_NUMBER() partitioned by genre and ordered by duration; keep rank 1.
-- Concepts: CTE, ROW_NUMBER(), PARTITION BY
-- ---------------------------------------------------------------------
WITH ranked AS (
    SELECT track_genre, track_name, primary_artist, duration_min,
           ROW_NUMBER() OVER (PARTITION BY track_genre ORDER BY duration_min DESC, track_name) AS rn
    FROM tracks
)
SELECT track_genre, track_name, primary_artist, duration_min
FROM ranked
WHERE rn = 1
ORDER BY duration_min DESC, track_genre
LIMIT 20;

-- ---------------------------------------------------------------------
-- Q46 | Pearson correlation: energy vs popularity
-- Question: What is the linear correlation between energy and popularity?
-- Explanation: Computes r = (E[xy] - E[x]E[y]) / (sigma_x * sigma_y) from plain AVG() terms and SQRT(), so it
--              runs unchanged on MySQL 8 and SQLite. Matches pandas' Pearson r. Correlation is not causation.
-- Concepts: CTE, aggregate arithmetic, SQRT
-- ---------------------------------------------------------------------
WITH stats AS (
    SELECT AVG(energy) AS mean_x, AVG(popularity) AS mean_y,
           AVG(energy * energy) AS mean_xx, AVG(popularity * popularity) AS mean_yy,
           AVG(energy * popularity) AS mean_xy
    FROM tracks
)
SELECT ROUND((mean_xy - mean_x * mean_y)
             / (SQRT(mean_xx - mean_x * mean_x) * SQRT(mean_yy - mean_y * mean_y)), 4) AS pearson_energy_popularity
FROM stats;

-- ---------------------------------------------------------------------
-- Q47 | Explicit share by genre
-- Question: Which genres contain the highest share of explicit tracks?
-- Explanation: Genres must have at least 20 rows with an explicit flag. Empty on datasets without 'explicit'.
-- Concepts: GROUP BY, HAVING, SUM / COUNT(column)
-- ---------------------------------------------------------------------
SELECT track_genre,
       COUNT(explicit) AS rows_with_flag,
       ROUND(100.0 * SUM(explicit) / COUNT(explicit), 2) AS explicit_pct
FROM tracks
GROUP BY track_genre
HAVING COUNT(explicit) >= 20
ORDER BY explicit_pct DESC, track_genre
LIMIT 15;

-- ---------------------------------------------------------------------
-- Q48 | "Hit rate" by genre
-- Question: Which genres have the largest share of tracks with popularity >= 70?
-- Explanation: A business-oriented view - where is a high-popularity track most likely to be found?
-- Concepts: conditional aggregation, HAVING
-- ---------------------------------------------------------------------
SELECT track_genre,
       COUNT(*) AS track_rows,
       ROUND(100.0 * SUM(CASE WHEN popularity >= 70 THEN 1 ELSE 0 END) / COUNT(*), 2) AS pct_popularity_70_plus
FROM tracks
GROUP BY track_genre
HAVING COUNT(*) >= 20
ORDER BY pct_popularity_70_plus DESC, track_genre
LIMIT 15;

-- ---------------------------------------------------------------------
-- Q49 | Prolific artists' catalogue performance
-- Question: How do tracks by artists with more than 50 tracks perform on average?
-- Explanation: The IN subquery selects the prolific artists; the outer query aggregates their tracks.
--              May return an empty result on small samples.
-- Concepts: IN subquery, GROUP BY, AVG
-- ---------------------------------------------------------------------
SELECT primary_artist,
       COUNT(*) AS track_rows,
       ROUND(AVG(popularity), 2) AS avg_popularity
FROM tracks
WHERE primary_artist IN (
    SELECT primary_artist
    FROM tracks
    GROUP BY primary_artist
    HAVING COUNT(DISTINCT track_id) > 50
)
GROUP BY primary_artist
ORDER BY avg_popularity DESC, primary_artist
LIMIT 20;

-- ---------------------------------------------------------------------
-- Q50 | Genres in the top half for both popularity and energy
-- Question: Which genres rank in the top half for popularity AND in the top half for energy?
-- Explanation: Combines two RANK() windows in a CTE and filters on both - a recommendation-strategy style screen.
-- Concepts: CTE, RANK(), COUNT(*) OVER ()
-- ---------------------------------------------------------------------
WITH genre_scores AS (
    SELECT track_genre, AVG(popularity) AS pop, AVG(energy) AS en, COUNT(*) AS n
    FROM tracks
    GROUP BY track_genre
    HAVING COUNT(*) >= 20
),
ranked AS (
    SELECT track_genre, pop, en,
           RANK() OVER (ORDER BY pop DESC) AS pop_rank,
           RANK() OVER (ORDER BY en DESC)  AS energy_rank,
           COUNT(*) OVER ()                AS genre_total
    FROM genre_scores
)
SELECT track_genre, ROUND(pop, 2) AS avg_popularity, ROUND(en, 3) AS avg_energy, pop_rank, energy_rank
FROM ranked
WHERE pop_rank  <= genre_total / 2.0
  AND energy_rank <= genre_total / 2.0
ORDER BY pop_rank, track_genre;
