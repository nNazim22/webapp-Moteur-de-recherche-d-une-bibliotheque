"""Classement des résultats de recherche (fonctionnalité implicite de classement).

Critères :
  - "occurrences" : nombre d'occurrences du mot-clef dans le livre ;
  - "pagerank" / "closeness" / "betweenness" : centralité du livre dans le graphe de Jaccard ;
  - "mixte" : 0.7 * occurrences normalisées (échelle log) + 0.3 * PageRank normalisé.
"""
from __future__ import annotations

import math
import sqlite3
from pathlib import Path

CRITERES = ("occurrences", "pagerank", "closeness", "betweenness", "mixte")


def _norm(values):
    """Normalisation min-max dans [0,1]."""
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi == lo:
        return [0.0 for _ in values]
    return [(v - lo) / (hi - lo) for v in values]


class Ranker:
    def __init__(self, db_path="data/ranking.db"):
        self.path = Path(db_path)
        self.scores: dict[str, dict[int, float]] = {}
        self.available = False
        if self.path.exists():
            try:
                con = sqlite3.connect(self.path)
                for crit in ("pagerank", "closeness", "betweenness"):
                    rows = con.execute(
                        f"SELECT book_id, {crit} FROM centrality WHERE {crit} IS NOT NULL"
                    ).fetchall()
                    if rows:
                        self.scores[crit] = {int(b): float(v) for b, v in rows}
                con.close()
                self.available = bool(self.scores)
            except sqlite3.Error:
                self.available = False

    def criteres_disponibles(self):
        return ["occurrences"] + [c for c in ("pagerank", "closeness", "betweenness") if c in self.scores] \
            + (["mixte"] if "pagerank" in self.scores else [])

    def rank(self, results, critere="occurrences"):
        """results : liste de dicts avec 'id' et 'occurrences'. Retourne une
        nouvelle liste triée (score décroissant), avec un champ 'score'."""
        if critere not in CRITERES or (critere not in ("occurrences",) and not self.available):
            critere = "occurrences"
        items = [dict(r) for r in results]
        occ = [float(r.get("occurrences", 0) or 0) for r in items]
        if critere == "occurrences":
            sc = occ
        elif critere == "mixte":
            pr = [self.scores.get("pagerank", {}).get(int(r["id"]), 0.0) for r in items]
            lo = _norm([math.log1p(o) for o in occ])
            sc = [0.7 * a + 0.3 * b for a, b in zip(lo, _norm(pr))]
        else:
            table = self.scores.get(critere, {})
            sc = [table.get(int(r["id"]), 0.0) for r in items]
        for r, s in zip(items, sc):
            r["score"] = s
        # départage stable : score, puis occurrences, puis id
        items.sort(key=lambda r: (-r["score"], -float(r.get("occurrences", 0) or 0), int(r["id"])))
        return items

    def voisins(self, book_id, n=5):
        """Voisins d'un livre dans le graphe de Jaccard (pour les suggestions)."""
        if not self.path.exists():
            return []
        con = sqlite3.connect(self.path)
        rows = con.execute(
            """SELECT CASE WHEN a=? THEN b ELSE a END, jaccard FROM jaccard_edges
               WHERE a=? OR b=? ORDER BY jaccard DESC LIMIT ?""",
            (book_id, book_id, book_id, n),
        ).fetchall()
        con.close()
        return [(int(b), float(j)) for b, j in rows]


def export_graphe(db_path="data/ranking.db", manifest="data/manifest.csv"):
    """Données du graphe pour la page de visualisation : sommets (positions,
    centralités, titre) et arêtes (indices dans la liste des sommets, poids Jaccard).
    Retourne None si ranking.db est absent."""
    path = Path(db_path)
    if not path.exists():
        return None
    from .jaccard_graph import titles

    tt = titles(Path(manifest))
    con = sqlite3.connect(path)
    rows = con.execute(
        "SELECT book_id, pagerank, closeness, betweenness, degree, x, y FROM centrality ORDER BY book_id"
    ).fetchall()
    index = {int(r[0]): i for i, r in enumerate(rows)}
    nodes = [
        {"id": int(r[0]), "pagerank": r[1], "closeness": r[2], "betweenness": r[3],
         "degree": r[4], "x": r[5], "y": r[6], "title": tt.get(str(r[0]), "")}
        for r in rows
    ]
    edges = [
        [index[int(a)], index[int(b)], round(float(j), 4)]
        for a, b, j in con.execute("SELECT a, b, jaccard FROM jaccard_edges")
        if int(a) in index and int(b) in index
    ]
    params = dict(con.execute("SELECT key, value FROM params").fetchall())
    con.close()
    return {"params": params, "nodes": nodes, "edges": edges}