"""Every module imports, and the project folder contains all deliverables."""
import importlib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULES = ["config", "data_loader", "data_cleaning", "eda", "database", "insights", "ollama_service",
           "powerbi_export", "pipeline", "database_load", "sql_tools", "mysql_verify", "validate_dataset",
           "ollama_check"]
REQUIRED_FILES = [
    "README.md", "requirements.txt", ".gitignore", ".env.example", "LICENSE", "config/config.yaml",
    "notebooks/01_data_understanding.ipynb", "notebooks/02_data_cleaning.ipynb",
    "notebooks/03_exploratory_data_analysis.ipynb",
    "sql/01_create_database.sql", "sql/02_create_tables.sql", "sql/03_data_validation.sql",
    "sql/04_basic_analysis.sql", "sql/05_advanced_analysis.sql",
    "dashboard/streamlit_app.py", "dashboard/powerbi/spotify_theme.json", "dashboard/powerbi/dax_measures.md",
    "dashboard/powerbi/data_model.md", "dashboard/powerbi/load_data.pq",
    "docs/project_requirements.md", "docs/data_dictionary.md", "docs/sql_documentation.md",
    "docs/dashboard_documentation.md", "docs/setup_guide.md", "docs/testing_report.md",
    "docs/project_completion_report.md",
    "tests/test_data_cleaning.py", "tests/test_data_validation.py", "tests/test_insights.py",
]


class TestImports(unittest.TestCase):
    def test_all_src_modules_import(self):
        for name in MODULES:
            with self.subTest(module=name):
                importlib.import_module(f"src.{name}")

    def test_required_files_exist(self):
        missing = [f for f in REQUIRED_FILES if not (ROOT / f).exists()]
        self.assertEqual(missing, [])

    def test_database_url_builder_escapes_password(self):
        from src.database import get_mysql_url
        url = get_mysql_url({"MYSQL_USER": "u", "MYSQL_PASSWORD": "p@ss/word", "MYSQL_HOST": "h", "MYSQL_PORT": "3307",
                             "MYSQL_DATABASE": "d"})
        self.assertTrue(url.startswith("mysql+pymysql://u:p%40ss%2Fword@h:3307/d"))

    def test_sql_statement_splitter(self):
        from src.database import split_sql_statements
        self.assertEqual(split_sql_statements("-- c\nSELECT 1; SELECT 2;\n-- end"), ["SELECT 1", "SELECT 2"])


if __name__ == "__main__":
    unittest.main()


class TestNotebookStructure(unittest.TestCase):
    """Lightweight nbformat-4.5 checks (the real `nbformat` package is not required)."""

    def test_notebook_json_structure(self):
        import json
        for path in sorted((ROOT / "notebooks").glob("*.ipynb")):
            with self.subTest(notebook=path.name):
                book = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(book["nbformat"], 4)
                ids = []
                for cell in book["cells"]:
                    self.assertIn(cell["cell_type"], ("code", "markdown"))
                    self.assertIsInstance(cell["source"], list)
                    self.assertIsInstance(cell["metadata"], dict)
                    if cell["cell_type"] == "code":
                        self.assertIn("outputs", cell)
                        self.assertIn("execution_count", cell)
                    if book["nbformat_minor"] >= 5:  # 4.5+ requires unique cell ids
                        self.assertRegex(cell.get("id", ""), r"^[a-zA-Z0-9_-]{1,64}$")
                        ids.append(cell["id"])
                self.assertEqual(len(ids), len(set(ids)))
                self.assertIn("kernelspec", book["metadata"])

    def test_streamlit_app_avoids_deprecated_arguments(self):
        source = (ROOT / "dashboard" / "streamlit_app.py").read_text(encoding="utf-8")
        self.assertNotIn("use_container_width", source)
