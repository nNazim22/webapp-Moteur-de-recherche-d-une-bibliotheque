import importlib.util
import sys
from pathlib import Path


def test_setup_data_seeds_three_books_when_data_is_empty(tmp_path, monkeypatch):
    script = Path(__file__).resolve().parents[1] / "scripts" / "setup_data.py"
    spec = importlib.util.spec_from_file_location("daar_setup_data", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(
        sys,
        "argv",
        ["setup_data.py", "--skip-download", "--skip-index", "--data", str(tmp_path / "data")],
    )

    module.main()

    data = tmp_path / "data"
    assert (data / "manifest.csv").exists()
    assert {p.name for p in (data / "books").glob("*.txt")} == {"84.txt", "1342.txt", "2701.txt"}
