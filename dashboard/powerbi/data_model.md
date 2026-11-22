# Power BI Data Model

Source files are produced by `python -m src.pipeline` in `dashboard/powerbi/data/` (git-ignored).

## Tables

| Table | Grain | Rows (approx.) | Purpose |
|---|---|---|---|
| `fact_tracks` | one row per (track, genre) | = cleaned dataset | all measures and slicers |
| `dim_genre` | one row per genre | number of genres | genre averages, genre slicer |
| `dim_artist` | one row per primary artist | number of artists | artist slicer / artist ranking |
| `dim_popularity_band` | one row per band | 5 | sorted popularity bands |
| `feature_correlation` | feature pair | ~121 | correlation matrix (disconnected) |

## Relationships (all single direction, dimension -> fact)

| From (one side) | To (many side) |
|---|---|
| `dim_genre[track_genre]` | `fact_tracks[track_genre]` |
| `dim_artist[primary_artist]` | `fact_tracks[primary_artist]` |
| `dim_popularity_band[popularity_band]` | `fact_tracks[popularity_band]` |

`feature_correlation` has **no relationships**: it is a static matrix computed once in Python
on the full dataset, so it does not react to slicers. Use the filter-aware correlation measures in
`dax_measures.md` when you need a slicer-sensitive number.

## Column settings

* `fact_tracks[tempo_bin]` -> Column tools > **Sort by column** > `tempo_bin_order`
* `dim_popularity_band[popularity_band]` -> Sort by `sort_order`
* `fact_tracks[track_id]`, `key`, `mode`, `year`, `time_signature`, `explicit` -> **Don't summarize**
* Hide `fact_tracks[artists]`, `album_name`, `popularity_band` (use the dimension columns in visuals)

## Design notes

* Genre and artist dimensions are pre-aggregated in Python so genre/artist rankings stay fast
  with ~1M rows; measures on `fact_tracks` still respond to every slicer.
* For datasets where a track appears under several genres (the 114k file), `COUNTROWS` and `AVERAGE`
  count each (track, genre) row; `Total Tracks` uses `DISTINCTCOUNT(track_id)`.
* The `explicit` column is blank for datasets that do not provide it; explicit measures then return blank.
