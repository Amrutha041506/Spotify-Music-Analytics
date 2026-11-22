"""Streamlit app checks.

* test_app_logic_with_fake_streamlit - ALWAYS runs. Replaces `streamlit` with a mock and drives
  every page function with SYNTHETIC data. It catches NameErrors, bad column names and logic
  bugs, but it is NOT a real Streamlit server start.
* test_real_streamlit_app_starts - only runs when `streamlit` is installed; uses Streamlit's own
  AppTest harness to run the real script.
"""
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import matplotlib

matplotlib.use("Agg")

from src.config import load_config
from src.data_cleaning import clean_dataset
from src.data_loader import save_processed
from tests.synthetic import make_raw_tracks

APP_PATH = Path(__file__).resolve().parents[1] / "dashboard" / "streamlit_app.py"
PAGES = ["Overview", "Search Tracks", "Artists & Genres", "Audio Features", "Business Insights", "Ask the Data (Ollama)"]


def build_fake_streamlit(page):
    st = mock.MagicMock(name="streamlit")
    st.cache_data = lambda *a, **k: (a[0] if a and callable(a[0]) else (lambda f: f))
    st.columns.side_effect = lambda spec: [mock.MagicMock() for _ in range(spec if isinstance(spec, int) else len(spec))]
    st.sidebar.radio.side_effect = lambda label, options, *a, **k: page if label == "Page" else "All"
    st.sidebar.multiselect.return_value = []
    st.sidebar.slider.return_value = (0, 100)
    st.slider.side_effect = lambda label, lo, hi, value=None, **k: value if value is not None else lo
    st.selectbox.side_effect = lambda label, options, index=0, **k: options[index]
    st.text_input.side_effect = lambda label, value="", **k: "Give me five insights" if label == "Your question" else value
    st.checkbox.return_value = False
    st.button.side_effect = lambda label, **k: label == "Ask"
    return st


class TestStreamlitApp(unittest.TestCase):
    def test_app_logic_with_fake_streamlit(self):
        clean, _ = clean_dataset(make_raw_tracks(700, seed=21))
        for page in PAGES:
            with self.subTest(page=page):
                fake = build_fake_streamlit(page)
                previous = sys.modules.get("streamlit")
                sys.modules["streamlit"] = fake  # replace only this key (patch.dict would also drop newly imported modules)
                try:
                    spec = importlib.util.spec_from_file_location("streamlit_app_under_test", APP_PATH)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    with mock.patch.object(module, "load_processed", return_value=clean):
                        module.main()
                finally:
                    if previous is None:
                        sys.modules.pop("streamlit", None)
                    else:
                        sys.modules["streamlit"] = previous
                fake.error.assert_not_called()
                rendered = fake.pyplot.call_count + fake.markdown.call_count + fake.dataframe.call_count
                self.assertGreater(rendered, 0, f"{page} rendered nothing")

    @unittest.skipUnless(importlib.util.find_spec("streamlit"), "streamlit is not installed")
    def test_real_streamlit_app_starts(self):
        from streamlit.testing.v1 import AppTest

        clean, _ = clean_dataset(make_raw_tracks(500, seed=22))
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"SPOTIFY_PROCESSED_DIR": tmp}):
            save_processed(clean, load_config())
            app = AppTest.from_file(str(APP_PATH), default_timeout=90).run()
            self.assertFalse(app.exception, app.exception)


if __name__ == "__main__":
    unittest.main()
