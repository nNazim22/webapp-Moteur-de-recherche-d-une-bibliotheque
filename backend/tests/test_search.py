"""Tests de la recherche : mot exact, sous-chaîne (KMP) et regex (DFA)."""
import pytest


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