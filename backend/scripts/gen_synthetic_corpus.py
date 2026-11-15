"""Génère un corpus SYNTHÉTIQUE (faux livres) pour développer et tester hors connexion.

⚠ À n'utiliser que pour le développement, les tests de charge et la validation du pipeline.
  Le corpus rendu / présenté dans le rapport doit venir de Project Gutenberg
  (backend/scripts/setup_data.py) : ces textes n'ont aucun sens et leurs résultats de
  recherche ne sont pas représentatifs d'une vraie bibliothèque.

Modèle : vocabulaire global à loi de Zipf (comme une langue réelle) + vocabulaire de thème.
Chaque livre est rattaché à un thème : les livres d'un même thème partagent des mots rares,
donc le graphe de Jaccard a une vraie structure de communautés (utile pour tester
centralités, classement et suggestions).

Usage (depuis la racine du projet) :
    python backend/scripts/gen_synthetic_corpus.py --out data-synth --books 1664
    DAAR_DATA=data-synth python backend/scripts/build_index.py --data data-synth
    python backend/scripts/build_graph.py --data data-synth
    DAAR_DATA=data-synth uvicorn app.main:app --app-dir backend
"""
import argparse
import csv
import textwrap
import time
from pathlib import Path

import numpy as np

LETTERS = "abcdefghijklmnopqrstuvwxyz"
SYLLABLES = [c + v for c in "bcdfghjklmnprstvwz" for v in "aeiou"] + list("aeiou")


def make_words(rng, n, min_syl=1, max_syl=4):
    """n mots distincts, fabriqués par assemblage de syllabes (suffisamment « langue naturelle »)."""
    words = set()
    while len(words) < n:
        k = rng.integers(min_syl, max_syl + 1)
        words.add("".join(rng.choice(SYLLABLES, size=k)))
    return sorted(words)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default="data-synth", help="dossier de sortie (contiendra books/ et manifest.csv)")
    ap.add_argument("--books", type=int, default=1664)
    ap.add_argument("--min-words", type=int, default=10000)
    ap.add_argument("--max-words", type=int, default=40000)
    ap.add_argument("--themes", type=int, default=20)
    ap.add_argument("--vocab", type=int, default=30000, help="taille du vocabulaire global")
    ap.add_argument("--theme-vocab", type=int, default=1500)
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()

    rng = np.random.default_rng(a.seed)
    out = Path(a.out)
    (out / "books").mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    glob = np.array(make_words(rng, a.vocab))
    zipf = 1.0 / np.arange(1, a.vocab + 1)
    zipf /= zipf.sum()
    themes = [np.array(make_words(rng, a.theme_vocab, 2, 5)) for _ in range(a.themes)]
    theme_zipf = 1.0 / np.arange(1, a.theme_vocab + 1)
    theme_zipf /= theme_zipf.sum()

    with open(out / "manifest.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "titre", "auteur", "nb_mots", "url"])
        for i in range(a.books):
            book_id = 100000 + i                        # ids hors plage Gutenberg usuelle
            theme = int(rng.integers(a.themes))
            n = int(rng.integers(a.min_words, a.max_words + 1))
            share = rng.uniform(0.15, 0.40)             # part du texte propre au thème
            n_theme = int(n * share)
            words = np.concatenate([
                rng.choice(glob, size=n - n_theme, p=zipf),
                rng.choice(themes[theme], size=n_theme, p=theme_zipf),
            ])
            rng.shuffle(words)
            body = textwrap.fill(" ".join(words), width=70)
            title = f"Synthetic Book {i + 1:04d} (theme {theme})"
            (out / "books" / f"{book_id}.txt").write_text(
                f"Title: {title}\n\n*** START OF THE PROJECT GUTENBERG EBOOK {title} ***\n\n{body}\n\n"
                f"*** END OF THE PROJECT GUTENBERG EBOOK {title} ***\nSynthetic licence text\n",
                encoding="utf-8")
            w.writerow([book_id, title, f"Author {theme}", n, "synthetic://"])
            if (i + 1) % 200 == 0:
                print(f"  {i + 1}/{a.books} livres ({time.time() - t0:.0f} s)", flush=True)
    print(f"Corpus synthétique : {a.books} livres dans {out}/ en {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
