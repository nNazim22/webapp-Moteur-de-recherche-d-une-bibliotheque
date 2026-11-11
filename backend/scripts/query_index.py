"""Vérifie l'index : affiche les livres qui contiennent un mot, triés par occurrences.

Usage :
    python backend/scripts/query_index.py whale
    python backend/scripts/query_index.py whale --limit 10
"""
import argparse
import sqlite3

SQL = """
    SELECT b.id, b.title, p.count
    FROM vocab v
    JOIN postings p ON p.term_id = v.term_id
    JOIN books b ON b.id = p.book_id
    WHERE v.term = ?
    ORDER BY p.count DESC
    LIMIT ?
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("word")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--db", default="data/index.db")
    args = ap.parse_args()

    con = sqlite3.connect(args.db)
    rows = con.execute(SQL, (args.word.lower(), args.limit)).fetchall()
    n_vocab, n_books = con.execute(
        "SELECT (SELECT COUNT(*) FROM vocab), (SELECT COUNT(*) FROM books)").fetchone()
    print(f"Bibliothèque : {n_books} livres, {n_vocab} mots distincts")
    if not rows:
        print(f"Aucun livre ne contient « {args.word} ».")
    for book_id, title, count in rows:
        print(f"  {count:6d} occurrences  [{book_id}] {title[:60]}")


if __name__ == "__main__":
    main()