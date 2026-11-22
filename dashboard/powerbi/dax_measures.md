# DAX Measures

> **Status:** written to match the exported tables and checked by eye only - they have **not** been
> executed in Power BI Desktop (not available in the build environment). Create them in the
> `fact_tracks` table (Modeling > New measure) and fix any naming differences if you renamed tables.
> Tip: create a table `_Measures` (Enter Data) and put all measures there.

## KPI cards (Page 1)

```dax
Total Tracks = DISTINCTCOUNT ( fact_tracks[track_id] )
Total Artists = DISTINCTCOUNT ( fact_tracks[primary_artist] )
Total Genres = DISTINCTCOUNT ( fact_tracks[track_genre] )
Track Rows = COUNTROWS ( fact_tracks )
Avg Popularity = AVERAGE ( fact_tracks[popularity] )
Avg Duration (min) = AVERAGE ( fact_tracks[duration_min] )

Explicit Tracks =
CALCULATE ( COUNTROWS ( fact_tracks ), fact_tracks[explicit] = 1 )

Tracks With Explicit Flag =
CALCULATE ( COUNTROWS ( fact_tracks ), NOT ISBLANK ( fact_tracks[explicit] ) )

Explicit Track % =
DIVIDE ( [Explicit Tracks], [Tracks With Explicit Flag] )   -- format as percentage
```

## Audio feature cards (Page 3)

```dax
Avg Energy = AVERAGE ( fact_tracks[energy] )
Avg Danceability = AVERAGE ( fact_tracks[danceability] )
Avg Acousticness = AVERAGE ( fact_tracks[acousticness] )
Avg Valence = AVERAGE ( fact_tracks[valence] )
Avg Tempo (BPM) = AVERAGE ( fact_tracks[tempo] )
Avg Instrumentalness = AVERAGE ( fact_tracks[instrumentalness] )
```

## Ranking and comparison

```dax
Genre Popularity Rank =
RANKX ( ALL ( dim_genre[track_genre] ), [Avg Popularity], , DESC, Dense )

Popularity vs Overall Average =
[Avg Popularity] - CALCULATE ( [Avg Popularity], ALL ( fact_tracks ) )

Share of Tracks 70+ =
DIVIDE ( CALCULATE ( COUNTROWS ( fact_tracks ), fact_tracks[popularity] >= 70 ), COUNTROWS ( fact_tracks ) )

Track Share of Total =
DIVIDE ( [Track Rows], CALCULATE ( [Track Rows], ALL ( fact_tracks ) ) )
```

For "Top 10" visuals use a **visual-level Top N filter** (Top 10 by `Avg Popularity` or `Max Popularity`),
and for artists also filter `dim_artist[track_count] >= 5` so one-hit artists do not dominate.

```dax
Max Popularity = MAX ( fact_tracks[popularity] )
```

## Slicer-aware correlation (association only - not causation)

```dax
Corr Energy vs Popularity =
VAR n   = COUNTROWS ( fact_tracks )
VAR sx  = SUM ( fact_tracks[energy] )
VAR sy  = SUM ( fact_tracks[popularity] )
VAR sxy = SUMX ( fact_tracks, fact_tracks[energy] * fact_tracks[popularity] )
VAR sxx = SUMX ( fact_tracks, fact_tracks[energy] ^ 2 )
VAR syy = SUMX ( fact_tracks, fact_tracks[popularity] ^ 2 )
RETURN
    DIVIDE ( n * sxy - sx * sy, SQRT ( ( n * sxx - sx ^ 2 ) * ( n * syy - sy ^ 2 ) ) )
```

Copy the measure and replace `energy` for `danceability`, `acousticness`, `valence`, etc.
On ~1M rows these `SUMX` iterations can be slow; the precomputed `feature_correlation` table is the fast alternative.

## Dynamic helpers

```dax
Selected Genre Label =
IF ( ISFILTERED ( fact_tracks[track_genre] ), "Genre: " & SELECTEDVALUE ( fact_tracks[track_genre], "multiple" ), "All genres" )

Popularity Colour =
SWITCH ( TRUE (), [Avg Popularity] >= 60, "#055220", [Avg Popularity] >= 40, "#B3B3B3", "#E22134" )
-- use as: Conditional formatting > Format by: Field value
```
