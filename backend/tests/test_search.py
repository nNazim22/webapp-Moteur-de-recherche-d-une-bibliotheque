"""Tests de bout en bout : construction de l'index sur 3 petits livres, puis recherches."""
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


@pytest.fixture(scope="module")
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


def ids_and_scores(result):
    return [(b["id"], b["score"]) for b in result["results"]]


def test_exact_search_ranks_by_occurrences(lib):
    assert ids_and_scores(lib.search("whale")) == [(1, 4), (3, 2)]


def test_search_is_case_insensitive(lib):
    assert lib.search("WHALE")["results"] == lib.search("whale")["results"]


def test_unknown_word_gives_no_result(lib):
    r = lib.search("zzzz")
    assert r["results"] == [] and r["n_books"] == 0


def test_substring_search_uses_kmp(lib):
    r = lib.search("lov", mode="substring")
    assert r["matched_terms"] == ["loves"]
    assert ids_and_scores(r) == [(2, 2)]


def test_regex_search_on_vocabulary(lib):
    r = lib.search("wh(a|e)+l", mode="regex")      # whale, wheel (pas wheat, pas white)
    assert sorted(r["matched_terms"]) == ["whale", "wheel"]
    assert ids_and_scores(r) == [(1, 4), (3, 3)]


def test_limit(lib):
    assert len(lib.search("the", limit=1)["results"]) == 1


def test_errors(lib):
    with pytest.raises(ValueError):
        lib.search("   ")
    with pytest.raises(ValueError):
        lib.search("a(b", mode="regex")
    with pytest.raises(ValueError):
        lib.search("x", mode="inconnu")