"""Couche serveur : recherche par mot-clé et recherche avancée par regex.

Toutes les recherches passent par le vocabulaire de l'index :
  1. on trouve les mots du vocabulaire qui correspondent à la requête ;
  2. on additionne leurs occurrences dans chaque livre (index inversé) ;
  3. on classe les livres par nombre d'occurrences décroissant.

Usage en ligne de commande (depuis le dossier backend/) :
    python -m app.search whale
    python -m app.search wha --mode substring
    python -m app.search "wh(a|e)+l" --mode regex
"""
import argparse
import os
import sqlite3
import time
from collections import OrderedDict
from contextlib import closing
from pathlib import Path

from engine import KMPMatcher, compile_regex
from engine.regex_parser import RegexSyntaxError

# Chemin de l'index : variable d'environnement DAAR_DB, sinon <racine du projet>/data/index.db
DEFAULT_DB = Path(os.environ.get("DAAR_DB", Path(__file__).resolve().parents[2] / "data" / "index.db"))
CHUNK = 500        # nombre de mots par requête SQL (SQLite limite le nombre de paramètres)
CACHE_SIZE = 128   # nombre de requêtes dont on garde la liste de mots correspondants
MODES = ("exact", "substring", "regex")
MAX_TERMS = 50     # nombre maximal de mots correspondants renvoyés dans la réponse


class Library:
    def __init__(self, db_path=DEFAULT_DB):
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"Index introuvable : {self.db_path} (lancez build_index.py)")
        # Le vocabulaire est chargé une fois en mémoire : c'est la liste sur laquelle
        # on teste le mot-clé ou la regex (bien plus petite que le texte des livres).
        with closing(sqlite3.connect(self.db_path)) as con:
            self.vocab = con.execute("SELECT term_id, term FROM vocab").fetchall()
            self.n_books = con.execute("SELECT COUNT(*) FROM books").fetchone()[0]
        self.term_id = {term: tid for tid, term in self.vocab}
        self.term_of = {tid: term for tid, term in self.vocab}
        self._cache = OrderedDict()

    # --- étape 1 : quels mots du vocabulaire correspondent à la requête ? ---

    def _matching_terms(self, query, mode):
        key = (mode, query)
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]

        if mode == "exact":
            tid = self.term_id.get(query)
            ids = [tid] if tid is not None else []
        elif mode == "substring":
            matcher = KMPMatcher(query)                       # algorithme KMP
            ids = [tid for tid, term in self.vocab if matcher.search(term)]
        else:
            try:
                matcher = compile_regex(query)                # regex -> NFA -> DFA
            except RegexSyntaxError as e:
                raise ValueError(f"Regex invalide : {e}") from e
            ids = [tid for tid, term in self.vocab if matcher.search(term)]

        self._cache[key] = ids
        if len(self._cache) > CACHE_SIZE:
            self._cache.popitem(last=False)
        return ids

    # --- étape 2 et 3 : score de chaque livre, puis classement ---

    def _score_books(self, term_ids):
        scores = {}
        with closing(sqlite3.connect(self.db_path)) as con:
            for i in range(0, len(term_ids), CHUNK):
                part = term_ids[i:i + CHUNK]
                marks = ",".join("?" * len(part))
                rows = con.execute(
                    f"SELECT book_id, SUM(count) FROM postings "
                    f"WHERE term_id IN ({marks}) GROUP BY book_id", part)
                for book_id, c in rows:
                    scores[book_id] = scores.get(book_id, 0) + c
        return scores

    def _book_infos(self, book_ids):
        if not book_ids:
            return {}
        marks = ",".join("?" * len(book_ids))
        with closing(sqlite3.connect(self.db_path)) as con:
            rows = con.execute(
                f"SELECT id, title, author, n_words FROM books WHERE id IN ({marks})", book_ids)
            return {r[0]: r for r in rows}

    # --- lecture d'un livre ---

    def get_book(self, book_id):
        """Métadonnées d'un livre (None s'il n'existe pas dans l'index)."""
        with closing(sqlite3.connect(self.db_path)) as con:
            row = con.execute(
                "SELECT id, title, author, n_words FROM books WHERE id = ?", (book_id,)).fetchone()
        if row is None:
            return None
        return {"id": row[0], "title": row[1], "author": row[2], "n_words": row[3]}

    def book_path(self, book_id):
        """Fichier texte du livre : data/books/<id>.txt, à côté de index.db."""
        return self.db_path.parent / "books" / f"{int(book_id)}.txt"

    def search(self, query, mode="exact", limit=20):
        """Renvoie un dictionnaire : livres classés par occurrences + infos utiles."""
        if mode not in MODES:
            raise ValueError(f"Mode inconnu : {mode} (attendu : {', '.join(MODES)})")
        query = query.strip().lower()     # l'index est en minuscules
        if not query:
            raise ValueError("Requête vide")

        t0 = time.perf_counter()
        term_ids = self._matching_terms(query, mode)
        scores = self._score_books(term_ids)
        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]
        infos = self._book_infos([b for b, _ in ranked])
        results = [{"id": b, "title": infos[b][1], "author": infos[b][2],
                    "n_words": infos[b][3], "score": s} for b, s in ranked]
        return {
            "query": query,
            "mode": mode,
            "n_terms": len(term_ids),                 # mots du vocabulaire qui correspondent
            "matched_terms": [self.term_of[t] for t in term_ids[:MAX_TERMS]],
            "n_books": len(scores),                   # livres contenant au moins un de ces mots
            "time_ms": round((time.perf_counter() - t0) * 1000, 1),
            "results": results,
        }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--mode", choices=MODES, default="exact")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--db", default=str(DEFAULT_DB))
    args = ap.parse_args()

    lib = Library(args.db)
    try:
        r = lib.search(args.query, args.mode, args.limit)
    except ValueError as e:
        raise SystemExit(f"Erreur : {e}")
    print(f"{r['n_books']} livres, {r['n_terms']} mots correspondants "
          f"(ex. {', '.join(r['matched_terms'][:8])}) en {r['time_ms']} ms")
    for b in r["results"]:
        print(f"  {b['score']:6d}  [{b['id']}] {b['title'][:60]}")


if __name__ == "__main__":
    main()