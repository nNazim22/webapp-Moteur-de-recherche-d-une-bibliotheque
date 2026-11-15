"""Vérifie que la bibliothèque respecte les contraintes du sujet.

    - au moins 1664 livres ;
    - au moins 10 000 mots par livre (hors en-tête/pied de page Gutenberg) ;
    - chaque ligne du manifest.csv a son fichier data/books/<id>.txt (provenance traçable).

Usage (depuis la racine du projet) :
    python backend/scripts/validate_corpus.py [--data data] [--min-books 1664] [--min-words 10000]
Code de sortie 0 si tout est conforme, 1 sinon (utilisable en CI ou avant de rendre le projet).
"""
import argparse
import csv
import re
import sys
from pathlib import Path

WORD = re.compile(r"\w+")
START = re.compile(r"\*\*\* ?START OF (?:THE|THIS) PROJECT GUTENBERG EBOOK.*", re.I)
END = re.compile(r"\*\*\* ?END OF (?:THE|THIS) PROJECT GUTENBERG EBOOK.*", re.I)


def count_words(text):
    m = START.search(text)
    if m:
        text = text[m.end():]
    m = END.search(text)
    if m:
        text = text[:m.start()]
    return len(WORD.findall(text))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--min-books", type=int, default=1664)
    ap.add_argument("--min-words", type=int, default=10000)
    a = ap.parse_args()

    data = Path(a.data)
    manifest = data / "manifest.csv"
    if not manifest.exists():
        sys.exit(f"ERREUR : {manifest} introuvable (lancez setup_data.py)")
    with open(manifest, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    missing, short, sizes = [], [], []
    for r in rows:
        path = data / "books" / f"{r['id']}.txt"
        if not path.exists():
            missing.append(r["id"])
            continue
        n = count_words(path.read_text(encoding="utf-8", errors="replace"))
        sizes.append(n)
        if n < a.min_words:
            short.append((r["id"], n))

    ok = True
    print(f"Livres dans le manifest : {len(rows)}  (fichiers présents : {len(sizes)})")
    if sizes:
        sizes.sort()
        print(f"Mots par livre : min {sizes[0]:,}  médiane {sizes[len(sizes) // 2]:,}  max {sizes[-1]:,}".replace(",", " "))
    if len(sizes) < a.min_books:
        print(f"✗ {len(sizes)} livres < {a.min_books} demandés")
        ok = False
    if missing:
        print(f"✗ {len(missing)} fichiers manquants, ex. {missing[:5]}")
        ok = False
    if short:
        print(f"✗ {len(short)} livres de moins de {a.min_words} mots, ex. {short[:5]}")
        ok = False
    print("✓ Corpus conforme au sujet." if ok else "✗ Corpus NON conforme.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
