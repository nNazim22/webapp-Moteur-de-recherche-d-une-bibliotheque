"""Prépare toutes les données du projet : télécharge les livres, puis construit l'index.

Les données (data/) ne sont pas dans l'archive rendue : ce script les recrée.

Usage (depuis la racine du projet) :
    python backend/scripts/setup_data.py                 # tout faire (environ 45 à 90 min)
    python backend/scripts/setup_data.py --run           # puis lancer le serveur
    python backend/scripts/setup_data.py --source catalog
    python backend/scripts/setup_data.py --target 1664 --skip-index

Le script est reprenable : on peut l'interrompre (Ctrl+C) et le relancer, les livres déjà
téléchargés ne sont pas retéléchargés. Si une source de livres est en panne, il bascule seul
sur l'autre (Gutendex <-> catalogue officiel de Gutenberg).
Si corpus/manifest.csv existe (liste exacte des livres de l'auteur), ces livres sont téléchargés en
premier : le corpus est alors identique à celui du rapport.
Les options inconnues sont transmises à download_books.py (ex. --min-words, --sleep).
"""
import argparse
import csv
import importlib.util
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent          # backend/scripts
ROOT = HERE.parents[1]                          # racine du projet (ou /app dans le conteneur)
MIN_BOOKS = 1664                                # minimum demandé par le sujet
CORPUS_MANIFEST = ROOT / "corpus" / "manifest.csv"   # liste exacte des livres, fournie dans l'archive

SOURCES = {
    "auto": ["gutendex", "catalog", "gutendex", "catalog"],
    "manifest": ["manifest"],
    "gutendex": ["gutendex"] * 3,
    "catalog": ["catalog"] * 3,
}


def count_books(data):
    manifest = data / "manifest.csv"
    if not manifest.exists():
        return 0
    with open(manifest, newline="", encoding="utf-8") as f:
        return sum(1 for _ in csv.DictReader(f))


def download(args, extra, data):
    sources = list(SOURCES[args.source])
    if args.source == "auto" and Path(args.manifest).exists():
        sources.insert(0, "manifest")          # d'abord les livres exacts de l'auteur, puis les secours
    for attempt, source in enumerate(sources, 1):
        have = count_books(data)
        if have >= args.target:
            break
        print(f"\n=== Téléchargement, essai {attempt}/{len(sources)} (source : {source}) "
              f": {have}/{args.target} livres ===", flush=True)
        cmd = [sys.executable, str(HERE / "download_books.py"), "--target", str(args.target),
               "--source", source, "--out", str(data), "--manifest", args.manifest, *extra]
        code = subprocess.run(cmd).returncode
        if code != 0:
            print(f"(le téléchargement s'est terminé avec le code {code})")
        if count_books(data) < args.target and attempt < len(sources):
            print(f"Objectif non atteint, nouvel essai dans {args.pause:.0f} s...", flush=True)
            time.sleep(args.pause)


def build_index(args, data):
    index, manifest = data / "index.db", data / "manifest.csv"
    if index.exists() and index.stat().st_mtime >= manifest.stat().st_mtime and not args.force_index:
        print("\nIndex déjà à jour.")
        return
    print("\n=== Construction de l'index ===", flush=True)
    subprocess.run([sys.executable, str(HERE / "build_index.py"), "--data", str(data)], check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", type=int, default=1700, help="nombre de livres à télécharger (défaut : 1700)")
    ap.add_argument("--min-books", type=int, default=MIN_BOOKS, help="minimum exigé (défaut : 1664)")
    ap.add_argument("--source", choices=sorted(SOURCES), default="auto",
                    help="auto : livres du manifeste corpus/manifest.csv s'il existe, puis Gutendex et le "
                         "catalogue officiel en secours (défaut)")
    ap.add_argument("--manifest", default=str(CORPUS_MANIFEST), help="liste exacte des livres du projet")
    ap.add_argument("--data", default=str(ROOT / "data"), help="dossier des données (défaut : <projet>/data)")
    ap.add_argument("--pause", type=float, default=10, help="attente (s) entre deux essais")
    ap.add_argument("--skip-download", action="store_true", help="ne pas télécharger les livres")
    ap.add_argument("--skip-index", action="store_true", help="ne pas construire l'index")
    ap.add_argument("--force-index", action="store_true", help="reconstruire l'index même s'il est à jour")
    ap.add_argument("--run", action="store_true", help="lancer le serveur web à la fin")
    ap.add_argument("--port", type=int, default=8000, help="port du serveur avec --run")
    args, extra = ap.parse_known_args()

    data = Path(args.data)
    data.mkdir(parents=True, exist_ok=True)

    if not args.skip_download and importlib.util.find_spec("requests") is None:
        sys.exit("Le module « requests » est absent. Installez les dépendances :\n"
                 "    python -m pip install -r backend/requirements.txt\n"
                 "(ou lancez telecharger_donnees.bat sous Windows / telecharger_donnees.sh sous Linux, "
                 "qui le font pour vous).")

    try:
        if not args.skip_download:
            have = count_books(data)
            if have >= args.target:
                print(f"{have} livres déjà téléchargés : rien à télécharger.")
            else:
                print(f"Objectif : {args.target} livres (déjà là : {have}). Cela peut prendre 45 à 90 minutes ;"
                      " Ctrl+C interrompt, relancer la commande reprend.", flush=True)
                download(args, extra, data)

        n = count_books(data)
        if n == 0:
            sys.exit("Aucun livre téléchargé : impossible de construire l'index.")
        if not args.skip_index:
            build_index(args, data)
    except KeyboardInterrupt:
        sys.exit("\nInterrompu. Relancez la même commande pour reprendre là où ça s'est arrêté.")

    n = count_books(data)
    print(f"\n=== Bilan : {n} livres dans {data / 'books'} ===")
    if n >= args.min_books:
        print(f"Le minimum du sujet ({args.min_books} livres) est atteint.")
    else:
        print(f"ATTENTION : {n} livres seulement, le sujet en exige {args.min_books}. "
              "Relancez la commande (autre source, ou plus tard si le réseau est instable).")
    if (data / "index.db").exists():
        print("Pour lancer l'application :  cd backend  puis  uvicorn app.main:app --host 0.0.0.0")

    if args.run:
        print(f"\nServeur sur http://127.0.0.1:{args.port}/  (Ctrl+C pour arrêter)")
        env = {**os.environ, "DAAR_DB": str(data / "index.db")}
        try:
            subprocess.run([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0",
                            "--port", str(args.port)], cwd=ROOT / "backend", env=env)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
