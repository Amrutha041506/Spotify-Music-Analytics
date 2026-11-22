"""Streamlit explorer for the Spotify analytics project.

Run from the project root:   streamlit run dashboard/streamlit_app.py
Requires the cleaned dataset (run `python -m src.pipeline` first).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from src import eda, insights
from src.config import load_config
from src.data_loader import AUDIO_FEATURES, load_processed
from src.ollama_service import OllamaClient, OllamaSettings, answer_with_fallback

PAGES = ["Overview", "Search Tracks", "Artists & Genres", "Audio Features", "Business Insights", "Ask the Data (Ollama)"]

CSS = """
<style>
  .block-container {padding-top: 1.5rem;}
  h1, h2, h3 {color: #1DB954;}
  div[data-testid="stMetric"] {background: #191414; border: 1px solid #1DB954; border-radius: 10px; padding: 0.6rem 0.9rem;}
</style>
"""


@st.cache_data(show_spinner="Loading cleaned dataset...")
def load_data() -> pd.DataFrame:
    return load_processed(load_config())


@st.cache_data(show_spinner="Computing summary facts...")
def full_dataset_facts() -> dict:
    cfg = load_config()
    a = cfg["analysis"]
    return insights.compute_facts(load_data(), a["min_tracks_per_artist"], a["min_tracks_per_genre"], a["popular_quantile"])


def render(fig) -> None:
    st.pyplot(fig)
    plt.close(fig)


def sidebar_filters(df: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.header("Filters")
    genres = sorted(df["track_genre"].dropna().unique())
    chosen_genres = st.sidebar.multiselect("Genres", genres, placeholder="All genres")
    low, high = st.sidebar.slider("Popularity range", 0, 100, (0, 100))
    mask = df["popularity"].between(low, high)
    if chosen_genres:
        mask &= df["track_genre"].isin(chosen_genres)
    if df["explicit"].notna().any():
        choice = st.sidebar.radio("Explicit content", ["All", "Explicit only", "Non-explicit only"])
        if choice == "Explicit only":
            mask &= df["explicit"] == 1
        elif choice == "Non-explicit only":
            mask &= df["explicit"] == 0
    return df[mask]


def page_overview(df: pd.DataFrame) -> None:
    st.header("Dataset overview")
    tracks = eda.unique_tracks(df)
    share = eda.explicit_share(df)
    cols = st.columns(6)
    cols[0].metric("Unique tracks", f"{len(tracks):,}")
    cols[1].metric("Artists", f"{tracks['primary_artist'].nunique():,}")
    cols[2].metric("Genres", f"{df['track_genre'].nunique():,}")
    cols[3].metric("Avg popularity", f"{tracks['popularity'].mean():.1f}")
    cols[4].metric("Avg duration (min)", f"{tracks['duration_min'].mean():.2f}")
    cols[5].metric("Explicit %", f"{share['explicit_pct']}%" if share["available"] else "n/a")

    left, right = st.columns(2)
    with left:
        render(eda.histogram(tracks["popularity"], "Distribution of Track Popularity",
                             "Popularity score (0-100)", "Number of tracks", bins=50))
    with right:
        top = eda.top_tracks(df, 10)
        top["label"] = top["track_name"] + " - " + top["primary_artist"]
        render(eda.bar_chart(top, "label", "popularity", "Top 10 Tracks", "Popularity score", "Track - artist"))
    with st.expander("Preview the data"):
        st.dataframe(df.head(200))


def page_search(df: pd.DataFrame) -> None:
    st.header("Search tracks")
    query = st.text_input("Track or artist name contains", placeholder="e.g. love")
    results = df
    if query:
        mask = df["track_name"].str.contains(query, case=False, na=False, regex=False) | \
               df["artists"].str.contains(query, case=False, na=False, regex=False)
        results = df[mask]
    st.caption(f"{len(results):,} matching rows (showing the 500 most popular)")
    cols = ["track_name", "artists", "track_genre", "popularity", "duration_min", "energy", "danceability", "valence"]
    st.dataframe(results.sort_values("popularity", ascending=False)[cols].head(500))


def page_artists_genres(df: pd.DataFrame) -> None:
    st.header("Artists and genres")
    cfg = load_config()["analysis"]
    left, right = st.columns(2)
    with left:
        min_tracks = st.slider("Minimum tracks per artist", 1, 50, cfg["min_tracks_per_artist"])
        artists = eda.top_artists_by_avg_popularity(df, 10, min_tracks)
        if artists.empty:
            st.info("No artists meet this minimum under the current filters.")
        else:
            render(eda.bar_chart(artists, "primary_artist", "avg_popularity",
                                 f"Top Artists by Average Popularity (min. {min_tracks} tracks)",
                                 "Average popularity", "Artist"))
    with right:
        metric = st.selectbox("Rank genres by", ["popularity", "danceability", "energy", "valence",
                                                 "acousticness", "instrumentalness"])
        genre_min = st.slider("Minimum tracks per genre", 1, 200, cfg["min_tracks_per_genre"])
        genres = eda.genre_metric_ranking(df, metric, 10, genre_min)
        if genres.empty:
            st.info("No genres meet this minimum under the current filters.")
        else:
            render(eda.bar_chart(genres, "track_genre", f"avg_{metric}", f"Top Genres by Average {metric.capitalize()}",
                                 f"Average {metric}", "Genre"))
    st.subheader("Artists with the most tracks")
    st.dataframe(eda.artist_track_counts(df, 15))


def page_audio(df: pd.DataFrame) -> None:
    st.header("Audio feature analysis")
    features = [f for f in AUDIO_FEATURES + ["duration_min"] if f in df.columns]
    feature = st.selectbox("Feature", features, index=features.index("energy") if "energy" in features else 0)
    sample_n = load_config()["analysis"]["plot_sample_size"]
    tracks = eda.unique_tracks(df)
    left, right = st.columns(2)
    with left:
        render(eda.density_scatter(tracks, feature, "popularity", f"Popularity vs {feature}", feature,
                                   "Popularity score (0-100)", sample_n))
    with right:
        render(eda.histogram(tracks[feature], f"Distribution of {feature}", feature))
    corr = eda.popularity_correlations(df)
    corr["strength"] = corr["pearson_r"].map(insights.describe_correlation)
    st.subheader("Association with popularity")
    st.dataframe(corr)
    st.caption(insights.CAUSATION_NOTE)
    render(eda.heatmap(eda.feature_correlation_matrix(df), "Correlation Matrix of Audio Features"))


def page_insights() -> None:
    st.header("Business insights")
    facts = full_dataset_facts()
    st.caption("Computed on the full cleaned dataset (filters do not apply).")
    for text in insights.generate_insights(facts, 10):
        st.markdown(f"- {text}")
    st.subheader("Ideas for recommendation platforms (hypotheses)")
    for text in insights.strategy_suggestions(facts):
        st.markdown(f"- {text}")
    with st.expander("Caveats"):
        for note in facts["notes"]:
            st.markdown(f"- {note}")


def page_ollama() -> None:
    st.header("Ask the data (optional Ollama)")
    st.write("Answers are generated from pre-computed results. If Ollama is not running you get the rule-based answer.")
    settings = OllamaSettings.from_config(load_config())
    use_ollama = st.checkbox("Use Ollama", value=False)
    settings.model = st.text_input("Model name", value=settings.model)
    client = OllamaClient(settings) if use_ollama else None
    if use_ollama and st.button("Check Ollama connection"):
        try:
            models = client.list_models()
            st.success(f"Connected. Installed models: {', '.join(models) or 'none'}")
        except Exception as exc:  # noqa: BLE001 - show any connection problem to the user
            st.error(str(exc))

    presets = ["Which genre has the highest average popularity?", "What are the top-performing artists?",
               "What are the main trends in the dataset?", "Which audio features show the strongest correlation with popularity?",
               "Give me five important business insights.", "Suggest strategies for music recommendation platforms."]
    preset = st.selectbox("Example questions", ["(type your own)"] + presets)
    question = st.text_input("Your question", value="" if preset == "(type your own)" else preset)
    if st.button("Ask") and question.strip():
        with st.spinner("Thinking..."):
            answer = answer_with_fallback(question, full_dataset_facts(), client)
        st.markdown(answer.text)
        st.caption(f"Source: {'Ollama (' + str(answer.model) + ')' if answer.source == 'ollama' else 'rule-based analytics'}")
        if answer.error and use_ollama:
            st.warning(answer.error)
        for warning in answer.warnings:
            st.warning(warning)


def main() -> None:
    st.set_page_config(page_title="Spotify Music Analytics", page_icon="🎧", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    st.title("🎧 Spotify Music Analytics")
    try:
        df = load_data()
    except FileNotFoundError as exc:
        st.error(str(exc))
        st.stop()
        return

    page = st.sidebar.radio("Page", PAGES)
    filtered = sidebar_filters(df)
    if filtered.empty and page not in ("Business Insights", "Ask the Data (Ollama)"):
        st.warning("No tracks match the current filters.")
        return

    if page == "Overview":
        page_overview(filtered)
    elif page == "Search Tracks":
        page_search(filtered)
    elif page == "Artists & Genres":
        page_artists_genres(filtered)
    elif page == "Audio Features":
        page_audio(filtered)
    elif page == "Business Insights":
        page_insights()
    else:
        page_ollama()


if __name__ == "__main__":
    main()
