"""Construit l'index inversé de la bibliothèque dans une base SQLite.

Usage (depuis la racine du projet) :
    python backend/scripts/build_index.py

Entrée : data/manifest.csv et data/books/<id>.txt
Sortie : data/index.db avec 3 tables
    books(id, title, author, n_words)           -- n_words : mots après tokenisation
    vocab(term_id, term, doc_freq, total_count) -- les mots distincts de la bibliothèque
    postings(term_id, book_id, count)           -- index inversé : mot -> livre -> occurrences

L'index est reconstruit entièrement à chaque lancement : c'est rapide, et cela
permet de relancer après avoir téléchargé de nouveaux livres.
"""
import argparse
import csv
import re
import sqlite3
import time
from collections import Counter
from pathlib import Path

# Un mot = suite de lettres (sans chiffres ni "_"). Les apostrophes coupent les mots :
# "don't" donne "don" et "t" ; les mots d'une seule lettre sont ensuite supprimés.
TOKEN = re.compile(r"[^\W\d_]+")
MIN_LEN = 2


def tokenize(text):
    """Texte -> liste de mots en minuscules."""
    return [t for t in TOKEN.findall(text.lower()) if len(t) >= MIN_LEN]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data", help="dossier contenant manifest.csv et books/")
    args = ap.parse_args()

    data = Path(args.data)
    db_path = data / "index.db"
    if db_path.exists():
        db_path.unlink()

    con = sqlite3.connect(db_path)
    # Pas de journal : la base est reconstruite de zéro, on privilégie la vitesse.
    con.execute("PRAGMA journal_mode = OFF")
    con.execute("PRAGMA synchronous = OFF")
    con.executescript("""
        CREATE TABLE books(
            id INTEGER PRIMARY KEY, title TEXT, author TEXT, n_words INTEGER);
        CREATE TABLE postings(
            term_id INTEGER NOT NULL, book_id INTEGER NOT NULL, count INTEGER NOT NULL,
            PRIMARY KEY (term_id, book_id)) WITHOUT ROWID;
    """)

    term_ids = {}          # mot -> identifiant entier
    doc_freq = Counter()   # identifiant -> nombre de livres contenant le mot
    total = Counter()      # identifiant -> nombre total d'occurrences

    t0 = time.time()
    with open(data / "manifest.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    n_books = 0
    for i, row in enumerate(rows, 1):
        path = data / "books" / f"{row['id']}.txt"
        if not path.exists():
            print(f"  fichier manquant, livre ignoré : {path}")
            continue
        words = tokenize(path.read_text(encoding="utf-8", errors="replace"))
        counts = Counter(words)

        postings = []
        for term, c in counts.items():
            tid = term_ids.setdefault(term, len(term_ids) + 1)
            doc_freq[tid] += 1
            total[tid] += c
            postings.append((tid, int(row["id"]), c))
        con.executemany("INSERT INTO postings VALUES (?, ?, ?)", postings)
        con.execute("INSERT INTO books VALUES (?, ?, ?, ?)",
                    (int(row["id"]), row["titre"], row["auteur"], len(words)))
        n_books += 1
        if i % 50 == 0:
            print(f"  {i}/{len(rows)} livres indexés ({time.time() - t0:.0f} s)")

    # Table du vocabulaire : sert à la recherche par mot-clé et à la regex.
    con.execute("""CREATE TABLE vocab(
        term_id INTEGER PRIMARY KEY, term TEXT NOT NULL UNIQUE,
        doc_freq INTEGER NOT NULL, total_count INTEGER NOT NULL)""")
    con.executemany("INSERT INTO vocab VALUES (?, ?, ?, ?)",
                    ((tid, term, doc_freq[tid], total[tid]) for term, tid in term_ids.items()))
    con.commit()

    n_post = con.execute("SELECT COUNT(*) FROM postings").fetchone()[0]
    con.close()
    size_mb = db_path.stat().st_size / 1e6
    print(f"Terminé en {time.time() - t0:.0f} s : {n_books} livres, "
          f"{len(term_ids)} mots distincts, {n_post} entrées d'index, {size_mb:.0f} Mo.")


if __name__ == "__main__":
    main()