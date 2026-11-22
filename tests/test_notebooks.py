"""Execute the code cells of every notebook (in order) against SYNTHETIC data.

This is a lightweight stand-in for `jupyter nbconvert --execute` so the notebooks can be
checked without Jupyter installed. It proves the code cells run end-to-end; it does not
check Jupyter rendering.
"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import matplotlib

matplotlib.use("Agg")

from tests.synthetic import make_raw_tracks

NOTEBOOK_DIR = Path(__file__).resolve().parents[1] / "notebooks"
NOTEBOOKS = ["01_data_understanding", "02_data_cleaning", "03_exploratory_data_analysis"]


def _code_cells(name):
    book = json.loads((NOTEBOOK_DIR / f"{name}.ipynb").read_text(encoding="utf-8"))
    return ["".join(c["source"]) for c in book["cells"] if c["cell_type"] == "code"]


class TestNotebooks(unittest.TestCase):
    def test_notebooks_execute_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            dirs = {"SPOTIFY_RAW_DIR": "raw", "SPOTIFY_PROCESSED_DIR": "processed", "SPOTIFY_REPORTS_DIR": "reports"}
            env = {}
            for var, folder in dirs.items():
                (tmp / folder).mkdir()
                env[var] = str(tmp / folder)
            make_raw_tracks(n=900, seed=3).to_csv(tmp / "raw" / "synthetic_tracks.csv", index=False)

            old_cwd = os.getcwd()
            os.chdir(NOTEBOOK_DIR)
            try:
                with mock.patch.dict(os.environ, env), mock.patch("matplotlib.pyplot.show"):
                    for name in NOTEBOOKS:
                        namespace = {"display": lambda *a, **k: None, "__name__": "__main__"}
                        for i, source in enumerate(_code_cells(name)):
                            try:
                                exec(compile(source, f"{name}[cell {i}]", "exec"), namespace)
                            except Exception as exc:  # noqa: BLE001
                                self.fail(f"{name} cell {i} failed: {type(exc).__name__}: {exc}\n---\n{source}")
            finally:
                os.chdir(old_cwd)
            self.assertTrue((tmp / "processed" / "tracks_clean.csv").exists())
            self.assertTrue((tmp / "reports" / "data_quality_report.md").exists())
            self.assertGreaterEqual(len(list((tmp / "reports" / "figures").glob("*.png"))), 18)


if __name__ == "__main__":
    unittest.main()
