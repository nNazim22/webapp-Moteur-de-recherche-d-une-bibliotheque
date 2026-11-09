"""Télécharge des livres du Projet Gutenberg (en anglais) pour constituer la bibliothèque.

Usage :
    python backend/scripts/download_books.py --target 1700

- Métadonnées : API Gutendex (https://gutendex.com), livres triés par popularité.
- Textes : fichiers .txt de gutenberg.org, sans l'en-tête ni le pied de page Gutenberg.
- On ne garde que les livres d'au moins --min-words mots.
- Reprise automatique : relancer la commande continue là où elle s'est arrêtée.

Sortie :
    data/books/<id>.txt
    data/manifest.csv     (id, titre, auteur, nb_mots, url)  -> preuve de provenance
    data/rejected.txt     (ids écartés : trop courts ou illisibles)
"""
import argparse
import csv
import re
import time
from pathlib import Path

import requests

API = "https://gutendex.com/books/?languages=en"
HEADERS = {"User-Agent": "daar-projet2-etudiant (projet universitaire, Sorbonne Universite)"}
START = re.compile(r"\*\*\* ?START OF (?:THE|THIS) PROJECT GUTENBERG EBOOK.*", re.I)
END = re.compile(r"\*\*\* ?END OF (?:THE|THIS) PROJECT GUTENBERG EBOOK.*", re.I)
WORD = re.compile(r"\w+")


def strip_gutenberg(text):
    """Retire l'en-tête et le pied de page ajoutés par Gutenberg."""
    m = START.search(text)
    if m:
        text = text[m.end():]
    m = END.search(text)
    if m:
        text = text[:m.start()]
    return text.strip()


def text_url(book):
    """Adresse du fichier texte brut d'un livre (None s'il n'y en a pas)."""
    formats = book.get("formats", {})
    for key in ("text/plain; charset=utf-8", "text/plain; charset=us-ascii", "text/plain"):
        if key in formats:
            return formats[key]
    for key, url in formats.items():
        if key.startswith("text/plain") and not url.endswith(".zip"):
            return url
    return None


def fetch(url, tries=3):
    """GET avec quelques essais ; renvoie None si tout échoue."""
    for attempt in range(1, tries + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=60)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            print(f"  erreur ({e}), essai {attempt}/{tries}")
            time.sleep(2 * attempt)
    return None


def read_ids(path):
    return {line.strip() for line in path.read_text().splitlines() if line.strip()} if path.exists() else set()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=1700, help="nombre de livres à garder")
    ap.add_argument("--min-words", type=int, default=10000)
    ap.add_argument("--out", default="data")
    ap.add_argument("--sleep", type=float, default=1.0, help="pause (s) entre deux téléchargements")
    args = ap.parse_args()

    out = Path(args.out)
    books_dir = out / "books"
    books_dir.mkdir(parents=True, exist_ok=True)
    manifest = out / "manifest.csv"
    rejected_file = out / "rejected.txt"

    kept = set()
    if manifest.exists():
        with open(manifest, newline="", encoding="utf-8") as f:
            kept = {row["id"] for row in csv.DictReader(f)}
    rejected = read_ids(rejected_file)
    print(f"Reprise : {len(kept)} livres déjà gardés, {len(rejected)} écartés.")

    new_file = not manifest.exists()
    mf = open(manifest, "a", newline="", encoding="utf-8")
    writer = csv.writer(mf)
    if new_file:
        writer.writerow(["id", "titre", "auteur", "nb_mots", "url"])
    rf = open(rejected_file, "a", encoding="utf-8")

    url = API
    while url and len(kept) < args.target:
        page = fetch(url)
        if page is None:
            print("Impossible de lire la liste Gutendex, arrêt.")
            break
        data = page.json()
        for book in data["results"]:
            if len(kept) >= args.target:
                break
            book_id = str(book["id"])
            if book_id in kept or book_id in rejected:
                continue
            link = text_url(book)
            r = fetch(link) if link else None
            time.sleep(args.sleep)
            text = strip_gutenberg(r.content.decode("utf-8", errors="replace").lstrip("\ufeff")) if r else ""
            n_words = len(WORD.findall(text))
            if n_words < args.min_words:
                rejected.add(book_id)
                rf.write(book_id + "\n")
                rf.flush()
                continue
            (books_dir / f"{book_id}.txt").write_text(text, encoding="utf-8")
            authors = "; ".join(a["name"] for a in book.get("authors", [])) or "Inconnu"
            writer.writerow([book_id, book["title"], authors, n_words, link])
            mf.flush()
            kept.add(book_id)
            print(f"[{len(kept)}/{args.target}] {book_id} {book['title'][:50]} ({n_words} mots)")
        url = data.get("next")

    mf.close()
    rf.close()
    print(f"Terminé : {len(kept)} livres dans {books_dir}")


if __name__ == "__main__":
    main()