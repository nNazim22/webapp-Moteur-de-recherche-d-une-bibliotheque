"""Télécharge des livres du Projet Gutenberg (en anglais) pour constituer la bibliothèque.

Usage (depuis la racine du projet) :
    python backend/scripts/download_books.py --target 1700
    python backend/scripts/download_books.py --target 1700 --source catalog   # sans Gutendex
    python backend/scripts/download_books.py --source manifest                # corpus identique à l'auteur

Trois sources pour LA LISTE des livres (les textes viennent toujours de gutenberg.org) :
- manifest : la liste EXACTE des livres du projet (corpus/manifest.csv, fournie dans l'archive).
  Recrée le même corpus que l'auteur : c'est la source à utiliser pour reproduire les résultats.
- gutendex (par défaut) : API https://gutendex.com, livres triés par popularité.
  Parfois lente : les requêtes sont réessayées avec une attente croissante, et la page
  en cours est sauvegardée (data/next_page.txt) pour reprendre au bon endroit.
- catalog : catalogue officiel de Gutenberg (un seul fichier CSV, mis en cache dans
  data/pg_catalog.csv). Ne dépend pas de Gutendex ; livres pris dans l'ordre des numéros.

Dans les deux cas :
- on ne garde que les livres d'au moins --min-words mots, sans l'en-tête ni le pied de page Gutenberg ;
- relancer la commande reprend là où elle s'est arrêtée ;
- une erreur réseau ne fait JAMAIS écarter un livre.

Sortie :
    data/books/<id>.txt
    data/manifest.csv     (id, titre, auteur, nb_mots, url)  -> preuve de provenance
    data/rejected.txt     (ids écartés : trop courts ou sans texte disponible)
"""
import argparse
import csv
import io
import re
import time
from pathlib import Path

import requests

API = "https://gutendex.com/books/?languages=en"
CATALOG_URL = "https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv"
TEXT_URL = "https://www.gutenberg.org/ebooks/{id}.txt.utf-8"
DEFAULT_MANIFEST = Path(__file__).resolve().parents[2] / "corpus" / "manifest.csv"
HEADERS = {"User-Agent": "daar-projet2-etudiant (projet universitaire, Sorbonne Universite)"}
START = re.compile(r"\*\*\* ?START OF (?:THE|THIS) PROJECT GUTENBERG EBOOK.*", re.I)
END = re.compile(r"\*\*\* ?END OF (?:THE|THIS) PROJECT GUTENBERG EBOOK.*", re.I)
WORD = re.compile(r"\w+")
PERMANENT = (403, 404, 410)    # erreurs HTTP inutiles à réessayer


class Unavailable(Exception):
    """La page demandée n'existe pas (erreur HTTP permanente)."""


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


def fetch(url, tries, timeout, backoff):
    """GET avec réessais. Renvoie la réponse, ou None si le réseau échoue encore après `tries` essais.

    Lève Unavailable pour une erreur permanente (404...) : inutile de réessayer.
    """
    for attempt in range(1, tries + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout)
            if r.status_code in PERMANENT:
                raise Unavailable(f"HTTP {r.status_code}")
            r.raise_for_status()
            return r
        except Unavailable:
            raise
        except requests.RequestException as e:
            wait = backoff * 2 ** (attempt - 1)
            suite = f", nouvel essai dans {wait:.0f} s" if attempt < tries else ""
            print(f"  erreur ({type(e).__name__}), essai {attempt}/{tries}{suite}")
            if attempt < tries:
                time.sleep(wait)
    return None


def read_ids(path):
    return {line.strip() for line in path.read_text().splitlines() if line.strip()} if path.exists() else set()


# ---------------------------------------------------------------------------
# Sources de la liste des livres : chacune renvoie des lots (listes) de livres,
# au même format que Gutendex : id, title, authors, formats.
# ---------------------------------------------------------------------------

def gutendex_batches(args, net, checkpoint, state):
    url = args.api
    if checkpoint.exists() and not args.restart:
        url = checkpoint.read_text().strip() or args.api
        print(f"Reprise à la page Gutendex sauvegardée : {url}")
    while url:
        checkpoint.write_text(url)
        print(f"Lecture de la page Gutendex {url.rsplit('page=', 1)[-1] if 'page=' in url else 1}"
              f" (jusqu'à {args.timeout:.0f} s d'attente par essai)...")
        page = fetch(url, **net)
        if page is None:
            print("Gutendex ne répond pas. Relancez la même commande dans quelques minutes :"
                  " le téléchargement reprendra à cette page (ou essayez --source catalog).")
            state["stalled"] = True
            return
        data = page.json()
        yield data["results"]
        url = data.get("next")
    state["finished"] = True


def catalog_batches(args, net, out, state):
    cache = out / "pg_catalog.csv"
    if not cache.exists():
        print("Téléchargement du catalogue Gutenberg (une seule fois)...")
        r = fetch(args.catalog_url, tries=net["tries"], timeout=net["timeout"] * 2, backoff=net["backoff"])
        if r is None:
            print("Le catalogue n'a pas pu être téléchargé. Relancez la commande plus tard.")
            state["stalled"] = True
            return
        cache.write_bytes(r.content)
    text = cache.read_text(encoding="utf-8-sig", errors="replace")
    batch = []
    for row in csv.DictReader(io.StringIO(text, newline="")):
        if row.get("Type") != "Text":
            continue
        langs = [x.strip() for x in re.split(r"[;,]", row.get("Language") or "") if x.strip()]
        if langs != ["en"]:                      # uniquement les livres entièrement en anglais
            continue
        try:
            book_id = int(row["Text#"])
        except (KeyError, ValueError):
            continue
        author = (row.get("Authors") or "").strip()
        batch.append({
            "id": book_id,
            "title": " ".join((row.get("Title") or "Sans titre").split()),
            "authors": [{"name": author}] if author else [],
            "formats": {"text/plain; charset=utf-8": args.text_url.format(id=book_id)},
        })
        if len(batch) == 50:
            yield batch
            batch = []
    if batch:
        yield batch
    state["finished"] = True


def manifest_batches(args, state):
    """Les livres listés dans un manifeste (id, titre, auteur, nb_mots, url) : corpus identique à l'auteur."""
    path = Path(args.manifest)
    if not path.exists():
        print(f"Manifeste introuvable : {path}")
        state["stalled"] = True
        return
    batch = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            author = (row.get("auteur") or "").strip()
            batch.append({
                "id": int(row["id"]),
                "title": row.get("titre") or "Sans titre",
                "authors": [] if author in ("", "Inconnu") else [{"name": author}],
                "formats": {"text/plain; charset=utf-8": row["url"]},
            })
            if len(batch) == 50:
                yield batch
                batch = []
    if batch:
        yield batch
    state["finished"] = True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=1700, help="nombre de livres à garder")
    ap.add_argument("--source", choices=("gutendex", "catalog", "manifest"), default="gutendex",
                    help="où trouver la liste des livres")
    ap.add_argument("--min-words", type=int, default=10000)
    ap.add_argument("--out", default="data")
    ap.add_argument("--sleep", type=float, default=1.0, help="pause (s) entre deux téléchargements")
    ap.add_argument("--api", default=API, help="adresse de la première page Gutendex")
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="manifeste de la source « manifest »")
    ap.add_argument("--catalog-url", default=CATALOG_URL)
    ap.add_argument("--text-url", default=TEXT_URL, help="modèle d'adresse d'un livre (source catalog)")
    ap.add_argument("--timeout", type=float, default=90, help="délai maximal d'une requête (s)")
    ap.add_argument("--retries", type=int, default=5, help="nombre d'essais par requête")
    ap.add_argument("--backoff", type=float, default=3.0, help="attente avant le 2e essai (s), doublée ensuite")
    ap.add_argument("--restart", action="store_true",
                    help="(gutendex) repartir de la page 1 ; retente aussi les livres en échec réseau")
    args = ap.parse_args()
    net = dict(tries=args.retries, timeout=args.timeout, backoff=args.backoff)

    out = Path(args.out)
    books_dir = out / "books"
    books_dir.mkdir(parents=True, exist_ok=True)
    manifest = out / "manifest.csv"
    rejected_file = out / "rejected.txt"
    checkpoint = out / "next_page.txt"

    kept = set()
    if manifest.exists():
        with open(manifest, newline="", encoding="utf-8") as f:
            kept = {row["id"] for row in csv.DictReader(f)}
    rejected = read_ids(rejected_file)
    print(f"Reprise : {len(kept)} livres déjà gardés, {len(rejected)} écartés. Source : {args.source}.")

    new_file = not manifest.exists()
    mf = open(manifest, "a", newline="", encoding="utf-8")
    writer = csv.writer(mf)
    if new_file:
        writer.writerow(["id", "titre", "auteur", "nb_mots", "url"])
    rf = open(rejected_file, "a", encoding="utf-8")

    def reject(book_id):
        rejected.add(book_id)
        rf.write(book_id + "\n")
        rf.flush()

    failed = 0

    def handle(book):
        """Télécharge un livre et le garde s'il est assez long."""
        nonlocal failed
        book_id = str(book["id"])
        if book_id in kept or book_id in rejected:
            return
        link = text_url(book)
        if link is None:
            reject(book_id)
            return
        try:
            r = fetch(link, **net)
        except Unavailable:
            reject(book_id)
            return
        time.sleep(args.sleep)
        if r is None:                         # panne réseau : on NE rejette PAS le livre
            failed += 1
            print(f"  livre {book_id} : réseau indisponible, ignoré pour cette fois")
            return
        text = strip_gutenberg(r.content.decode("utf-8", errors="replace").lstrip("\ufeff"))
        n_words = len(WORD.findall(text))
        if n_words < args.min_words:
            reject(book_id)
            return
        (books_dir / f"{book_id}.txt").write_text(text, encoding="utf-8")
        authors = "; ".join(a["name"] for a in book.get("authors", [])) or "Inconnu"
        writer.writerow([book_id, book["title"], authors, n_words, link])
        mf.flush()
        kept.add(book_id)
        print(f"[{len(kept)}/{args.target}] {book_id} {book['title'][:50]} ({n_words} mots)")

    state = {"finished": False, "stalled": False}
    if args.source == "manifest":
        batches = manifest_batches(args, state)
    elif args.source == "catalog":
        batches = catalog_batches(args, net, out, state)
    else:
        batches = gutendex_batches(args, net, checkpoint, state)

    for books in batches:
        for book in books:
            if len(kept) >= args.target:
                break
            handle(book)
        if len(kept) >= args.target:
            break

    mf.close()
    rf.close()
    if state["finished"]:
        checkpoint.unlink(missing_ok=True)
        print("Fin de la liste.")
    if failed:
        print(f"{failed} livre(s) non téléchargés à cause du réseau : relancez avec --restart pour les retenter.")
    print(f"Terminé : {len(kept)} livres dans {books_dir}")


if __name__ == "__main__":
    main()
