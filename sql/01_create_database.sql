-- =====================================================================
-- 01_create_database.sql
-- Creates the database used by the Spotify analytics project (MySQL 8).
-- Run:  mysql -u root -p -e "source sql/01_create_database.sql"
-- =====================================================================
CREATE DATABASE IF NOT EXISTS spotify_analytics
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE spotify_analytics;
