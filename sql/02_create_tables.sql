-- =====================================================================
-- 02_create_tables.sql
-- Table design for the CLEANED dataset (dataset/processed/tracks_clean.csv).
-- Column names and order match src/data_loader.py::CLEAN_COLUMNS.
--
-- Grain: one row per (track_id, track_genre). Some datasets list the same
-- track under several genres, hence the composite primary key.
-- Columns that some datasets do not provide (album_name, year, explicit) are NULL-able.
-- Run:  mysql -u root -p -e "source sql/02_create_tables.sql"
-- =====================================================================
USE spotify_analytics;

DROP TABLE IF EXISTS tracks;
CREATE TABLE tracks (
    track_id            VARCHAR(32)   NOT NULL,
    track_name          VARCHAR(512)  NOT NULL,
    artists             VARCHAR(1024) NOT NULL,
    primary_artist      VARCHAR(255)  NOT NULL,
    album_name          VARCHAR(512)  NULL,
    track_genre         VARCHAR(100)  NOT NULL,
    year                SMALLINT      NULL,
    popularity          SMALLINT      NOT NULL,
    duration_ms         INT           NOT NULL,
    duration_min        DECIMAL(8,3)  NOT NULL,
    explicit            TINYINT       NULL,
    danceability        DOUBLE        NOT NULL,
    energy              DOUBLE        NOT NULL,
    `key`               SMALLINT      NOT NULL,
    loudness            DOUBLE        NOT NULL,
    `mode`              SMALLINT      NOT NULL,
    speechiness         DOUBLE        NOT NULL,
    acousticness        DOUBLE        NOT NULL,
    instrumentalness    DOUBLE        NOT NULL,
    liveness            DOUBLE        NOT NULL,
    valence             DOUBLE        NOT NULL,
    tempo               DOUBLE        NULL,
    time_signature      SMALLINT      NULL,
    is_duration_outlier TINYINT       NOT NULL DEFAULT 0,
    PRIMARY KEY (track_id, track_genre),
    CONSTRAINT chk_popularity CHECK (popularity BETWEEN 0 AND 100)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Indexes that speed up the analysis queries on ~1M rows
CREATE INDEX idx_tracks_genre      ON tracks (track_genre);
CREATE INDEX idx_tracks_artist     ON tracks (primary_artist);
CREATE INDEX idx_tracks_popularity ON tracks (popularity);
CREATE INDEX idx_tracks_year       ON tracks (year);

-- Lookup table used by the JOIN examples (popularity bands)
DROP TABLE IF EXISTS popularity_band;
CREATE TABLE popularity_band (
    band_name      VARCHAR(30) NOT NULL PRIMARY KEY,
    min_popularity SMALLINT    NOT NULL,
    max_popularity SMALLINT    NOT NULL,
    sort_order     SMALLINT    NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO popularity_band (band_name, min_popularity, max_popularity, sort_order) VALUES
    ('00-19 Low',        0,  19, 1),
    ('20-39 Below avg', 20,  39, 2),
    ('40-59 Medium',    40,  59, 3),
    ('60-79 High',      60,  79, 4),
    ('80-100 Very high', 80, 100, 5);

-- =====================================================================
-- CSV IMPORT (choose ONE method)
--
-- Method A - Python (recommended, works on every OS, chunked for 1M rows):
--     python -m src.database_load        (see docs/setup_guide.md)
--
-- Method B - LOAD DATA LOCAL INFILE (fastest). Needs local_infile enabled:
--     mysql --local-infile=1 -u root -p spotify_analytics
--     SET GLOBAL local_infile = 1;
--   Then run the statement below, replacing the path (use forward slashes on Windows).
--   It is commented out so this script stays runnable as-is.
--
-- LOAD DATA LOCAL INFILE 'C:/path/to/Spotify-Music-Analytics/dataset/processed/tracks_clean.csv'
-- INTO TABLE tracks
-- CHARACTER SET utf8mb4
-- FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
-- LINES TERMINATED BY '\n'
-- IGNORE 1 LINES
-- (track_id, track_name, artists, primary_artist, @album_name, track_genre, @year, popularity,
--  duration_ms, duration_min, @explicit, danceability, energy, `key`, loudness, `mode`,
--  speechiness, acousticness, instrumentalness, liveness, valence, @tempo, @time_signature,
--  is_duration_outlier)
-- SET album_name     = NULLIF(@album_name, ''),
--     year           = NULLIF(@year, ''),
--     explicit       = NULLIF(@explicit, ''),
--     tempo          = NULLIF(@tempo, ''),
--     time_signature = NULLIF(@time_signature, '');
-- =====================================================================
