"""Fixture commune : un mini-index construit à partir de 3 petits livres."""
import csv
import subprocess
import sys
from pathlib import Path

import pytest

from app.search import Library

BOOKS = {
    1: "The white whale swims in the ocean. The whale is huge. Whale whale.",
    2: "The king loves the ocean and the king loves his queen.",
    3: "A wheel of wheat. Whale song in whale country.",
}
BUILD_INDEX = Path(__file__).resolve().parents[1] / "scripts" / "build_index.py"


@pytest.fixture(scope="session")
def lib(tmp_path_factory):
    data = tmp_path_factory.mktemp("data")
    (data / "books").mkdir()
    with open(data / "manifest.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "titre", "auteur", "nb_mots", "url"])
        for book_id, text in BOOKS.items():
            (data / "books" / f"{book_id}.txt").write_text(text, encoding="utf-8")
            w.writerow([book_id, f"Livre {book_id}", "Auteur", 0, "u"])
    subprocess.run([sys.executable, str(BUILD_INDEX), "--data", str(data)], check=True)
    return Library(data / "index.db")