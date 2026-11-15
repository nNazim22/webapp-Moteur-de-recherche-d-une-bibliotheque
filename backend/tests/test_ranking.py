"""Tests du classement par occurrences et centralité."""
import sqlite3

from app.ranking import Ranker


def test_ranker_falls_back_to_occurrences_when_graph_is_missing(tmp_path):
    ranker = Ranker(tmp_path / "missing.db")
    rows = [{"id": 2, "occurrences": 3}, {"id": 1, "occurrences": 8}]
    ranked = ranker.rank(rows, "pagerank")
    assert [row["id"] for row in ranked] == [1, 2]
    assert ranked[0]["score"] == 8


def test_ranker_uses_pagerank_and_suggestions(tmp_path):
    db = tmp_path / "ranking.db"
    with sqlite3.connect(db) as con:
        con.executescript("""
            CREATE TABLE centrality(
                book_id INTEGER PRIMARY KEY, pagerank REAL, closeness REAL,
                betweenness REAL, degree INTEGER, x REAL, y REAL
            );
            CREATE TABLE jaccard_edges(a INTEGER, b INTEGER, jaccard REAL);
            INSERT INTO centrality VALUES (1, 0.1, 0.2, 0.0, 1, 0, 0);
            INSERT INTO centrality VALUES (2, 0.9, 0.8, 0.0, 1, 1, 1);
            INSERT INTO jaccard_edges VALUES (1, 2, 0.75);
        """)
    ranker = Ranker(db)
    ranked = ranker.rank(
        [{"id": 1, "occurrences": 20}, {"id": 2, "occurrences": 1}],
        "pagerank",
    )
    assert [row["id"] for row in ranked] == [2, 1]
    assert ranker.voisins(1, 5) == [(2, 0.75)]
