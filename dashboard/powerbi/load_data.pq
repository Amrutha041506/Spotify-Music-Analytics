// Power Query (M) - paste each query into: Home > Transform data > New Source > Blank Query > Advanced Editor.
// 1) Create a parameter first: Manage Parameters > New Parameter
//      Name: DataFolder   Type: Text   Value: C:\path\to\Spotify-Music-Analytics\dashboard\powerbi\data\
//    (the folder produced by `python -m src.pipeline`; keep the trailing backslash)
// 2) Create the five queries below (names: fact_tracks, dim_genre, dim_artist, dim_popularity_band, feature_correlation).

// ---------------------------------------------------------------- fact_tracks
let
    Source = Csv.Document(File.Contents(DataFolder & "fact_tracks.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Promoted, {
        {"track_id", type text}, {"track_name", type text}, {"artists", type text}, {"primary_artist", type text},
        {"album_name", type text}, {"track_genre", type text}, {"popularity_band", type text}, {"tempo_bin", type text},
        {"year", Int64.Type}, {"popularity", Int64.Type}, {"key", Int64.Type}, {"mode", Int64.Type},
        {"time_signature", Int64.Type}, {"explicit", Int64.Type}, {"tempo_bin_order", Int64.Type},
        {"duration_min", type number}, {"danceability", type number}, {"energy", type number}, {"loudness", type number},
        {"speechiness", type number}, {"acousticness", type number}, {"instrumentalness", type number},
        {"liveness", type number}, {"valence", type number}, {"tempo", type number}
    }, "en-US")
in
    Typed

// ---------------------------------------------------------------- dim_genre
let
    Source = Csv.Document(File.Contents(DataFolder & "dim_genre.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Promoted, {{"track_genre", type text}, {"track_count", Int64.Type}}, "en-US"),
    Numeric = Table.TransformColumnTypes(Typed, List.Transform(List.Skip(Table.ColumnNames(Typed), 2), each {_, type number}), "en-US")
in
    Numeric

// ---------------------------------------------------------------- dim_artist
let
    Source = Csv.Document(File.Contents(DataFolder & "dim_artist.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Promoted, {{"primary_artist", type text}, {"track_count", Int64.Type}, {"avg_popularity", type number}}, "en-US")
in
    Typed

// ---------------------------------------------------------------- dim_popularity_band
let
    Source = Csv.Document(File.Contents(DataFolder & "dim_popularity_band.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Promoted, {{"popularity_band", type text}, {"min_popularity", Int64.Type}, {"max_popularity", Int64.Type}, {"sort_order", Int64.Type}}, "en-US")
in
    Typed

// ---------------------------------------------------------------- feature_correlation
let
    Source = Csv.Document(File.Contents(DataFolder & "feature_correlation.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(Promoted, {{"feature_x", type text}, {"feature_y", type text}, {"correlation", type number}}, "en-US")
in
    Typed
